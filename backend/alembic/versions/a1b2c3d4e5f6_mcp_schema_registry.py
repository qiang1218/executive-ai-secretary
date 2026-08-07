"""mcp_schema_registry

Revision ID: a1b2c3d4e5f6
Revises: f31a6d902b47
Create Date: 2026-08-07

新增 mcp_schema_registry 表，替代旧 mcp_tool_configs/mcp_tool_definitions
的 case-by-case 模式，实现通用 3 步 MCP（discover_schema / query_schema / execute_query）。

- mcp_schema_registry: 企业级数据表 schema 注册，管理哪些表对 Agent 可见
- 旧表 (mcp_tool_configs / mcp_tool_definitions) 保持不变，后续 Phase 4 再清理
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f31a6d902b47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mcp_schema_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("enterprise_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("enterprises.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("table_name", sa.String(120), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("category", sa.String(80), nullable=False, server_default=sa.text("''")),
        sa.Column("column_schema", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_indexed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("max_rows", sa.Integer, nullable=False, server_default=sa.text("100")),
        sa.Column("query_timeout_seconds", sa.Integer, nullable=False,
                  server_default=sa.text("10")),
        sa.Column("sample_rows", postgresql.JSONB, nullable=True),
        sa.Column("schema_version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("enterprise_id", "table_name",
                            name="uq_mcp_schema_enterprise_table"),
        sa.Index("ix_mcp_schema_enterprise_enabled", "enterprise_id", "is_enabled"),
        sa.Index("ix_mcp_schema_enterprise_category", "enterprise_id", "category"),
    )


def downgrade() -> None:
    op.drop_table("mcp_schema_registry")
