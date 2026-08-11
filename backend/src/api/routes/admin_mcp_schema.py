"""MCP v2 Schema 管理路由。

挂载在 ``/admin/mcp-schemas`` 前缀下；v2 用 :class:`mcp_schema_registry` +
``discover_schema`` / ``query_schema`` / ``execute_query`` / ``semantic_search``
四个通用 MCP 工具代替旧版逐 case hardcode handler。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from api.deps import (
    McpSchemaServiceDep,
    EntityIndexerServiceDep,
    PrincipalDep,
)
from schemas.mcp_schema import (
    EmbeddingConfigIn,
    EmbeddingConfigOut,
    EmbeddingStatsOut,
    EmbeddingTriggerOut,
    McpSchemaCandidateListOut,
    McpSchemaCatalogOut,
    McpSchemaDeleteOut,
    McpSchemaOut,
    McpSchemaRefreshOut,
    McpSchemaRegisterIn,
    McpSchemaUpdate,
)

router = APIRouter(prefix="/admin/mcp-schemas", tags=["admin-mcp-schemas"])


@router.get("/candidates", response_model=McpSchemaCandidateListOut)
async def list_candidates(
    principal: PrincipalDep,
    service: McpSchemaServiceDep,
):
    """候选物理表列表(BUILTIN_TABLES - 已注册表),用于"勾选注册"工作流。"""

    return await service.list_candidates(principal)


@router.post("/register/{table_name}", response_model=McpSchemaOut, status_code=201)
async def register_schema(
    payload: McpSchemaRegisterIn | None = None,
    table_name: str = Path(description="物理表名"),
    principal: PrincipalDep = ...,
    service: McpSchemaServiceDep = ...,
):
    """注册一张新的物理表(从 BUILTIN_TABLES 模板创建 McpSchemaRegistry 行)。"""

    return await service.register_table(table_name, payload, principal)


@router.post("/unregister/{table_name}", response_model=McpSchemaDeleteOut)
async def unregister_schema(
    table_name: str = Path(description="物理表名"),
    principal: PrincipalDep = ...,
    service: McpSchemaServiceDep = ...,
):
    """注销某张表(只删 mcp_schema_registry 行,不删除物理表)。"""

    return await service.unregister_table(table_name, principal)


@router.get("", response_model=McpSchemaCatalogOut)
async def list_schemas(
    principal: PrincipalDep,
    service: McpSchemaServiceDep,
):
    """列出企业所有已注册的数据表 schema。"""
    return await service.list_schemas(principal)


@router.get("/{table_name}", response_model=McpSchemaOut)
async def get_schema(
    table_name: str = Path(description="物理表名"),
    principal: PrincipalDep = ...,
    service: McpSchemaServiceDep = ...,
):
    """获取指定表的 schema 详情。"""
    schema = await service.get_schema(table_name, principal)
    if schema is None:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
    return schema


@router.patch("/{table_name}", response_model=McpSchemaOut)
async def update_schema(
    payload: McpSchemaUpdate,
    table_name: str = Path(description="物理表名"),
    principal: PrincipalDep = ...,
    service: McpSchemaServiceDep = ...,
):
    """更新表配置（显示名称、启用状态、限制参数等）。"""
    schema = await service.update_schema(table_name, payload, principal)
    if schema is None:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
    return schema


@router.post("/{table_name}/refresh", response_model=McpSchemaRefreshOut)
async def refresh_schema(
    table_name: str = Path(description="物理表名"),
    principal: PrincipalDep = ...,
    service: McpSchemaServiceDep = ...,
):
    """刷新指定表的列结构（从数据库自动发现最新 schema）。"""
    return await service.refresh_schema(table_name, principal)


@router.post("/refresh-all", response_model=McpSchemaCatalogOut)
async def refresh_all_schemas(
    principal: PrincipalDep,
    service: McpSchemaServiceDep,
):
    """刷新企业所有注册表的 schema。"""
    return await service.refresh_all(principal)


# ── 向量索引（embedding）管理 ─────────────────────────────


@router.put(
    "/{table_name}/embedding/config",
    response_model=EmbeddingConfigOut,
)
async def configure_embedding(
    payload: EmbeddingConfigIn,
    table_name: str = Path(description="物理表名"),
    principal: PrincipalDep = ...,
    service: EntityIndexerServiceDep = ...,
):
    """配置单张表的 embedding 字段拼接规则。

    - ``content_fields``：用于拼接 ``content_text`` 的字段（顺序敏感）
    - ``metadata_fields``：冗余到 ``metadata_json`` 的字段，用于检索过滤

    配置完成后需调用 ``POST /{table_name}/embedding/trigger`` 触发索引构建。
    """
    row = await service.configure_embedding(
        table_name,
        content_fields=payload.content_fields,
        metadata_fields=payload.metadata_fields,
        principal=principal,
    )
    return EmbeddingConfigOut(
        table_name=row.table_name,
        embedding_config_json=row.embedding_config_json or {},
        embedding_status=row.embedding_status,
        embedding_summary_json=row.embedding_summary_json or {},
        last_indexed_at=row.last_indexed_at,
        embedding_locked_at=row.embedding_locked_at,
    )


@router.get(
    "/{table_name}/embedding/config",
    response_model=EmbeddingConfigOut,
)
async def get_embedding_config(
    table_name: str = Path(description="物理表名"),
    principal: PrincipalDep = ...,
    service: EntityIndexerServiceDep = ...,
):
    """查看单张表的 embedding 配置 + 当前构建状态。"""
    data = await service.get_embedding_config(table_name, principal)
    return EmbeddingConfigOut(**data)


@router.post(
    "/{table_name}/embedding/trigger",
    response_model=EmbeddingTriggerOut,
)
async def trigger_embedding(
    table_name: str = Path(description="物理表名"),
    principal: PrincipalDep = ...,
    service: EntityIndexerServiceDep = ...,
):
    """手动触发单张表的向量索引构建（异步 Job）。

    返回 ``job_id``，前端可轮询
    ``GET /{table_name}/embedding/config`` 查看构建状态
    （``embedding_status`` = running / succeeded / failed / partial_success）。
    """
    result = await service.trigger_indexing(table_name, principal)
    return EmbeddingTriggerOut(**result)


@router.get(
    "/{table_name}/embedding/stats",
    response_model=EmbeddingStatsOut,
)
async def get_embedding_stats(
    table_name: str = Path(description="物理表名"),
    principal: PrincipalDep = ...,
    service: EntityIndexerServiceDep = ...,
):
    """查看单张表 entity_embeddings 的行级统计（按 index_status 分组）。

    用于管理端展示"已索引 N 条 / 失败 M 条 / 待处理 K 条"。
    """
    from sqlalchemy import func, select
    from models.entity_embedding import EntityEmbedding

    # 复用 service 的 session
    session = service._session  # noqa: SLF001 — 同包内访问
    result = await session.execute(
        select(
            EntityEmbedding.index_status,
            func.count(EntityEmbedding.id),
        )
        .where(
            EntityEmbedding.enterprise_id == principal.enterprise_id,
            EntityEmbedding.source_table == table_name,
        )
        .group_by(EntityEmbedding.index_status)
    )
    counts = {row[0]: int(row[1]) for row in result.all()}
    return EmbeddingStatsOut(
        table_name=table_name,
        total=sum(counts.values()),
        indexed=counts.get("indexed", 0),
        pending=counts.get("pending", 0),
        failed=counts.get("failed", 0),
        stale=counts.get("stale", 0),
    )
