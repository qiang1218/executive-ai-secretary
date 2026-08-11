"""邮件账户与邮件消息仓储层（纯数据访问）。"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import EmailAccount, EmailMessage


async def find_account_owned(
    db: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID
) -> EmailAccount | None:
    """返回属于 ``user_id`` 的邮件账户，否则 ``None``。"""
    return await db.scalar(
        select(EmailAccount).where(
            EmailAccount.id == account_id,
            EmailAccount.user_id == user_id,
        )
    )


async def list_accounts(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    include_disabled: bool = False,
) -> list[EmailAccount]:
    """列出用户的所有邮件账户。"""
    stmt = select(EmailAccount).where(EmailAccount.user_id == user_id)
    if not include_disabled:
        stmt = stmt.where(EmailAccount.is_enabled.is_(True))
    result = await db.scalars(stmt.order_by(EmailAccount.created_at.asc()))
    return list(result.all())


async def list_enabled_accounts(db: AsyncSession) -> list[EmailAccount]:
    """列出所有启用中的邮件账户（供 job 拉取用，跨用户）。"""
    result = await db.scalars(
        select(EmailAccount)
        .where(EmailAccount.is_enabled.is_(True))
        .order_by(EmailAccount.last_synced_at.asc().nulls_first())
    )
    return list(result.all())


async def list_recent_messages(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 50,
    unread_only: bool = False,
) -> list[EmailMessage]:
    """列出用户最近的邮件消息。"""
    stmt = select(EmailMessage).where(EmailMessage.user_id == user_id)
    if unread_only:
        stmt = stmt.where(EmailMessage.is_read.is_(False))
    result = await db.scalars(
        stmt.order_by(EmailMessage.received_at.desc()).limit(limit)
    )
    return list(result.all())


async def find_existing_uids(
    db: AsyncSession, account_id: uuid.UUID, uids: list[int]
) -> set[int]:
    """返回 ``account_id`` 下已存在的 ``message_uid`` 集合，用于去重。"""
    if not uids:
        return set()
    result = await db.scalars(
        select(EmailMessage.message_uid).where(
            EmailMessage.email_account_id == account_id,
            EmailMessage.message_uid.in_(uids),
        )
    )
    return set(result.all())


def find_existing_uids_sync(
    db, account_id: uuid.UUID, uids: list[int]
) -> set[int]:
    """同步版本：供 job handler 在同步 SQLAlchemy ``Session`` 中使用。"""
    if not uids:
        return set()
    result = db.scalars(
        select(EmailMessage.message_uid).where(
            EmailMessage.email_account_id == account_id,
            EmailMessage.message_uid.in_(uids),
        )
    )
    return set(result.all())


async def list_unnotified_since(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    since,
) -> list[EmailMessage]:
    """列出指定时间之后未计入通知的邮件（供每日摘要使用）。"""
    result = await db.scalars(
        select(EmailMessage).where(
            EmailMessage.user_id == user_id,
            EmailMessage.is_notified.is_(False),
            EmailMessage.received_at >= since,
        ).order_by(EmailMessage.received_at.asc())
    )
    return list(result.all())
