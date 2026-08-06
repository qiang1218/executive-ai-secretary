"""Project repository: 纯数据访问，模块级函数 + ``db: AsyncSession`` 第一参数。

遵循 ``repositories/audit.py`` 风格：不引入 Repository 类，仅提供按
``find_by_xxx`` / ``list_by_xxx`` / ``save`` 命名的查询函数。Service 层
通过 ``from repositories import project as project_repo`` 后调用
``await project_repo.find_xxx(self._session, ...)``。

仅搬运查询语句，不包含业务逻辑（业务校验、审计、commit 仍由 service 负责）。
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Project
from services.authz import Principal


async def find_by_id(db: AsyncSession, project_id: uuid.UUID | str) -> Project | None:
    """按主键查询项目。"""
    return await db.scalar(select(Project).where(Project.id == project_id))


async def find_by_id_for_update(db: AsyncSession, project_id: uuid.UUID | str) -> Project | None:
    """按主键查询项目并加行锁。

    注意：与 ``user_repo.find_by_id_for_update`` 不同，这里不加方言判断，
    以保持与原 service 层 ``select(...).with_for_update()`` 行为完全一致
    （PostgreSQL 生效，SQLite 静默跳过 with_for_update）。
    """
    return await db.scalar(
        select(Project).where(Project.id == project_id).with_for_update()
    )


async def find_owned(
    db: AsyncSession,
    principal: Principal,
    project_id: uuid.UUID,
) -> Project | None:
    """按 id + enterprise_id + owner_user_id 查询（所有权校验）。

    返回 Project 或 None（不抛错，业务层负责抛 404 与 ``assert_org_scope``）。

    来源：project_service._owned_project。注意 Project 模型用 ``owner_user_id``
    而非 ``created_by_user_id``（与 Job 模型不同）。
    """
    return await db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.enterprise_id == principal.enterprise_id,
            Project.owner_user_id == principal.user.id,
        )
    )


async def find_owned_active(
    db: AsyncSession,
    principal: Principal,
    project_id: uuid.UUID,
) -> Project | None:
    """同 find_owned 但额外过滤 archived_at IS NULL。

    来源：conversation_service.create_conversation、update_conversation_project
    中对 ``Project.archived_at.is_(None)`` 的过滤逻辑。
    """
    return await db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.enterprise_id == principal.enterprise_id,
            Project.owner_user_id == principal.user.id,
            Project.archived_at.is_(None),
        )
    )


async def list_by_owner(
    db: AsyncSession,
    principal: Principal,
    *,
    cursor_id: uuid.UUID | None = None,
    limit: int = 50,
    include_archived: bool = False,
) -> list[Project]:
    """按 owner 列出项目，含游标分页、归档过滤。

    注意：调用方仍需在 Python 层对返回结果做 ``assert_org_scope`` 过滤
    （见 project_service.list_projects）。limit 参数按调用方约定，实际查询
    会取 ``limit + 1`` 行用于判断是否还有下一页，调用方据此计算 next_cursor。
    """
    statement = select(Project).where(
        Project.enterprise_id == principal.enterprise_id,
        Project.owner_user_id == principal.user.id,
    )
    if not include_archived:
        statement = statement.where(Project.archived_at.is_(None))
    if cursor_id:
        statement = statement.where(Project.id < cursor_id)
    statement = statement.order_by(Project.id.desc()).limit(limit + 1)
    result = await db.execute(statement)
    return list(result.scalars().all())


def list_ids_by_enterprise(db: AsyncSession, enterprise_id: uuid.UUID):
    """返回 ``select(Project.id).where(enterprise_id == ...)`` 语句对象。

    供调用方用作 ``.where(...in_(...))`` 的子查询参数。注意：返回的是 select
    对象（未执行），调用方负责把它塞进 ``in_()`` 子句中，而非直接迭代结果。
    """
    return select(Project.id).where(Project.enterprise_id == enterprise_id)


async def save(db: AsyncSession, project: Project) -> Project:
    """add + flush，返回已 flush 的实体（含主键）。"""
    db.add(project)
    await db.flush()
    return project
