"""Memory service.

Follows the anspire service pattern: a class that receives the database
session (and ``Settings`` when needed) in the constructor and exposes
business methods. The ``/memories`` router instantiates
``MemoryService(db, settings)`` and delegates all DB / business logic here.
"""

from __future__ import annotations

import uuid

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import Settings
from exceptions.errors import AppError
from models import Memory, MemoryEvent, new_uuid
from repositories import conversation as conversation_repo
from repositories.audit import record_audit
from services.authz import (
    Principal,
    accessible_organization_unit_ids,
    assert_org_scope,
)
from services.personal_data import ensure_memory_encrypted, set_memory_content
from schemas import MemoryCreate, MemoryOut, MemoryUpdate, Page


class MemoryService:
    """Service for long-term memory CRUD and lifecycle.

    Mirrors the anspire ``Service`` convention: stateless business logic
    layered on top of a SQLAlchemy ``AsyncSession``.
    """

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    # ------------------------------------------------------------------ utils

    def _memory_out(self, item: Memory) -> MemoryOut:
        return MemoryOut.model_validate(item).model_copy(
            update={"content": ensure_memory_encrypted(item, self._settings)}
        )

    async def _owned_memory(self, principal: Principal, memory_id: uuid.UUID) -> Memory:
        item = await self._session.scalar(
            select(Memory).where(
                Memory.id == memory_id,
                Memory.enterprise_id == principal.enterprise_id,
                # Long-term memory is private even from enterprise admin/FDE.
                Memory.user_id == principal.user.id,
                Memory.status != "deleted",
            )
        )
        if item is None:
            raise AppError(404, "memory_not_found", "记忆不存在")
        await assert_org_scope(self._session, principal, item.organization_unit_id)
        return item

    # ---------------------------------------------------------------- queries

    async def list_memories(
        self, principal: Principal, *, include_disabled: bool = False
    ) -> Page:
        statement = select(Memory).where(
            Memory.enterprise_id == principal.enterprise_id,
            Memory.user_id == principal.user.id,
            Memory.status != "deleted",
        )
        if not include_disabled:
            statement = statement.where(Memory.status == "active")
        result = await self._session.scalars(
            statement.order_by(Memory.updated_at.desc()).limit(100)
        )
        rows = result.all()
        if not rows:
            await self._session.commit()
            return Page(items=[])
        # 预计算可访问事业部集合（只查一次 DB），避免 N+1
        allowed = await accessible_organization_unit_ids(self._session, principal)
        visible = []
        for item in rows:
            try:
                await assert_org_scope(
                    self._session, principal, item.organization_unit_id, allowed=allowed
                )
            except AppError:
                continue
            visible.append(self._memory_out(item))
        await self._session.commit()
        return Page(items=visible)

    # --------------------------------------------------------------- mutations

    async def create_memory(
        self,
        payload: MemoryCreate,
        request: Request,
        principal: Principal,
    ) -> MemoryOut:
        await assert_org_scope(self._session, principal, payload.organization_unit_id)
        if payload.source_conversation_id:
            source = await conversation_repo.find_owned(
                self._session, principal, payload.source_conversation_id
            )
            if source is None:
                raise AppError(404, "conversation_not_found", "来源会话不存在")
        item = Memory(
            id=new_uuid(),
            enterprise_id=principal.enterprise_id,
            user_id=principal.user.id,
            organization_unit_id=payload.organization_unit_id,
            source_conversation_id=payload.source_conversation_id,
            kind=payload.kind,
            title=payload.title,
            content="",
        )
        set_memory_content(item, payload.content, self._settings)
        self._session.add(item)
        await self._session.flush()
        self._session.add(
            MemoryEvent(
                memory_id=item.id,
                actor_user_id=principal.user.id,
                event_type="created",
                new_content=None,
            )
        )
        await record_audit(
            self._session,
            request,
            "memory.created",
            actor=principal.user,
            session=principal.session,
            target_type="memory",
            target_id=item.id,
            metadata={"kind": item.kind, "content_length": len(payload.content)},
        )
        await self._session.commit()
        return self._memory_out(item)

    async def get_memory(self, principal: Principal, memory_id: uuid.UUID) -> MemoryOut:
        item = await self._owned_memory(principal, memory_id)
        output = self._memory_out(item)
        await self._session.commit()
        return output

    async def update_memory(
        self,
        memory_id: uuid.UUID,
        payload: MemoryUpdate,
        request: Request,
        principal: Principal,
    ) -> MemoryOut:
        item = await self._owned_memory(principal, memory_id)
        changes = payload.model_dump(exclude_unset=True)
        if "content" in changes:
            set_memory_content(item, changes.pop("content"), self._settings)
        for key, value in changes.items():
            setattr(item, key, value)
        item.version += 1
        self._session.add(
            MemoryEvent(
                memory_id=item.id,
                actor_user_id=principal.user.id,
                event_type="updated",
                previous_content=None,
                new_content=None,
            )
        )
        await record_audit(
            self._session,
            request,
            "memory.updated",
            actor=principal.user,
            session=principal.session,
            target_type="memory",
            target_id=item.id,
            metadata={"fields": sorted(changes)},
        )
        await self._session.commit()
        await self._session.refresh(item)
        return self._memory_out(item)

    async def delete_memory(
        self,
        memory_id: uuid.UUID,
        request: Request,
        principal: Principal,
    ) -> None:
        item = await self._owned_memory(principal, memory_id)
        item.status = "deleted"
        item.version += 1
        self._session.add(
            MemoryEvent(
                memory_id=item.id,
                actor_user_id=principal.user.id,
                event_type="deleted",
            )
        )
        await record_audit(
            self._session,
            request,
            "memory.deleted",
            actor=principal.user,
            session=principal.session,
            target_type="memory",
            target_id=item.id,
        )
        await self._session.commit()
