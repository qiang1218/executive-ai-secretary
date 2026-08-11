"""站内通知仓储层（纯数据访问）。"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import utc_now
from models import Notification


async def list_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    unread_only: bool = False,
    type_filter: str | None = None,
    limit: int = 50,
) -> list[Notification]:
    """列出用户的通知。"""
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    if type_filter:
        stmt = stmt.where(Notification.type == type_filter)
    result = await db.scalars(
        stmt.order_by(Notification.created_at.desc()).limit(limit)
    )
    return list(result.all())


async def unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    """未读通知数。"""
    result = await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
    )
    return int(result or 0)


async def mark_read(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    ids: list[uuid.UUID] | None = None,
    all_unread: bool = False,
) -> int:
    """标记已读；返回更新行数。"""
    if not ids and not all_unread:
        return 0
    now = utc_now()
    stmt = (
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=now)
    )
    if ids and not all_unread:
        stmt = stmt.where(Notification.id.in_(ids))
    result = await db.execute(stmt)
    return int(getattr(result, "rowcount", 0) or 0)


async def latest_by_type(
    db: AsyncSession, user_id: uuid.UUID, type_filter: str
) -> Notification | None:
    """取指定类型的最新一条通知。"""
    return await db.scalar(
        select(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.type == type_filter,
        )
        .order_by(Notification.created_at.desc())
        .limit(1)
    )


async def latest_digest(db: AsyncSession, user_id: uuid.UUID) -> Notification | None:
    """取最新一条邮件摘要通知。"""
    return await db.scalar(
        select(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.type.in_(("email_digest", "daily_brief")),
        )
        .order_by(Notification.created_at.desc())
        .limit(1)
    )
