"""MCP Schema 管理服务 — MCP v2 通用 3 步模式。

管理 ``mcp_schema_registry`` 表：注册、启用/停用、刷新 schema。
取代旧 ``McpToolService`` 的 case-by-case 工具管理模式。
"""

from __future__ import annotations

import datetime
import decimal
import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.config import McpSchemaRegistry
from schemas.mcp_schema import (
    McpColumnSchema,
    McpSchemaCandidateListOut,
    McpSchemaCandidateOut,
    McpSchemaCatalogOut,
    McpSchemaDeleteOut,
    McpSchemaOut,
    McpSchemaRefreshOut,
    McpSchemaRegisterIn,
    McpSchemaUpdate,
)
from exceptions.errors import AppError
from services.authz import Principal

logger = logging.getLogger(__name__)

# ── 内置表注册清单 ────────────────────────────────────────

BUILTIN_TABLES: list[dict] = [
    {
        "table_name": "ods_opportunity",
        "display_name": "商机 ODS 表",
        "description": "商机数据：编号、客户、销售负责人、预期/签约金额、阶段、行业等",
        "category": "opportunity",
    },
    {
        "table_name": "ods_delivery",
        "display_name": "交付 ODS 表",
        "description": "项目交付数据：项目编码、项目经理、合同金额、确认收入、完成率、延期天数等",
        "category": "delivery",
    },
    {
        "table_name": "ods_collection",
        "display_name": "回款 ODS 表",
        "description": "回款数据：应收/已收/未收金额、逾期天数、账龄、发票状态等",
        "category": "collection",
    },
]

