"""User repository: 纯数据访问，模块级函数 + ``db: AsyncSession`` 第一参数。

遵循 ``repositories/audit.py`` 风格：不引入 Repository 类，仅提供按
``find_by_xxx`` / ``list_by_xxx`` / ``save`` 命名的查询函数。Service 层
通过 ``from repositories import user as user_repo`` 后调用
``await user_repo.find_xxx(self._session, ...)``。
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import User


async def find_by_id(db: AsyncSession, user_id: uuid.UUID | str) -> User | None:
    """按主键查询用户。"""
    return await db.scalar(select(User).where(User.id == user_id))


async def find_by_id_for_update(db: AsyncSession, user_id: uuid.UUID | str) -> User | None:
    """按主键查询用户并加行锁。"""
    statement = (
        select(User)
        .where(User.id == user_id)
        .with_for_update()
    )
    return await db.scalar(statement)


async def find_by_email(
    db: AsyncSession,
    email: str,
    *,
    enterprise_id: uuid.UUID | str | None = None,
) -> User | None:
    """按 email 查询（登录标识）。

    Email 在系统内作为登录标识，需跨租户唯一。默认不限定 enterprise_id
    （全局查重）；当传入 ``enterprise_id`` 时仅在企业内查询。
    """
    statement = select(User).where(User.email == email)
    if enterprise_id is not None:
        statement = statement.where(User.enterprise_id == enterprise_id)
    return await db.scalar(statement)


async def find_enterprise_user(
    db: AsyncSession,
    principal,
    user_id: uuid.UUID | str,
) -> User | None:
    """按 id + enterprise_id 查询企业内用户。

    ``principal`` 需提供 ``enterprise_id`` 属性（与 service 层
    ``Principal`` 协议一致）。
    """
    return await db.scalar(
        select(User).where(
            User.id == user_id,
            User.enterprise_id == principal.enterprise_id,
        )
    )


async def list_by_enterprise(
    db: AsyncSession,
    enterprise_id: uuid.UUID | str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[User]:
    """列出企业内用户（分页，按创建时间倒序）。"""
    result = await db.scalars(
        select(User)
        .where(User.enterprise_id == enterprise_id)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.all())


async def save(db: AsyncSession, user: User) -> User:
    """add + flush，返回已 flush 的实体（含主键）。"""
    db.add(user)
    await db.flush()
    return user
