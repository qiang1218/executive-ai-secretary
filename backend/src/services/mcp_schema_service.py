"""MCP Schema 管理服务 — MCP v2 通用 3 步模式。

管理 ``mcp_schema_registry`` 表：注册、启用/停用、刷新 schema。
取代旧 ``McpToolService`` 的 case-by-case 工具管理模式。
"""

from __future__ import annotations

import datetime
import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.config import McpSchemaRegistry
from schemas.mcp_schema import (
    McpColumnSchema,
    McpSchemaCatalogOut,
    McpSchemaOut,
    McpSchemaRefreshOut,
    McpSchemaUpdate,
)
from services.authz import Principal

logger = logging.getLogger(__name__)

# ── 内置表注册清单 ────────────────────────────────────────

BUILTIN_TABLES: list[dict] = [
    {
        "table_name": "fact_opportunity",
        "display_name": "商机事实表",
        "description": "商机核心数据：编号、阶段、金额、预计关闭日期、赢率等",
        "category": "opportunity",
    },
    {
        "table_name": "fact_opportunity_participant",
        "display_name": "商机参与人表",
        "description": "商机的参与人员及角色（销售、售前、交付等）",
        "category": "opportunity",
    },
    {
        "table_name": "fact_opportunity_product",
        "display_name": "商机产品表",
        "description": "商机关联的产品/服务清单",
        "category": "opportunity",
    },
    {
        "table_name": "fact_delivery",
        "display_name": "交付事实表",
        "description": "项目交付数据：状态、进度、风险、金额、里程碑等",
        "category": "delivery",
    },
    {
        "table_name": "fact_finance_collection",
        "display_name": "回款事实表",
        "description": "回款与财务数据：应收/已收/未收金额、逾期天数、账龄等",
        "category": "collection",
    },
    {
        "table_name": "fact_target",
        "display_name": "目标事实表",
        "description": "经营目标数据：指标代码、目标值、周期等",
        "category": "target",
    },
    {
        "table_name": "dim_customer",
        "display_name": "客户维度表",
        "description": "客户主数据：名称、行业、区域、价值等级等",
        "category": "dimension",
    },
    {
        "table_name": "dim_person",
        "display_name": "人员维度表",
        "description": "人员主数据：姓名、角色、活跃状态等",
        "category": "dimension",
    },
    {
        "table_name": "daily_snapshot",
        "display_name": "日快照表",
        "description": "每日经营快照数据：指标 JSON、异常检测结果",
        "category": "snapshot",
    },
]