# ODS 物理表位于 executive_source_v3 schema，查询前需设置 search_path
ODS_SCHEMA = "executive_source_v3"


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

    # ── 注册 / 注销 ──────────────────────────────────────

    async def list_candidates(self, principal: Principal) -> McpSchemaCandidateListOut:
        """列出 ``BUILTIN_TABLES`` 中尚未在企业名下注册的物理表。
        前端用这张候选清单完成"勾选注册"的工作流。
        """

        result = await self._session.execute(
            select(McpSchemaRegistry.table_name).where(
                McpSchemaRegistry.enterprise_id == principal.enterprise_id,
            )
        )
        registered = set(result.scalars().all())
        candidates = [
            McpSchemaCandidateOut(
                table_name=spec["table_name"],
                display_name=spec["display_name"],
                description=spec["description"],
                category=spec["category"],
            )
            for spec in BUILTIN_TABLES
            if spec["table_name"] not in registered
        ]
        return McpSchemaCandidateListOut(candidates=candidates, total=len(candidates))

    async def register_table(
        self,
        table_name: str,
        payload: McpSchemaRegisterIn | None,
        principal: Principal,
    ) -> McpSchemaOut:
        """从 ``BUILTIN_TABLES`` 注册一条表。重复注册/不在内置清单内的表名都拒绝。

        ``payload`` 是可选覆盖项,``is_enabled`` 默认 ``True``,``max_rows`` 默认
        ``100``,``query_timeout_seconds`` 默认 ``10``。
        """

        spec = next((t for t in BUILTIN_TABLES if t["table_name"] == table_name), None)
        if spec is None:
            raise AppError(
                404,
                "mcp_table_not_in_registry",
                f"表 {table_name!r} 不在候选清单内",
            )
        result = await self._session.execute(
            select(McpSchemaRegistry).where(
                McpSchemaRegistry.enterprise_id == principal.enterprise_id,
                McpSchemaRegistry.table_name == table_name,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            raise AppError(
                409,
                "mcp_table_already_registered",
                f"表 {table_name!r} 已被注册过",
            )
        is_enabled = True if payload is None or payload.is_enabled is None else payload.is_enabled
        max_rows = 100 if payload is None or payload.max_rows is None else payload.max_rows
        query_timeout = (
            10
            if payload is None or payload.query_timeout_seconds is None
            else payload.query_timeout_seconds
        )
        now = datetime.datetime.now(datetime.timezone.utc)
        row = McpSchemaRegistry(
            enterprise_id=principal.enterprise_id,
            table_name=spec["table_name"],
            display_name=spec["display_name"],
            description=spec["description"],
            category=spec["category"],
            is_enabled=is_enabled,
            max_rows=max_rows,
            query_timeout_seconds=query_timeout,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_out(row)

    async def unregister_table(
        self,
        table_name: str,
        principal: Principal,
    ) -> McpSchemaDeleteOut:
        """注销企业名下某张表(只删 mcp_schema_registry 行,不碰物理表)。

        业务规则:核心表(category=='core')/启用的表,在有审计记录的情况下
        仍然允许注销,以保证 admin 撤销误注册的能力;审计会记录事件。
        """

        result = await self._session.execute(
            select(McpSchemaRegistry).where(
                McpSchemaRegistry.enterprise_id == principal.enterprise_id,
                McpSchemaRegistry.table_name == table_name,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise AppError(
                404,
                "mcp_table_not_registered",
                f"表 {table_name!r} 当前未在企业名下注册",
            )
        await self._session.delete(row)

        # 同步清理 entity_embeddings 中该表的全部向量数据，
        # 避免注销后 semantic_search 仍返回已注销表的结果。
        # 使用独立 session 调用，避免 ORM delete 触发 mcp_schema_registry
        # 的级联加载（row 已 pending delete）。
        from services.entity_indexer_service import EntityIndexerService
        purge_service = EntityIndexerService(self._session, settings=None)
        try:
            purged = await purge_service.purge_embeddings(
                table_name, principal.enterprise_id
            )
            if purged:
                logger.info(
                    "mcp_schema_unregister_purged_embeddings table=%s count=%d",
                    table_name, purged,
                )
        except Exception as e:  # noqa: BLE001
            # purge 失败不阻塞注销，仅记录日志；残留向量由下次手动触发清理。
            logger.warning(
                "mcp_schema_unregister_purge_failed table=%s error=%s",
                table_name, e,
            )

        await self._session.commit()
        return McpSchemaDeleteOut(
            table_name=table_name,
            deleted=True,
            message="已注销" + (
                f"（已清理 {purged} 条向量数据）" if purged else ""
            ),
        )

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
    """通过 SQLAlchemy Inspector 自动发现表结构。

    在 AsyncEngine 下必须用 ``conn.run_sync`` 把 inspect 放到同步上下文里
    执行；直接对 AsyncEngine 或其 ``sync_engine`` 调 ``inspect`` 会抛
    "Inspection on an AsyncEngine is currently not supported"。
    """
    def _do_discover(sync_conn) -> list[dict]:
        from sqlalchemy import inspect, text
        # ODS 表在 executive_source_v3 schema，设置 search_path 让 inspect 能找到
        sync_conn.execute(text(f"SET search_path TO {ODS_SCHEMA}, public"))
        insp = inspect(sync_conn)
        columns = insp.get_columns(table_name)
        pk = insp.get_pk_constraint(table_name)
        fks = insp.get_foreign_keys(table_name)

        pk_columns = set(pk.get("constrained_columns", []))
        fk_map: dict[str, dict[str, str]] = {}
        for fk in fks:
            for col in fk.get("constrained_columns", []):
                fk_map[col] = {
                    "table": fk.get("referred_table", ""),
                    "column": (fk.get("referred_columns") or [""])[0],
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

    # 用 AsyncConnection.run_sync 确保回调收到的是 sync Connection
    conn = await session.connection()
    return await conn.run_sync(_do_discover)


async def _fetch_sample_rows(
    session: AsyncSession, table_name: str, limit: int = 3
) -> list[dict] | None:
    """获取表的示例数据行。"""
    from sqlalchemy import text as sa_text
    try:
        # ODS 表在 executive_source_v3 schema，设置 search_path
        await session.execute(sa_text(f"SET search_path TO {ODS_SCHEMA}, public"))
        result = await session.execute(
            sa_text(f"SELECT * FROM {table_name} LIMIT :limit"),
            {"limit": limit},
        )
        rows = result.fetchall()
        if not rows:
            return None
        return [_json_safe_row(r._mapping) for r in rows]
    except Exception:
        return None


def _json_safe_row(mapping) -> dict:
    """把 SQLAlchemy row mapping 转成 JSON 可序列化的 dict。

    数据库返回的行可能包含 ``datetime`` / ``date`` / ``Decimal`` / ``UUID``
    等原生 Python 类型，直接写入 JSONB 字段会触发
    ``TypeError: Object of type datetime is not JSON serializable``。
    这里统一转成 ``str`` 兜底，保证 ``json.dumps`` 与 JSONB 编码都能通过。
    """
    safe: dict = {}
    for key, value in mapping.items():
        if value is None:
            safe[key] = None
        elif isinstance(value, (str, int, float, bool)):
            safe[key] = value
        elif isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
            safe[key] = value.isoformat()
        elif isinstance(value, uuid.UUID):
            safe[key] = str(value)
        elif isinstance(value, decimal.Decimal):
            safe[key] = float(value)
        else:
            # bytes、enum、interval 等兜底转字符串
            safe[key] = str(value)
    return safe


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
