"""Conversation repository.

纯数据访问层：Conversation / ProjectConversation 的查询封装。
模块级函数 + ``db: AsyncSession`` 第一参数，风格与 ``repositories/audit.py`` 一致。
仅搬运查询语句，不包含业务逻辑（业务校验、审计、commit 仍由 service 负责）。
"""

from __future__ import annotations

import uuid
from typing import Literal

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Conversation, ProjectConversation
from services.authz import Principal


async def find_owned(
    db: AsyncSession,
    principal: Principal,
    conversation_id: uuid.UUID,
    *,
    lock: bool = False,
) -> Conversation | None:
    """按 id + enterprise_id + owner_user_id 查询（所有权校验）。

    返回 Conversation 或 None（不抛错，业务层负责抛 404）。

    来源：conversation_service._owned_conversation、fetch_stream_batch、
    job_management_service.retry_job、memory_service.create_memory。
    """
    statement = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.enterprise_id == principal.enterprise_id,
        # Content is always owner-private in phase one, including from admin/FDE.
        Conversation.owner_user_id == principal.user.id,
    )
    if lock:
        statement = statement.with_for_update()
    return await db.scalar(statement)


async def find_owned_active(
    db: AsyncSession,
    principal: Principal,
    conversation_id: uuid.UUID,
) -> Conversation | None:
    """同 find_owned 但额外过滤 archived_at IS NULL（用于 retry_job）。"""
    return await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.enterprise_id == principal.enterprise_id,
            Conversation.owner_user_id == principal.user.id,
            Conversation.archived_at.is_(None),
        )
    )


async def find_by_id_and_owner(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    enterprise_id: uuid.UUID,
    owner_user_id: uuid.UUID,
) -> Conversation | None:
    """SSE 流式查询用（fetch_stream_batch 静态方法）。

    与 find_owned 的区别：直接接收 enterprise_id / owner_user_id 参数，
    不依赖 Principal，便于在 router 的独立 SessionLocal 块中复用。
    """
    return await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.enterprise_id == enterprise_id,
            Conversation.owner_user_id == owner_user_id,
        )
    )


async def list_by_owner(
    db: AsyncSession,
    principal: Principal,
    *,
    cursor_id: uuid.UUID | None = None,
    limit: int = 50,
    project_id: uuid.UUID | None = None,
    placement: Literal["unassigned", "project", "all"] = "all",
    include_archived: bool = False,
) -> list[Conversation]:
    """按 owner 列表查询，含游标分页、项目归属过滤、归档过滤。

    注意：调用方仍需在 Python 层对返回结果做 assert_org_scope /
    normalize_scope 过滤（见 conversation_service.list_conversations）。
    """
    statement = select(Conversation).where(
        Conversation.enterprise_id == principal.enterprise_id,
        Conversation.owner_user_id == principal.user.id,
    )
    if project_id:
        statement = statement.join(
            ProjectConversation,
            ProjectConversation.conversation_id == Conversation.id,
        ).where(ProjectConversation.project_id == project_id)
    elif placement == "unassigned":
        statement = statement.where(
            ~exists(
                select(ProjectConversation.id).where(
                    ProjectConversation.conversation_id == Conversation.id
                )
            )
        )
    elif placement == "project":
        statement = statement.where(
            exists(
                select(ProjectConversation.id).where(
                    ProjectConversation.conversation_id == Conversation.id
                )
            )
        )
    if not include_archived:
        statement = statement.where(Conversation.archived_at.is_(None))
    if cursor_id:
        statement = statement.where(Conversation.id < cursor_id)
    statement = statement.order_by(Conversation.id.desc()).limit(limit + 1)
    result = await db.execute(statement)
    return list(result.scalars().all())


def list_ids_by_enterprise(db: AsyncSession, enterprise_id: uuid.UUID):
    """返回 ``select(Conversation.id).where(enterprise_id == ...)`` 语句对象。

    供 harness_admin_service 用作 ``.where(MessageRoute.conversation_id.in_(...))``
    的子查询参数。注意：返回的是 select 对象（未执行），调用方负责把它塞进
    ``in_()`` 子句中，而非直接迭代结果。
    """
    return select(Conversation.id).where(
        Conversation.enterprise_id == enterprise_id
    )