class McpSchemaService:
    """MCP Schema 管理服务。"""

    def __init__(self, session: AsyncSession):
        self._session = session

    # ── 查询 ──────────────────────────────────────────────

    async def list_schemas(self, principal: Principal) -> McpSchemaCatalogOut:
        """列出企业的所有注册表。"""
        result = await self._session.execute(
            select(McpSchemaRegistry)
            .where(McpSchemaRegistry.enterprise_id == principal.enterprise_id)
            .order_by(McpSchemaRegistry.category, McpSchemaRegistry.display_name)
        )
        rows = result.scalars().all()
        enabled_count = sum(1 for r in rows if r.is_enabled)
        last = max((r.last_refreshed_at for r in rows if r.last_refreshed_at), default=None)
        return McpSchemaCatalogOut(
            tables=[_to_out(r) for r in rows],
            total=len(rows),
            enabled_count=enabled_count,
            last_refreshed_at=last,
        )

    async def get_schema(
        self, table_name: str, principal: Principal
    ) -> McpSchemaOut | None:
        """获取单条注册记录。"""
        result = await self._session.execute(
            select(McpSchemaRegistry).where(
                McpSchemaRegistry.enterprise_id == principal.enterprise_id,
                McpSchemaRegistry.table_name == table_name,
            )
        )
        row = result.scalar_one_or_none()
        return _to_out(row) if row else None

    # ── 更新 ──────────────────────────────────────────────

    async def update_schema(
        self, table_name: str, payload: McpSchemaUpdate, principal: Principal
    ) -> McpSchemaOut | None:
        """更新表配置（显示名称、描述、启用状态等）。"""
        result = await self._session.execute(
            select(McpSchemaRegistry).where(
                McpSchemaRegistry.enterprise_id == principal.enterprise_id,
                McpSchemaRegistry.table_name == table_name,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        for field_name in ("display_name", "description", "category",
                           "is_enabled", "max_rows", "query_timeout_seconds"):
            val = getattr(payload, field_name, None)
            if val is not None:
                setattr(row, field_name, val)
        row.updated_at = datetime.datetime.now(datetime.timezone.utc)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_out(row)

    # ── Schema 刷新 ───────────────────────────────────────

    async def refresh_schema(
        self, table_name: str, principal: Principal
    ) -> McpSchemaRefreshOut:
        """刷新指定表的列结构（从数据库自动发现）。"""
        row = await self._ensure_registered(table_name, principal)
        try:
            columns = await _discover_columns(self._session, table_name)
            sample = await _fetch_sample_rows(self._session, table_name, limit=3)
        except Exception as e:
            logger.warning("mcp_schema_refresh_failed table=%s error=%s", table_name, e)
            return McpSchemaRefreshOut(
                table_name=table_name,
                schema_version=row.schema_version,
                columns_discovered=0,
                refreshed_at=datetime.datetime.now(datetime.timezone.utc),
                error=str(e),
            )

        row.column_schema = columns
        row.sample_rows = sample
        row.schema_version = row.schema_version + 1
        row.last_refreshed_at = datetime.datetime.now(datetime.timezone.utc)
        row.updated_at = row.last_refreshed_at
        await self._session.commit()

        return McpSchemaRefreshOut(
            table_name=table_name,
            schema_version=row.schema_version,
            columns_discovered=len(columns),
            refreshed_at=row.last_refreshed_at,
        )

    async def refresh_all(self, principal: Principal) -> McpSchemaCatalogOut:
        """刷新企业所有注册表的 schema。"""
        result = await self._session.execute(
            select(McpSchemaRegistry).where(
                McpSchemaRegistry.enterprise_id == principal.enterprise_id,
            )
        )
        rows = result.scalars().all()
        for row in rows:
            try:
                columns = await _discover_columns(self._session, row.table_name)
                sample = await _fetch_sample_rows(self._session, row.table_name, limit=3)
                row.column_schema = columns
                row.sample_rows = sample
                row.schema_version = row.schema_version + 1
                row.last_refreshed_at = datetime.datetime.now(datetime.timezone.utc)
                row.updated_at = row.last_refreshed_at
            except Exception as e:
                logger.warning("mcp_schema_refresh_all_failed table=%s error=%s",
                               row.table_name, e)
        await self._session.commit()

        return await self.list_schemas(principal)

    # ── 种子数据 ──────────────────────────────────────────

    async def seed_builtin_tables(self, enterprise_id: str) -> int:
        """为指定企业初始化内置表注册（幂等，已存在的跳过）。"""
        count = 0
        for spec in BUILTIN_TABLES:
            result = await self._session.execute(
                select(McpSchemaRegistry).where(
                    McpSchemaRegistry.enterprise_id == enterprise_id,
                    McpSchemaRegistry.table_name == spec["table_name"],
                )
            )
            if result.scalar_one_or_none() is not None:
                continue
            now = datetime.datetime.now(datetime.timezone.utc)
            self._session.add(McpSchemaRegistry(
                enterprise_id=enterprise_id,
                table_name=spec["table_name"],
                display_name=spec["display_name"],
                description=spec["description"],
                category=spec["category"],
                created_at=now,
                updated_at=now,
            ))
            count += 1
        if count:
            await self._session.commit()
        return count

    # ── 内部辅助 ──────────────────────────────────────────

    async def _ensure_registered(
        self, table_name: str, principal: Principal
    ) -> McpSchemaRegistry:
        """确保表已注册（不存在则从 BUILTIN_TABLES 中创建）。"""
        result = await self._session.execute(
            select(McpSchemaRegistry).where(
                McpSchemaRegistry.enterprise_id == principal.enterprise_id,
                McpSchemaRegistry.table_name == table_name,
            )
        )
        row = result.scalar_one_or_none()
        if row is not None:
            return row
        spec = next((t for t in BUILTIN_TABLES if t["table_name"] == table_name), None)
        now = datetime.datetime.now(datetime.timezone.utc)
        row = McpSchemaRegistry(
            enterprise_id=principal.enterprise_id,
            table_name=table_name,
            display_name=spec["display_name"] if spec else table_name,
            description=spec["description"] if spec else "",
            category=spec["category"] if spec else "",
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return row


# ── 模块级工具函数 ────────────────────────────────────────

async def _discover_columns(session: AsyncSession, table_name: str) -> list[dict]:
    """通过 SQLAlchemy Inspector 自动发现表结构。"""
    from sqlalchemy import inspect

    conn = await session.connection()
    engine = conn.engine
    # 获取同步引擎以运行 inspect
    sync_engine = engine.sync_engine if hasattr(engine, "sync_engine") else engine
    try:
        insp = inspect(sync_engine)
        columns = insp.get_columns(table_name)
        pk = insp.get_pk_constraint(table_name)
        fks = insp.get_foreign_keys(table_name)
    except Exception:
        # 如果 sync_engine 不可用，尝试直接通过 async engine
        insp = inspect(engine)
        columns = insp.get_columns(table_name)
        pk = insp.get_pk_constraint(table_name)
        fks = insp.get_foreign_keys(table_name)

    pk_columns = set(pk.get("constrained_columns", []))
    fk_map: dict[str, dict[str, str]] = {}
    for fk in fks:
        for col in fk.get("constrained_columns", []):
            fk_map[col] = {
                "table": fk.get("referred_table", ""),
                "column": fk.get("referred_columns", [""])[0],
            }

    return [
        {
            "name": col["name"],
            "type": str(col["type"]),
            "nullable": col.get("nullable", True),
            "comment": col.get("comment") or "",
            "is_primary_key": col["name"] in pk_columns,
            "references": fk_map.get(col["name"]),
        }
        for col in columns
    ]


async def _fetch_sample_rows(
    session: AsyncSession, table_name: str, limit: int = 3
) -> list[dict] | None:
    """获取表的示例数据行。"""
    from sqlalchemy import text as sa_text
    try:
        result = await session.execute(
            sa_text(f"SELECT * FROM {table_name} LIMIT :limit"),
            {"limit": limit},
        )
        rows = result.fetchall()
        if not rows:
            return None
        return [dict(r._mapping) for r in rows]
    except Exception:
        return None


def _to_out(row: McpSchemaRegistry) -> McpSchemaOut:
    """ORM 对象 -> Pydantic 输出模型。"""
    return McpSchemaOut(
        id=str(row.id),
        enterprise_id=str(row.enterprise_id),
        table_name=row.table_name,
        display_name=row.display_name,
        description=row.description,
        category=row.category,
        column_schema=[McpColumnSchema(**c) for c in (row.column_schema or [])],
        is_enabled=row.is_enabled,
        is_indexed=row.is_indexed,
        max_rows=row.max_rows,
        query_timeout_seconds=row.query_timeout_seconds,
        sample_rows=row.sample_rows,
        schema_version=row.schema_version,
        last_refreshed_at=row.last_refreshed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
