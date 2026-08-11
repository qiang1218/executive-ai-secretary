"""MCP v2 Schema 管理 Pydantic 模型。

定义表级 schema 注册的请求/响应结构。
"""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── 列结构 ────────────────────────────────────────────────

class McpColumnSchema(BaseModel):
    """单个列的元数据描述。"""

    name: str = Field(description="列名")
    type: str = Field(description="数据类型，如 uuid / numeric / text / date")
    nullable: bool = Field(default=False, description="是否可为 NULL")
    comment: str = Field(default="", description="列注释")
    is_primary_key: bool = Field(default=False, description="是否为主键")
    references: dict[str, str] | None = Field(
        default=None,
        description="外键引用，如 {'table': 'dim_customer', 'column': 'id'}",
    )


# ── 输出 ──────────────────────────────────────────────────

class McpSchemaOut(BaseModel):
    """mcp_schema_registry 单条记录输出。"""

    id: str = Field(description="UUID")
    enterprise_id: str
    table_name: str
    display_name: str
    description: str
    category: str
    column_schema: list[McpColumnSchema] = Field(default_factory=list)
    is_enabled: bool
    is_indexed: bool
    max_rows: int
    query_timeout_seconds: int
    sample_rows: list[dict[str, Any]] | None = None
    schema_version: int
    last_refreshed_at: datetime.datetime | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class McpSchemaCatalogOut(BaseModel):
    """列表输出（含就绪度摘要）。"""

    tables: list[McpSchemaOut]
    total: int
    enabled_count: int
    last_refreshed_at: datetime.datetime | None = None


# ── 更新输入 ──────────────────────────────────────────────

class McpSchemaUpdate(BaseModel):
    """更新表配置的可选字段。"""

    model_config = {
        "extra": "forbid",
        "from_attributes": True,
        "validate_assignment": True,
    }

    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None)
    category: str | None = Field(default=None, max_length=80)
    is_enabled: bool | None = None
    max_rows: int | None = Field(default=None, ge=1, le=1000)
    query_timeout_seconds: int | None = Field(default=None, ge=1, le=60)


# ── 注册/注销流程 ─────────────────────────────────────────

class McpSchemaCandidateOut(BaseModel):
    """可注册的候选物理表（来自 ``BUILTIN_TABLES`` 但当前未在企业名下注册）。"""

    table_name: str
    display_name: str
    description: str
    category: str


class McpSchemaCandidateListOut(BaseModel):
    """候选物理表列表输出。"""

    candidates: list[McpSchemaCandidateOut]
    total: int


class McpSchemaRegisterIn(BaseModel):
    """注册新表的可选覆盖字段。``table_name`` 走 URL 路径,这里只允许改
    默认 ``is_enabled`` / ``max_rows`` / ``query_timeout_seconds``。"""

    model_config = {
        "extra": "forbid",
        "from_attributes": True,
    }

    is_enabled: bool | None = Field(default=None, description="注册后是否直接启用")
    max_rows: int | None = Field(default=None, ge=1, le=1000)
    query_timeout_seconds: int | None = Field(default=None, ge=1, le=60)


class McpSchemaDeleteOut(BaseModel):
    """注销结果。"""

    table_name: str
    deleted: bool
    message: str = Field(default="已注销")


# ── 刷新结果 ──────────────────────────────────────────────

class McpSchemaRefreshOut(BaseModel):
    """单表 schema 刷新结果。"""

    table_name: str
    schema_version: int
    columns_discovered: int
    refreshed_at: datetime.datetime
    error: str | None = None


# ── 向量索引配置 / 触发 / 状态 ────────────────────────────


class EmbeddingConfigIn(BaseModel):
    """配置 embedding 字段拼接规则。"""

    model_config = {"extra": "forbid"}

    content_fields: list[str] = Field(
        description="拼接成 content_text 的字段名列表（顺序敏感）"
    )
    metadata_fields: list[str] = Field(
        default_factory=list,
        description="冗余到 metadata_json 的字段名列表，用于检索过滤",
    )


class EmbeddingConfigOut(BaseModel):
    """embedding 配置 + 状态输出。"""

    table_name: str
    embedding_config_json: dict[str, Any] = Field(default_factory=dict)
    embedding_status: str = Field(description="idle / running / succeeded / failed / partial_success")
    embedding_summary_json: dict[str, Any] = Field(default_factory=dict)
    last_indexed_at: datetime.datetime | None = None
    embedding_locked_at: datetime.datetime | None = None


class EmbeddingTriggerOut(BaseModel):
    """触发索引构建的结果。"""

    table_name: str
    job_id: str
    status: str = Field(description="queued / running")


class EmbeddingStatsOut(BaseModel):
    """单表的 entity_embeddings 行级统计（按 index_status 分组）。"""

    table_name: str
    total: int = 0
    indexed: int = 0
    pending: int = 0
    failed: int = 0
    stale: int = 0
