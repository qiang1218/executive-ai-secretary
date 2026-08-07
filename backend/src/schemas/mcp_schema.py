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


# ── 刷新结果 ──────────────────────────────────────────────

class McpSchemaRefreshOut(BaseModel):
    """单表 schema 刷新结果。"""

    table_name: str
    schema_version: int
    columns_discovered: int
    refreshed_at: datetime.datetime
    error: str | None = None
