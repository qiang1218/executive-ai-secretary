"""实体向量索引构建服务。

负责把 ``mcp_schema_registry`` 中已注册的业务表（``ods_opportunity`` /
``ods_delivery`` / ``ods_collection`` …）的行内容拼接成 ``content_text``，
调用 Anspire 网关 ``text-embedding-v4`` 模型生成 embedding，集中写入
``entity_embeddings`` 表，供 MCP ``semantic_search`` 工具做最近邻检索。

设计要点：

1. **单表多实体**：``entity_embeddings.source_table`` 区分业务表，避免每张
   业务表都建一张向量表。HNSW 索引在百万级数据下查询仍 < 10ms。

2. **手动触发**：管理端配置 ``embedding_config_json`` 后调用
   ``POST /admin/mcp-schemas/{table}/embedding/trigger`` 触发，创建
   ``entity.index`` Job 异步执行；Job handler 调用本服务的
   :func:`run_indexing` 完成实际工作。

3. **增量索引**：``content_hash`` 记录 ``content_text`` 的 SHA256，重建时
   跳过 ``content_hash`` 未变更的行，节省 embedding 调用成本。

4. **失败隔离**：单批 embedding 调用失败只标记该批行为 ``failed``，不阻塞
   整个任务；下次触发时优先重新处理 ``failed`` 行。

5. **状态机**：``mcp_schema_registry.embedding_status`` 记录每张表的构建状态
   （idle / running / succeeded / failed / partial_success），
   ``embedding_summary_json`` 记录上次构建的统计结果。

6. **并发锁**：``embedding_locked_at`` 时间戳 + ``embedding_lock_timeout_seconds``
   超时检测，避免同一张表被并发触发。
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import logging
import uuid
from dataclasses import dataclass
from typing import Any

import asyncpg
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import Settings, get_settings
from core.security import utc_now
from exceptions.errors import AppError
from models.config import McpSchemaRegistry
from models.entity_embedding import EntityEmbedding
from services.authz import Principal
from services.embedding_client import (
    EmbeddingError,
    embed_texts,
    resolve_anspire_api_key,
)

logger = logging.getLogger(__name__)


# ── 常量 ──────────────────────────────────────────────────

# ODS 物理表所在的 schema；与 mcp_schema_service.ODS_SCHEMA 一致。
_ODS_SCHEMA = "executive_source_v3"

# embedding_config_json 默认配置（管理端未配置时使用）。
_DEFAULT_CONTENT_FIELDS_BY_TABLE: dict[str, list[str]] = {
    "ods_opportunity": [
        "title", "customer_name", "opportunity_code", "sales_owner",
        "stage_label", "industry", "latest_progress",
    ],
    "ods_delivery": [
        "project_name", "customer_name", "project_code", "project_manager",
        "status_label", "risk_level", "current_milestone", "latest_progress",
    ],
    "ods_collection": [
        "customer_name", "collection_code", "payment_type", "payment_milestone",
        "status_label", "aging_bucket", "invoice_status", "latest_follow_up",
    ],
}
_DEFAULT_METADATA_FIELDS_BY_TABLE: dict[str, list[str]] = {
    "ods_opportunity": ["status_code", "industry", "customer_value_level", "is_archived"],
    "ods_delivery": ["status_code", "risk_level", "organization_name"],
    "ods_collection": ["status_label", "aging_bucket", "organization_name"],
}


# ── 数据结构 ──────────────────────────────────────────────


@dataclass
class _IndexBatch:
    """单批待索引的业务行。"""
    source_ids: list[str]
    content_texts: list[str]
    metadata_dicts: list[dict[str, Any]]


# ── 异常 ──────────────────────────────────────────────────


class IndexingError(RuntimeError):
    """索引构建失败。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


# ── 服务 ──────────────────────────────────────────────────


