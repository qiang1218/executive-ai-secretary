"""Message repository.

纯数据访问层：Message 的查询封装。
模块级函数 + ``db: AsyncSession`` 第一参数，风格与 ``repositories/audit.py`` 一致。
仅搬运查询语句，不包含业务逻辑（业务校验、审计、commit 仍由 service 负责）。
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Message


async def find_by_id(
    db: AsyncSession,
    message_id: uuid.UUID,
    *,
    conversation_id: uuid.UUID | None = None,
) -> Message | None:
    """按 id 查询，可选 conversation_id 过滤。"""
    statement = select(Message).where(Message.id == message_id)
    if conversation_id is not None:
        statement = statement.where(Message.conversation_id == conversation_id)
    return await db.scalar(statement)


async def list_by_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    *,
    after_sequence: int = 0,
    limit: int = 100,
) -> list[Message]:
    """按 conversation_id + sequence > after 查询，按 sequence 升序 + 分页。

    注意：返回 ``limit + 1`` 条以便调用方判断是否有下一页（与
    conversation_service.list_messages 的原有行为一致）。
    """
    result = await db.scalars(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.sequence > after_sequence,
        )
        .order_by(Message.sequence)
        .limit(limit + 1)
    )
    return list(result.all())


async def find_last_by_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID,
) -> Message | None:
    """查询 conversation 的最后一条消息（按 sequence 倒序取首条）。"""
    return await db.scalar(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sequence.desc())
        .limit(1)
    )
