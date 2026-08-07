"""Drop legacy MCP v1 tables after Phase 4 cleanup.

Revision ID: b8f4c8a2d5e7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-07 18:00:00.000000

Removes the case-by-case MCP tool definitions that are now superseded by the
generic :class:`McpSchemaRegistry` model introduced in ``a1b2c3d4e5f6``. The
agent only ever consumes the three generic tools (``discover_schema``,
``query_schema``, ``execute_query``) backed by ``mcp_schema_registry``, so the
two legacy tables are no longer reachable from any application code path.
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "b8f4c8a2d5e7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("mcp_tool_configs")
    op.drop_table("mcp_tool_definitions")


def downgrade() -> None:
    # Recreate the legacy tables with the same shape as the v1 initial schema.
    # We do not attempt to restore historical rows; only the schema is needed
    # so ``alembic downgrade`` keeps a working lineage.

    op.create_table(
        "mcp_tool_configs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("enterprise_id", sa.UUID(), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "planner_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("max_rows", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("operator_note", sa.String(length=500), nullable=True),
        sa.Column("updated_by_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "enterprise_id", "tool_name", name="uq_mcp_tool_enterprise_name"
        ),
        sa.ForeignKeyConstraint(
            ["enterprise_id"], ["enterprises.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.Index("ix_mcp_tool_enterprise_enabled", "enterprise_id", "is_enabled"),
    )

    op.create_table(
        "mcp_tool_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("enterprise_id", sa.UUID(), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column(
            "tool_type",
            sa.String(length=32),
            nullable=False,
            server_default="composite",
        ),
        sa.Column("component_tools_json", sa.JSON(), nullable=False),
        sa.Column("domains_json", sa.JSON(), nullable=False),
        sa.Column("parameters_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("updated_by_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "enterprise_id", "tool_name", name="uq_mcp_definition_enterprise_name"
        ),
        sa.ForeignKeyConstraint(
            ["enterprise_id"], ["enterprises.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.Index(
            "ix_mcp_definition_enterprise_type", "enterprise_id", "tool_type"
        ),
    )