class EntityIndexerService:
    """实体向量索引构建服务。"""

    def __init__(self, session: AsyncSession, settings: Settings | None = None):
        self._session = session
        self._settings = settings or get_settings()

    # ── 配置管理 ──────────────────────────────────────────

    async def configure_embedding(
        self,
        table_name: str,
        content_fields: list[str],
        metadata_fields: list[str] | None,
        principal: Principal,
    ) -> McpSchemaRegistry:
        """配置单张表的 embedding 字段拼接规则。

        ``content_fields`` 必填：用于拼接 ``content_text`` 的字段列表（顺序敏感）。
        ``metadata_fields`` 可选：冗余到 ``entity_embeddings.metadata_json`` 的字段，
        便于 ``semantic_search`` 做过滤；空列表表示只保留 ``source_id``。
        """
        if not content_fields:
            raise AppError(400, "invalid_embedding_config", "content_fields 不能为空")
        row = await self._get_registry_row(table_name, principal, for_update=True)
        row.embedding_config_json = {
            "content_fields": list(content_fields),
            "metadata_fields": list(metadata_fields or []),
        }
        row.updated_at = utc_now()
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def get_embedding_config(
        self, table_name: str, principal: Principal
    ) -> dict[str, Any]:
        """获取单张表的 embedding 配置 + 状态。"""
        row = await self._get_registry_row(table_name, principal)
        return {
            "table_name": row.table_name,
            "embedding_config_json": row.embedding_config_json or {},
            "embedding_status": row.embedding_status,
            "embedding_summary_json": row.embedding_summary_json or {},
            "last_indexed_at": row.last_indexed_at,
            "embedding_locked_at": row.embedding_locked_at,
        }

    # ── 触发索引 ──────────────────────────────────────────

    async def trigger_indexing(
        self, table_name: str, principal: Principal
    ) -> dict[str, Any]:
        """触发单张表的索引构建（创建 ``entity.index`` Job）。

        返回 ``{"job_id": ..., "table_name": ..., "status": "queued"}``。
        实际执行由 JobRunner 异步完成。
        """
        row = await self._get_registry_row(table_name, principal, for_update=True)
        if not row.embedding_config_json or not row.embedding_config_json.get("content_fields"):
            raise AppError(
                400,
                "embedding_not_configured",
                f"表 {table_name} 未配置 embedding 字段，请先调用 configure_embedding",
            )

        # 并发锁：同一张表正在构建时拒绝再次触发
        self._enforce_lock(row)

        # 创建 Job；handler 调用 run_indexing
        from models.job import Job
        job = Job(
            enterprise_id=principal.enterprise_id,
            job_type="entity.index",
            status="queued",
            max_attempts=self._settings.worker_job_max_attempts,
            payload_json={
                "table_name": table_name,
                "enterprise_id": str(principal.enterprise_id),
                "trigger_type": "manual",
            },
            scope_snapshot_json={"enterprise_id": str(principal.enterprise_id)},
            scheduled_at=utc_now(),
        )
        self._session.add(job)

        # 标记为 running（实际执行由 handler 完成；此处仅声明意图）
        row.embedding_status = "running"
        row.embedding_locked_at = utc_now()
        row.embedding_summary_json = {"status": "queued", "job_id": None}
        await self._session.commit()
        await self._session.refresh(job)
        # 回填 job_id 到 summary，便于管理端跟踪
        row.embedding_summary_json = {
            "status": "queued",
            "job_id": str(job.id),
            "queued_at": utc_now().isoformat(),
        }
        await self._session.commit()
        return {
            "job_id": str(job.id),
            "table_name": table_name,
            "status": "queued",
        }

    # ── 实际执行（由 Job handler 调用） ───────────────────

    async def run_indexing(
        self, enterprise_id: uuid.UUID, table_name: str
    ) -> dict[str, Any]:
        """执行实际的索引构建。

        步骤：
        1. 加锁：UPDATE mcp_schema_registry SET embedding_status='running' WHERE ...
        2. 读 embedding_config_json 配置
        3. 用 asyncpg 从 ODS 表读所有 is_deleted=false 的行
        4. 对每行拼 content_text + metadata_json + content_hash
        5. 比对现有 entity_embeddings.content_hash，分批调用 embedding API
        6. UPSERT entity_embeddings
        7. 删除源表已删除的行对应的 entity_embeddings
        8. 更新 mcp_schema_registry.embedding_status / summary
        """
        started_at = utc_now()
        # 1. 加锁 + 读配置
        row = await self._lock_and_load(enterprise_id, table_name)
        config = row.embedding_config_json or {}
        content_fields: list[str] = config.get("content_fields") or _DEFAULT_CONTENT_FIELDS_BY_TABLE.get(table_name, [])
        metadata_fields: list[str] = config.get("metadata_fields") or _DEFAULT_METADATA_FIELDS_BY_TABLE.get(table_name, [])
        if not content_fields:
            raise IndexingError(
                "no_content_fields",
                f"表 {table_name} 未配置 content_fields，无法构建索引",
            )

        # 2. 解析 Anspire API key（一次性，整个任务复用）
        api_key = await resolve_anspire_api_key(self._session)

        # 3. 读源表数据
        source_rows = await self._fetch_source_rows(table_name, content_fields, metadata_fields)

        # 4. 读现有 entity_embeddings（用于增量比对）
        existing_map = await self._load_existing(enterprise_id, table_name)

        # 5. 分批处理
        stats = _IndexStats(total=len(source_rows))
        batches = self._prepare_batches(source_rows, existing_map, content_fields, metadata_fields)
        for batch in batches:
            await self._process_batch(
                enterprise_id, table_name, batch, api_key, stats
            )

        # 6. 清理孤儿行（源表已删除的）
        orphans = await self._cleanup_orphans(enterprise_id, table_name, source_rows)
        stats.orphans_removed = orphans

        # 7. 更新状态 + 摘要
        stats.duration_seconds = (utc_now() - started_at).total_seconds()
        await self._finalize(enterprise_id, table_name, stats)
        return stats.to_dict()

    # ── 内部：锁 / 配置 ──────────────────────────────────

    async def _get_registry_row(
        self,
        table_name: str,
        principal: Principal,
        *,
        for_update: bool = False,
    ) -> McpSchemaRegistry:
        stmt = select(McpSchemaRegistry).where(
            McpSchemaRegistry.enterprise_id == principal.enterprise_id,
            McpSchemaRegistry.table_name == table_name,
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise AppError(
                404,
                "mcp_table_not_registered",
                f"表 {table_name} 未在 mcp_schema_registry 注册",
            )
        return row

    async def _lock_and_load(
        self, enterprise_id: uuid.UUID, table_name: str
    ) -> McpSchemaRegistry:
        """Job handler 入口：抢锁 + 读配置。

        如果锁已被占用且未超时，直接拒绝；超时则强制接管。
        """
        stmt = (
            select(McpSchemaRegistry)
            .where(
                McpSchemaRegistry.enterprise_id == enterprise_id,
                McpSchemaRegistry.table_name == table_name,
            )
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise IndexingError(
                "table_not_registered",
                f"表 {table_name} 未在 mcp_schema_registry 注册",
            )

        now = utc_now()
        if row.embedding_status == "running" and row.embedding_locked_at is not None:
            elapsed = (now - row.embedding_locked_at).total_seconds()
            if elapsed < self._settings.embedding_lock_timeout_seconds:
                raise IndexingError(
                    "already_running",
                    f"表 {table_name} 正在构建中（{int(elapsed)}s 前），请稍后再试",
                )
            logger.warning(
                "entity_indexer_lock_stale table=%s elapsed=%ss, taking over",
                table_name, int(elapsed),
            )

        row.embedding_status = "running"
        row.embedding_locked_at = now
        row.embedding_summary_json = {"status": "running", "started_at": now.isoformat()}
        await self._session.commit()
        return row

    def _enforce_lock(self, row: McpSchemaRegistry) -> None:
        """管理端触发时检查锁状态。"""
        if row.embedding_status != "running":
            return
        if row.embedding_locked_at is None:
            return
        elapsed = (utc_now() - row.embedding_locked_at).total_seconds()
        if elapsed < self._settings.embedding_lock_timeout_seconds:
            raise AppError(
                409,
                "embedding_already_running",
                f"表 {row.table_name} 正在构建中（{int(elapsed)}s 前），请稍后再试",
            )
        # 超时：管理端可以触发，handler 入口会接管

    # ── 内部：源数据读取 ─────────────────────────────────

    async def _fetch_source_rows(
        self,
        table_name: str,
        content_fields: list[str],
        metadata_fields: list[str],
    ) -> list[dict[str, Any]]:
        """用 asyncpg 直接读 ODS 表（在 executive_source_v3 schema）。

        过滤 ``is_deleted = false``，只索引有效行。
        """
        dsn = self._settings.database_url.replace(
            "postgresql+asyncpg://", "postgresql://", 1
        )
        # asyncpg 单独开连接（不复用 SQLAlchemy session；ODS 表在另一个 schema）
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute(f"SET search_path TO {_ODS_SCHEMA}, public")
            # 字段列表：id 必取，再加上 content_fields + metadata_fields 去重
            all_fields: list[str] = ["id"]
            seen = {"id"}
            for f in content_fields + metadata_fields:
                if f not in seen:
                    seen.add(f)
                    all_fields.append(f)
            # 字段名严格校验（防 SQL 注入）：只允许 [a-zA-Z_][a-zA-Z0-9_]*
            for f in all_fields:
                if not f.replace("_", "").isalnum():
                    raise IndexingError(
                        "invalid_field_name",
                        f"非法字段名：{f!r}（只允许字母数字下划线）",
                    )
            cols_sql = ", ".join(all_fields)
            sql = (
                f"SELECT {cols_sql} FROM {table_name} "
                f"WHERE is_deleted = false OR is_deleted IS NULL"
            )
            rows = await conn.fetch(sql)
            return [dict(r) for r in rows]
        finally:
            await conn.close()

    # ── 内部：增量比对 ───────────────────────────────────

    async def _load_existing(
        self, enterprise_id: uuid.UUID, table_name: str
    ) -> dict[str, EntityEmbedding]:
        """加载该表已有的 entity_embeddings，按 source_id 索引。"""
        result = await self._session.execute(
            select(EntityEmbedding).where(
                EntityEmbedding.enterprise_id == enterprise_id,
                EntityEmbedding.source_table == table_name,
            )
        )
        return {str(r.source_id): r for r in result.scalars().all()}

    def _prepare_batches(
        self,
        source_rows: list[dict[str, Any]],
        existing_map: dict[str, EntityEmbedding],
        content_fields: list[str],
        metadata_fields: list[str],
    ) -> list[_IndexBatch]:
        """把源表行分成待索引批次（跳过 content_hash 未变更的）。"""
        batch_size = self._settings.embedding_batch_size
        batches: list[_IndexBatch] = []
        current = _IndexBatch([], [], [])
        max_chars = self._settings.embedding_max_content_chars

        for row in source_rows:
            source_id = str(row["id"])
            content_text = self._build_content_text(row, content_fields)
            if len(content_text) > max_chars:
                content_text = content_text[:max_chars]
            content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()

            # 增量跳过：hash 一致 + 已 indexed
            existing = existing_map.get(source_id)
            if (
                existing is not None
                and existing.content_hash == content_hash
                and existing.index_status == "indexed"
            ):
                continue

            metadata = self._build_metadata(row, metadata_fields)
            current.source_ids.append(source_id)
            current.content_texts.append(content_text)
            current.metadata_dicts.append(metadata)
            if len(current.source_ids) >= batch_size:
                batches.append(current)
                current = _IndexBatch([], [], [])
        if current.source_ids:
            batches.append(current)
        return batches

    @staticmethod
    def _build_content_text(row: dict[str, Any], fields: list[str]) -> str:
        """拼接 content_text：把字段值转字符串后用空格连接。"""
        parts: list[str] = []
        for f in fields:
            val = row.get(f)
            if val is None:
                continue
            # 数组类型（如 text[]）转字符串
            if isinstance(val, (list, tuple)):
                val = " ".join(str(v) for v in val if v)
            else:
                val = str(val)
            if val:
                parts.append(val)
        return " ".join(parts)

    @staticmethod
    def _build_metadata(row: dict[str, Any], fields: list[str]) -> dict[str, Any]:
        """构造 metadata_json：保留 metadata_fields 字段的原始值。"""
        meta: dict[str, Any] = {}
        for f in fields:
            val = row.get(f)
            if val is None:
                continue
            # 数组/list 转 list（JSONB 兼容）
            if isinstance(val, tuple):
                val = list(val)
            # datetime / date / Decimal 转字符串
            if isinstance(val, (datetime.datetime, datetime.date)):
                val = val.isoformat()
            try:
                import decimal
                if isinstance(val, decimal.Decimal):
                    val = float(val)
            except Exception:  # noqa: BLE001
                pass
            meta[f] = val
        return meta

    # ── 内部：批次处理 ───────────────────────────────────

    async def _process_batch(
        self,
        enterprise_id: uuid.UUID,
        table_name: str,
        batch: _IndexBatch,
        api_key: str,
        stats: "_IndexStats",
    ) -> None:
        """处理单个批次：调用 embedding API + UPSERT entity_embeddings。"""
        n = len(batch.source_ids)
        try:
            vectors = await embed_texts(
                batch.content_texts,
                settings=self._settings,
                api_key=api_key,
            )
        except EmbeddingError as exc:
            logger.warning(
                "entity_indexer_batch_failed table=%s count=%d code=%s err=%s",
                table_name, n, exc.code, exc,
            )
            stats.failed += n
            # 标记这批行为 failed
            await self._mark_batch_failed(enterprise_id, table_name, batch, str(exc))
            return

        # UPSERT
        now = utc_now()
        for i, source_id in enumerate(batch.source_ids):
            content_text = batch.content_texts[i]
            content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()
            metadata = batch.metadata_dicts[i]
            vector = vectors[i]

            existing = await self._session.scalar(
                select(EntityEmbedding).where(
                    EntityEmbedding.enterprise_id == enterprise_id,
                    EntityEmbedding.source_table == table_name,
                    EntityEmbedding.source_id == source_id,
                )
            )
            if existing is None:
                self._session.add(
                    EntityEmbedding(
                        enterprise_id=enterprise_id,
                        source_table=table_name,
                        source_id=source_id,
                        content_text=content_text,
                        content_hash=content_hash,
                        embedding=vector,
                        metadata_json=metadata,
                        index_status="indexed",
                        indexed_at=now,
                    )
                )
            else:
                existing.content_text = content_text
                existing.content_hash = content_hash
                existing.embedding = vector
                existing.metadata_json = metadata
                existing.index_status = "indexed"
                existing.error_message = None
                existing.indexed_at = now
            stats.indexed += 1
        await self._session.commit()

    async def _mark_batch_failed(
        self,
        enterprise_id: uuid.UUID,
        table_name: str,
        batch: _IndexBatch,
        error_message: str,
    ) -> None:
        """把批次中的行标记为 failed（不存在则创建 pending 行）。"""
        now = utc_now()
        truncated_err = error_message[:500]
        for i, source_id in enumerate(batch.source_ids):
            existing = await self._session.scalar(
                select(EntityEmbedding).where(
                    EntityEmbedding.enterprise_id == enterprise_id,
                    EntityEmbedding.source_table == table_name,
                    EntityEmbedding.source_id == source_id,
                )
            )
            if existing is None:
                self._session.add(
                    EntityEmbedding(
                        enterprise_id=enterprise_id,
                        source_table=table_name,
                        source_id=source_id,
                        content_text=batch.content_texts[i],
                        content_hash=hashlib.sha256(
                            batch.content_texts[i].encode("utf-8")
                        ).hexdigest(),
                        embedding=None,
                        metadata_json=batch.metadata_dicts[i],
                        index_status="failed",
                        error_message=truncated_err,
                        indexed_at=None,
                    )
                )
            else:
                existing.index_status = "failed"
                existing.error_message = truncated_err
        await self._session.commit()

    # ── 内部：孤儿清理 ───────────────────────────────────

    async def _cleanup_orphans(
        self,
        enterprise_id: uuid.UUID,
        table_name: str,
        source_rows: list[dict[str, Any]],
    ) -> int:
        """删除 entity_embeddings 中 source_id 已不在源表的行。"""
        source_ids = {str(r["id"]) for r in source_rows}
        result = await self._session.execute(
            select(EntityEmbedding).where(
                EntityEmbedding.enterprise_id == enterprise_id,
                EntityEmbedding.source_table == table_name,
            )
        )
        all_existing = result.scalars().all()
        removed = 0
        for emb in all_existing:
            if emb.source_id not in source_ids:
                await self._session.delete(emb)
                removed += 1
        if removed:
            await self._session.commit()
        return removed

    # ── 内部：收尾 ───────────────────────────────────────

    async def _finalize(
        self,
        enterprise_id: uuid.UUID,
        table_name: str,
        stats: "_IndexStats",
    ) -> None:
        """更新 mcp_schema_registry.embedding_status / summary。"""
        stmt = (
            select(McpSchemaRegistry)
            .where(
                McpSchemaRegistry.enterprise_id == enterprise_id,
                McpSchemaRegistry.table_name == table_name,
            )
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return

        if stats.failed == 0:
            status = "succeeded"
        elif stats.indexed > 0:
            status = "partial_success"
        else:
            status = "failed"

        now = utc_now()
        row.embedding_status = status
        row.embedding_locked_at = None
        row.last_indexed_at = now if stats.indexed > 0 else row.last_indexed_at
        row.embedding_summary_json = {
            **stats.to_dict(),
            "status": status,
            "finished_at": now.isoformat(),
        }
        # 同步 is_indexed 标记：只要有 indexed > 0 行就算已索引
        if stats.indexed > 0:
            row.is_indexed = True
        await self._session.commit()


# ── 统计 ──────────────────────────────────────────────────


@dataclass
class _IndexStats:
    """索引构建统计。"""
    total: int = 0
    indexed: int = 0
    failed: int = 0
    skipped: int = 0
    orphans_removed: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "indexed": self.indexed,
            "failed": self.failed,
            "skipped": self.skipped,
            "orphans_removed": self.orphans_removed,
            "duration_seconds": round(self.duration_seconds, 2),
        }


# ── Job handler 入口 ─────────────────────────────────────


async def run_entity_index(
    ctx: Any, job: Any, settings: Settings
) -> dict[str, Any]:
    """``entity.index`` Job handler 入口。

    供 ``services.job_runner`` 注册；payload 格式：
        {"table_name": "ods_opportunity", "enterprise_id": "<uuid>",
         "trigger_type": "manual"}
    """
    payload = dict(job.payload_json or {})
    table_name = payload.get("table_name")
    enterprise_id_str = payload.get("enterprise_id") or str(job.enterprise_id)
    if not table_name:
        return {
            "status": "skipped",
            "reason": "payload.table_name missing",
        }
    try:
        enterprise_id = uuid.UUID(enterprise_id_str)
    except (ValueError, TypeError):
        return {
            "status": "skipped",
            "reason": f"invalid enterprise_id: {enterprise_id_str!r}",
        }

    async with _AsyncSessionLocal() as session:
        svc = EntityIndexerService(session, settings)
        try:
            return await svc.run_indexing(enterprise_id, table_name)
        except IndexingError as exc:
            # 把错误写到 mcp_schema_registry.embedding_summary_json
            await _record_failure(session, enterprise_id, table_name, exc)
            return {"status": "failed", "code": exc.code, "message": str(exc)}


async def _record_failure(
    session: AsyncSession,
    enterprise_id: uuid.UUID,
    table_name: str,
    exc: IndexingError,
) -> None:
    """索引构建失败时更新 mcp_schema_registry 状态。"""
    stmt = (
        select(McpSchemaRegistry)
        .where(
            McpSchemaRegistry.enterprise_id == enterprise_id,
            McpSchemaRegistry.table_name == table_name,
        )
        .with_for_update()
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return
    row.embedding_status = "failed"
    row.embedding_locked_at = None
    row.embedding_summary_json = {
        "status": "failed",
        "error_code": exc.code,
        "error_message": str(exc),
        "finished_at": utc_now().isoformat(),
    }
    await session.commit()


def _AsyncSessionLocal():  # noqa: N802 — 延迟导入避免循环依赖
    from db.session import AsyncSessionLocal
    return AsyncSessionLocal()


__all__ = [
    "EntityIndexerService",
    "IndexingError",
    "run_entity_index",
]
