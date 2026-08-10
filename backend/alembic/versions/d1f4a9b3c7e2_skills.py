"""skills

Revision ID: d1f4a9b3c7e2
Revises: b8f4c8a2d5e7
Create Date: 2026-08-10

新增 ``skills`` 表：全局 skill 库（不按企业隔离）。
- slug 唯一标识，hermes-agent 加载用
- files JSONB 存储完整文件树
- is_enabled 启用开关，启用时文件释放到共享目录 ``data/skills_active/``
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d1f4a9b3c7e2"
# 基于 9d5a2b7c1e40（phase3 closure v2，DB 当前版本）
# 注：b8f4c8a2d5e7 分支的 a1b2c3d4e5f6 表已通过其他方式应用到 DB，
# 需先执行 `alembic stamp b8f4c8a2d5e7` 把该分支标记为已应用（旧表 drop 不影响功能）
down_revision: Union[str, None] = "9d5a2b7c1e40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("root_file", sa.String(255), nullable=False, server_default=sa.text("'SKILL.md'")),
        sa.Column("files", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("slug", name="uq_skill_slug"),
        sa.Index("ix_skill_enabled", "is_enabled"),
    )


def downgrade() -> None:
    op.drop_table("skills")
