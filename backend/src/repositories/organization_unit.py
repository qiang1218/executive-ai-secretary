"""Organization unit repository: 纯数据访问，模块级函数 + ``db: AsyncSession`` 第一参数。

遵循 ``repositories/audit.py`` 风格：不引入 Repository 类，仅提供按
``find_by_xxx`` / ``list_by_xxx`` / ``save`` 命名的查询函数。
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import OrganizationUnit


async def find_by_id(db: AsyncSession, unit_id: uuid.UUID | str) -> OrganizationUnit | None:
    """按主键查询事业部。"""
    return await db.scalar(select(OrganizationUnit).where(OrganizationUnit.id == unit_id))


async def find_by_id_for_update(
    db: AsyncSession,
    unit_id: uuid.UUID | str,
) -> OrganizationUnit | None:
    """按主键查询事业部并加行锁。"""
    statement = (
        select(OrganizationUnit)
        .where(OrganizationUnit.id == unit_id)
        .with_for_update()
    )
    return await db.scalar(statement)


async def list_by_enterprise(
    db: AsyncSession,
    enterprise_id: uuid.UUID | str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[OrganizationUnit]:
    """列出企业内事业部（分页，按 sort_order / name 排序）。"""
    result = await db.scalars(
        select(OrganizationUnit)
        .where(OrganizationUnit.enterprise_id == enterprise_id)
        .order_by(OrganizationUnit.sort_order, OrganizationUnit.name)
        .limit(limit)
        .offset(offset)
    )
    return list(result.all())


async def list_by_parent(
    db: AsyncSession,
    parent_id: uuid.UUID | str,
) -> list[OrganizationUnit]:
    """按父节点查询（用于循环检测等场景）。"""
    result = await db.scalars(
        select(OrganizationUnit).where(OrganizationUnit.parent_id == parent_id)
    )
    return list(result.all())


async def save(db: AsyncSession, unit: OrganizationUnit) -> OrganizationUnit:
    """add + flush，返回已 flush 的实体（含主键）。"""
    db.add(unit)
    await db.flush()
    return unit
