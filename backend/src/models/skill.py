"""Skill 模型 — 全局 skill 库，文件内容以 JSONB 存储。

Skill 是 hermes-agent 的能力扩展单元（如代码审查、报告生成等工作流模板）。
admin 在 DB 中维护 skill 元数据与文件树（``files`` JSONB），启用时由
``skill_service`` 释放到 ``data/skills_active/<slug>/`` 共享目录，worker
通过 ``HERMES_HOME`` 环境变量让 hermes-agent 自动加载。
"""

from __future__ import annotations

from .base import *  # noqa: F401,F403  Base / JSONType / new_uuid / mixins / sqlalchemy symbols


class Skill(UUIDMixin, TimestampMixin, Base):
    """全局 skill 库（不按企业隔离）。

    ``files`` 字段存储完整文件树，格式如::

        {
            "SKILL.md": "---\\nname: code-review\\n---\\n# 代码审查...",
            "scripts/lint.py": "import sys\\n..."
        }

    admin 启用 skill 时，``skill_service`` 把 ``files`` 释放到
    ``data/skills_active/<slug>/`` 目录，worker 通过环境变量让 hermes-agent
    自动读取。
    """

    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_skill_slug"),
        Index("ix_skill_enabled", "is_enabled"),
    )

    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    """唯一标识，hermes 加载用。仅允许 ``[a-z0-9-]``，禁用 ``..`` / ``/``。"""

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    """显示名。"""

    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    """简短描述，用于 admin 列表展示。"""

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    """启用开关。启用时文件会落盘到共享目录。"""

    root_file: Mapped[str] = mapped_column(
        String(255), nullable=False, default="SKILL.md"
    )
    """主入口文件名（hermes-agent 默认读 ``SKILL.md``）。"""

    files: Mapped[dict[str, str]] = mapped_column(
        JSONType, default=dict, nullable=False
    )
    """完整文件树，``{相对路径: 文件内容}``。"""

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    """创建者 user_id（用于审计）。"""
