"""entity_embeddings

Revision ID: f7a3c5e2d8b1
Revises: e2b3c4d5f6a7
Create Date: 2026-08-11

新增通用实体向量索引表 ``entity_embeddings``，并扩展 ``mcp_schema_registry``
加入向量索引配置/状态字段：

- ``entity_embeddings``  单表多实体，HNSW 索引；source_table 区分业务表
- ``mcp_schema_registry.embedding_config_json``    管理端配置拼接字段
- ``mcp_schema_registry.embedding_status``         构建状态机
- ``mcp_schema_registry.embedding_summary_json``   上次构建摘要
- ``mcp_schema_registry.embedding_locked_at``      并发锁时间戳
- ``mcp_schema_registry.last_indexed_at``          上次成功时间

向量维度固定为 1024（与 Anspire 网关 ``text-embedding-v4`` 一致）。
切换模型必须 DROP 表后重建。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql


revision: str = "f7a3c5e2d8b1"
down_revision: Union[str, None] = "e2b3c4d5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── entity_embeddings 表 ─────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "entity_embeddings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("enterprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_table", sa.String(120), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("content_text", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "index_status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["enterprise_id"], ["enterprises.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "enterprise_id",
            "source_table",
            "source_id",
            name="uq_entity_embedding_enterprise_source",
        ),
    )
    op.create_index(
        "ix_entity_emb_enterprise_id",
        "entity_embeddings",
        ["enterprise_id"],
    )
    op.create_index(
        "ix_entity_emb_enterprise_source",
        "entity_embeddings",
        ["enterprise_id", "source_table"],
    )
    op.create_index(
        "ix_entity_emb_embedding_hnsw",
        "entity_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # ── mcp_schema_registry 扩展字段 ─────────────────────
    op.add_column(
        "mcp_schema_registry",
        sa.Column(
            "embedding_config_json",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "mcp_schema_registry",
        sa.Column(
            "embedding_status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'idle'"),
        ),
    )
    op.add_column(
        "mcp_schema_registry",
        sa.Column(
            "embedding_summary_json",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "mcp_schema_registry",
        sa.Column("embedding_locked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "mcp_schema_registry",
        sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mcp_schema_registry", "last_indexed_at")
    op.drop_column("mcp_schema_registry", "embedding_locked_at")
    op.drop_column("mcp_schema_registry", "embedding_summary_json")
    op.drop_column("mcp_schema_registry", "embedding_status")
    op.drop_column("mcp_schema_registry", "embedding_config_json")

    op.drop_index("ix_entity_emb_embedding_hnsw", table_name="entity_embeddings")
    op.drop_index("ix_entity_emb_enterprise_source", table_name="entity_embeddings")
    op.drop_index("ix_entity_emb_enterprise_id", table_name="entity_embeddings")
    op.drop_table("entity_embeddings")
