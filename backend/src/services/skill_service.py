"""Skill 管理服务 — DB CRUD + 共享目录文件落盘。

核心职责：
1. 维护 ``skills`` 表的 CRUD
2. 启用时把 ``files`` JSONB 释放到 ``skills_active_dir/skills/<slug>/``
3. 停用/删除时清理目录
4. API 启动时同步所有 enabled skill 到目录

``skills_active_dir`` 作为 ``HERMES_HOME``，hermes-agent 自动从
``<HERMES_HOME>/skills/<slug>/SKILL.md`` 加载。
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import Settings, get_settings
from exceptions.errors import AppError
from models.skill import Skill
from schemas.skill import (
    SkillCreate,
    SkillListItem,
    SkillListOut,
    SkillOut,
    SkillUpdate,
)
from services.authz import Principal

logger = logging.getLogger(__name__)


class SkillService:
    """Skill 管理服务。"""

    def __init__(self, session: AsyncSession, settings: Settings | None = None):
        self._session = session
        self._settings = settings or get_settings()
        self._active_dir = Path(self._settings.skills_active_dir)
        # hermes-agent 从 <HERMES_HOME>/skills/<slug>/SKILL.md 加载
        self._skills_dir = self._active_dir / "skills"

    # ── 查询 ──────────────────────────────────────────────

    async def list_skills(self) -> SkillListOut:
        """列出所有 skill（不含 files 内容）。"""
        result = await self._session.execute(
            select(Skill).order_by(Skill.created_at.desc())
        )
        rows = list(result.scalars().all())
        enabled_count = sum(1 for r in rows if r.is_enabled)
        return SkillListOut(
            skills=[_to_list_item(r) for r in rows],
            total=len(rows),
            enabled_count=enabled_count,
        )

    async def get_skill(self, skill_id: str) -> SkillOut | None:
        """获取单条 skill 详情（含 files）。"""
        row = await self._session.get(Skill, skill_id)
        return _to_out(row) if row else None

    async def list_enabled_slugs(self) -> list[str]:
        """查询所有已启用 skill 的 slug（供 conversations 注入 worker）。"""
        result = await self._session.execute(
            select(Skill.slug).where(Skill.is_enabled.is_(True))
        )
        return list(result.scalars().all())

    # ── 创建 ──────────────────────────────────────────────

    async def create_skill(
        self, payload: SkillCreate, principal: Principal
    ) -> SkillOut:
        """新建 skill。如果 ``is_enabled=True``，同时落盘。"""
        # 检查 slug 唯一
        existing = await self._session.execute(
            select(Skill.id).where(Skill.slug == payload.slug)
        )
        if existing.scalar_one_or_none() is not None:
            raise AppError(409, "skill_slug_exists", f"slug '{payload.slug}' 已存在")

        row = Skill(
            slug=payload.slug,
            name=payload.name,
            description=payload.description,
            root_file=payload.root_file,
            is_enabled=payload.is_enabled,
            files=payload.files,
            created_by_user_id=principal.user.id,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)

        if row.is_enabled:
            self._write_to_disk(row)

        return _to_out(row)

    # ── 更新 ──────────────────────────────────────────────

    async def update_skill(
        self, skill_id: str, payload: SkillUpdate
    ) -> SkillOut | None:
        """编辑 skill。如果已启用且 files 或 is_enabled 变化，重新落盘。"""
        row = await self._session.get(Skill, skill_id)
        if row is None:
            return None

        was_enabled = row.is_enabled
        files_changed = False

        if payload.name is not None:
            row.name = payload.name
        if payload.description is not None:
            row.description = payload.description
        if payload.root_file is not None:
            row.root_file = payload.root_file
        if payload.is_enabled is not None:
            row.is_enabled = payload.is_enabled
        if payload.files is not None:
            row.files = payload.files
            files_changed = True

        await self._session.commit()
        await self._session.refresh(row)

        # 文件系统同步
        if row.is_enabled and (files_changed or not was_enabled):
            # 启用且文件有变化（或刚启用）→ 重新落盘
            self._write_to_disk(row)
        elif not row.is_enabled and was_enabled:
            # 刚停用 → 清理目录
            self._remove_from_disk(row.slug)

        return _to_out(row)

    # ── 删除 ──────────────────────────────────────────────

    async def delete_skill(self, skill_id: str) -> bool:
        """删除 skill。同时清理共享目录。"""
        row = await self._session.get(Skill, skill_id)
        if row is None:
            return False

        slug = row.slug
        await self._session.delete(row)
        await self._session.commit()

        self._remove_from_disk(slug)
        return True

    # ── 文件落盘 ──────────────────────────────────────────

    def _write_to_disk(self, skill: Skill) -> None:
        """把 skill.files 释放到 ``skills_active_dir/skills/<slug>/``。"""
        skill_dir = self._skills_dir / skill.slug
        # 先清空再写，避免旧文件残留
        if skill_dir.exists():
            shutil.rmtree(skill_dir, ignore_errors=True)
        skill_dir.mkdir(parents=True, exist_ok=True)

        for rel_path, content in skill.files.items():
            # 二次校验路径安全（防止 DB 中已存入恶意路径）
            if ".." in rel_path.split("/") or rel_path.startswith("/"):
                logger.warning("skip_unsafe_path skill=%s path=%s", skill.slug, rel_path)
                continue
            target = skill_dir / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        logger.info("skill_files_released slug=%s files=%d", skill.slug, len(skill.files))

    def _remove_from_disk(self, slug: str) -> None:
        """删除 ``skills_active_dir/skills/<slug>/`` 目录。"""
        # 校验 slug 安全（防止路径穿越）
        if ".." in slug or "/" in slug or "\\" in slug:
            logger.warning("skip_unsafe_slug slug=%s", slug)
            return
        skill_dir = self._skills_dir / slug
        if skill_dir.exists():
            shutil.rmtree(skill_dir, ignore_errors=True)
            logger.info("skill_files_removed slug=%s", slug)

    # ── 启动同步 ──────────────────────────────────────────

    async def sync_active_skills_to_disk(self) -> None:
        """API 启动时调用：把所有 enabled skill 重新落盘。

        避免 DB/磁盘不一致（如手动删了目录、迁移环境等）。
        """
        result = await self._session.execute(
            select(Skill).where(Skill.is_enabled.is_(True))
        )
        enabled_skills = list(result.scalars().all())

        # 清空 skills 目录再重新释放，确保干净
        if self._skills_dir.exists():
            shutil.rmtree(self._skills_dir, ignore_errors=True)
        self._skills_dir.mkdir(parents=True, exist_ok=True)

        for skill in enabled_skills:
            self._write_to_disk(skill)

        logger.info(
            "skills_synced_to_disk enabled_count=%d dir=%s",
            len(enabled_skills), self._skills_dir,
        )

    # ── worker 路径 ───────────────────────────────────────

    def get_hermes_home(self) -> Path:
        """返回 HERMES_HOME 路径（worker 通过环境变量读取）。"""
        return self._active_dir


# ── 辅助函数 ──────────────────────────────────────────────


def _to_out(row: Skill) -> SkillOut:
    return SkillOut(
        id=str(row.id),
        slug=row.slug,
        name=row.name,
        description=row.description,
        is_enabled=row.is_enabled,
        root_file=row.root_file,
        files=row.files or {},
        created_by_user_id=str(row.created_by_user_id) if row.created_by_user_id else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_list_item(row: Skill) -> SkillListItem:
    files = row.files or {}
    return SkillListItem(
        id=str(row.id),
        slug=row.slug,
        name=row.name,
        description=row.description,
        is_enabled=row.is_enabled,
        root_file=row.root_file,
        file_count=len(files),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
