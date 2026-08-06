"""Conversation service.

Follows the anspire service pattern: a class that receives the database
session in the constructor and exposes business methods. The ``/conversations``
router instantiates ``ConversationService(db)`` and delegates all DB / business
logic here.

The SSE ``stream_conversation`` endpoint remains in the router because it is
tightly coupled to HTTP transport concerns (SSE protocol, heartbeats,
``is_disconnected``). This module provides a static helper
``fetch_stream_batch`` so the router can reuse the DB query logic inside its
own ``SessionLocal()`` block.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any, Literal

from fastapi import Request
from sqlalchemy import delete, exists, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import get_settings
from core.pagination import decode_cursor, encode_cursor
from core.security import utc_now
from exceptions.errors import AppError
from models import (
    Clarification,
    Conversation,
    HarnessConfigVersion,
    HarnessDiagnosticGrant,
    Job,
    Message,
    MessageEvidence,
    ProjectConversation,
)
from repositories import conversation as conversation_repo
from repositories import job as job_repo
from repositories import message as message_repo
from repositories import project as project_repo
from repositories.audit import record_audit
from schemas import (
    ClarificationOut,
    ClarificationResolve,
    ConversationCreate,
    ConversationOut,
    ConversationProjectUpdate,
    ConversationUpdate,
    DiagnosticShareOut,
    MessageCreate,
    MessageEvidenceOut,
    MessageOut,
    OrganizationScopeInput,
    Page,
)
from services.authz import Principal, assert_org_scope
from services.conversation_scope import (
    legacy_scope,
    normalize_scope,
    persisted_scope,
    scope_changed,
    scope_out,
    scope_snapshot,
    set_conversation_scope,
)
from services.harness_config import active_harness_config
from services.idempotency import replay, save_response
from services.model_authorization import authorized_model_rows, resolve_authorized_model


class ConversationService:
    """Service for conversation CRUD, messaging, and clarification lifecycle.

    Mirrors the anspire ``Service`` convention: stateless business logic
    layered on top of a SQLAlchemy ``AsyncSession``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------ utils

    async def _conversation_out(
        self, principal: Principal, item: Conversation
    ) -> ConversationOut:
        project_id = await self._session.scalar(
            select(ProjectConversation.project_id).where(
                ProjectConversation.conversation_id == item.id
            )
        )
        return ConversationOut(
            id=item.id,
            title=item.title,
            organization_unit_id=item.organization_unit_id,
            organization_scope=await scope_out(self._session, principal, item),
            project_id=project_id,
            selected_model_id=item.selected_model_id,
            status=item.status,
            pinned_at=item.pinned_at,
            archived_at=item.archived_at,
            last_message_at=item.last_message_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    async def _owned_conversation(
        self,
        principal: Principal,
        conversation_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> Conversation:
        item = await conversation_repo.find_owned(
            self._session, principal, conversation_id, lock=lock
        )
        if item is None:
            raise AppError(404, "conversation_not_found", "会话不存在")
        await normalize_scope(
            self._session, principal, await persisted_scope(self._session, item)
        )
        return item

    # ---------------------------------------------------------------- queries

    async def list_conversations(
        self,
        principal: Principal,
        *,
        cursor: str | None = None,
        limit: int = 50,
        project_id: uuid.UUID | None = None,
        placement: Literal["unassigned", "project", "all"] = "all",
        include_archived: bool = False,
    ) -> Page:
        if project_id and placement == "unassigned":
            raise AppError(
                422, "conversation_placement_conflict", "项目筛选不能与未归属筛选同时使用"
            )
        cursor_id = decode_cursor(cursor)
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
        result = await self._session.scalars(
            statement.order_by(Conversation.id.desc()).limit(limit + 1)
        )
        rows = result.all()
        next_cursor = encode_cursor(rows[limit - 1].id) if len(rows) > limit else None
        visible = []
        for item in rows[:limit]:
            try:
                await normalize_scope(
                    self._session,
                    principal,
                    await persisted_scope(self._session, item),
                )
            except AppError:
                continue
            visible.append(await self._conversation_out(principal, item))
        return Page(items=visible, next_cursor=next_cursor)

    async def get_conversation(
        self,
        principal: Principal,
        conversation_id: uuid.UUID,
    ) -> ConversationOut:
        return await self._conversation_out(
            principal, await self._owned_conversation(principal, conversation_id)
        )

    async def list_messages(
        self,
        principal: Principal,
        conversation_id: uuid.UUID,
        *,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> Page:
        await self._owned_conversation(principal, conversation_id)
        rows = await message_repo.list_by_conversation(
            self._session,
            conversation_id,
            after_sequence=after_sequence,
            limit=limit,
        )
        next_cursor = str(rows[limit - 1].sequence) if len(rows) > limit else None
        return Page(
            items=[MessageOut.model_validate(item) for item in rows[:limit]],
            next_cursor=next_cursor,
        )

    async def get_message(
        self,
        principal: Principal,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
    ) -> MessageOut:
        await self._owned_conversation(principal, conversation_id)
        item = await message_repo.find_by_id(
            self._session, message_id, conversation_id=conversation_id
        )
        if item is None:
            raise AppError(404, "message_not_found", "消息不存在")
        return MessageOut.model_validate(item)

    async def get_message_evidence(
        self,
        principal: Principal,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
    ) -> list[MessageEvidenceOut]:
        await self._owned_conversation(principal, conversation_id)
        message = await message_repo.find_by_id(
            self._session, message_id, conversation_id=conversation_id
        )
        if message is None:
            raise AppError(404, "message_not_found", "消息不存在")
        result = await self._session.scalars(
            select(MessageEvidence)
            .where(MessageEvidence.message_id == message.id)
            .order_by(MessageEvidence.created_at, MessageEvidence.id)
        )
        rows = result.all()
        return [MessageEvidenceOut.model_validate(row) for row in rows]

    # --------------------------------------------------------------- mutations

    async def create_conversation(
        self,
        payload: ConversationCreate,
        request: Request,
        principal: Principal,
    ) -> ConversationOut | tuple[int, dict[str, Any]]:
        previous = await replay(self._session, request, principal, payload)
        if previous:
            return previous
        project = None
        if payload.project_id:
            project = await project_repo.find_owned_active(
                self._session, principal, payload.project_id
            )
            if project is None:
                raise AppError(404, "project_not_found", "项目不存在")
            await assert_org_scope(self._session, principal, project.organization_unit_id)
        requested_scope = payload.organization_scope
        if requested_scope is None:
            if "organization_unit_id" in payload.model_fields_set:
                requested_scope = legacy_scope(payload.organization_unit_id)
            elif project and project.organization_unit_id:
                requested_scope = legacy_scope(project.organization_unit_id)
            else:
                requested_scope = OrganizationScopeInput(
                    mode="all_authorized", organization_unit_ids=[]
                )
        normalized_scope, _ = await normalize_scope(
            self._session, principal, requested_scope
        )
        if payload.model_id:
            selected_model_id = await resolve_authorized_model(
                self._session, principal.enterprise_id, payload.model_id
            )
        else:
            model_rows = await authorized_model_rows(
                self._session, principal.enterprise_id
            )
            default_model = next((row for row in model_rows if row.is_default), None)
            selected_model_id = default_model or (model_rows[0] if model_rows else None)
            selected_model_id = (
                selected_model_id.model_id if selected_model_id else None
            )
        item = Conversation(
            enterprise_id=principal.enterprise_id,
            owner_user_id=principal.user.id,
            organization_unit_id=None,
            scope_mode=normalized_scope.mode,
            selected_model_id=selected_model_id,
            title=payload.title,
        )
        self._session.add(item)
        await self._session.flush()
        await set_conversation_scope(self._session, item, normalized_scope)
        if project:
            self._session.add(
                ProjectConversation(project_id=project.id, conversation_id=item.id)
            )
        output = await self._conversation_out(principal, item)
        await record_audit(
            self._session,
            request,
            "conversation.created",
            actor=principal.user,
            session=principal.session,
            target_type="conversation",
            target_id=item.id,
            metadata={
                "project_id": str(project.id) if project else None,
                "model_id": selected_model_id,
            },
        )
        await save_response(self._session, request, principal, payload, 201, output)
        await self._session.commit()
        return output

    async def update_conversation(
        self,
        conversation_id: uuid.UUID,
        payload: ConversationUpdate,
        request: Request,
        principal: Principal,
    ) -> ConversationOut:
        item = await self._owned_conversation(principal, conversation_id)
        changes = payload.model_dump(exclude_unset=True)
        requested_model_id = changes.pop("model_id", None)
        requested_scope = changes.pop("organization_scope", None)
        if "organization_unit_id" in changes:
            requested_scope = legacy_scope(changes.pop("organization_unit_id"))
        if requested_scope is not None:
            if isinstance(requested_scope, dict):
                requested_scope = OrganizationScopeInput.model_validate(requested_scope)
            normalized_scope, _ = await normalize_scope(
                self._session, principal, requested_scope
            )
            await set_conversation_scope(self._session, item, normalized_scope)
        if requested_model_id is not None:
            item.selected_model_id = await resolve_authorized_model(
                self._session, principal.enterprise_id, requested_model_id
            )
        for key, value in changes.items():
            setattr(item, key, value)
        if changes.get("status") == "archived":
            item.archived_at = utc_now()
        elif changes.get("status") == "active":
            item.archived_at = None
        await record_audit(
            self._session,
            request,
            "conversation.updated",
            actor=principal.user,
            session=principal.session,
            target_type="conversation",
            target_id=item.id,
            metadata={
                "fields": sorted(changes),
                "scope_updated": requested_scope is not None,
                "model_updated": requested_model_id is not None,
            },
        )
        await self._session.commit()
        await self._session.refresh(item)
        return await self._conversation_out(principal, item)

    async def update_conversation_project(
        self,
        conversation_id: uuid.UUID,
        payload: ConversationProjectUpdate,
        request: Request,
        principal: Principal,
    ) -> ConversationOut:
        item = await self._owned_conversation(principal, conversation_id, lock=True)
        previous_project_id = await self._session.scalar(
            select(ProjectConversation.project_id).where(
                ProjectConversation.conversation_id == item.id
            )
        )
        project = None
        if payload.project_id is not None:
            project = await project_repo.find_owned_active(
                self._session, principal, payload.project_id
            )
            if project is None:
                raise AppError(404, "project_not_found", "项目不存在")
        await self._session.execute(
            delete(ProjectConversation).where(
                ProjectConversation.conversation_id == item.id
            )
        )
        if project is not None:
            self._session.add(
                ProjectConversation(project_id=project.id, conversation_id=item.id)
            )
        await record_audit(
            self._session,
            request,
            "conversation.project_updated",
            actor=principal.user,
            session=principal.session,
            target_type="conversation",
            target_id=item.id,
            metadata={
                "previous_project_id": (
                    str(previous_project_id) if previous_project_id else None
                ),
                "project_id": str(project.id) if project else None,
            },
        )
        await self._session.commit()
        await self._session.refresh(item)
        return await self._conversation_out(principal, item)

    async def archive_conversation(
        self,
        conversation_id: uuid.UUID,
        request: Request,
        principal: Principal,
    ) -> None:
        item = await self._owned_conversation(principal, conversation_id)
        item.archived_at = utc_now()
        item.status = "archived"
        await record_audit(
            self._session,
            request,
            "conversation.archived",
            actor=principal.user,
            session=principal.session,
            target_type="conversation",
            target_id=item.id,
        )
        await self._session.commit()

    async def pin_conversation(
        self,
        conversation_id: uuid.UUID,
        request: Request,
        principal: Principal,
    ) -> ConversationOut:
        item = await self._owned_conversation(principal, conversation_id)
        item.pinned_at = utc_now()
        await record_audit(
            self._session,
            request,
            "conversation.pinned",
            actor=principal.user,
            session=principal.session,
            target_type="conversation",
            target_id=item.id,
        )
        await self._session.commit()
        await self._session.refresh(item)
        return await self._conversation_out(principal, item)

    async def unpin_conversation(
        self,
        conversation_id: uuid.UUID,
        request: Request,
        principal: Principal,
    ) -> ConversationOut:
        item = await self._owned_conversation(principal, conversation_id)
        item.pinned_at = None
        await record_audit(
            self._session,
            request,
            "conversation.unpinned",
            actor=principal.user,
            session=principal.session,
            target_type="conversation",
            target_id=item.id,
        )
        await self._session.commit()
        await self._session.refresh(item)
        return await self._conversation_out(principal, item)

    async def create_message(
        self,
        conversation_id: uuid.UUID,
        payload: MessageCreate,
        request: Request,
        principal: Principal,
    ) -> MessageOut | tuple[int, dict[str, Any]]:
        previous = await replay(self._session, request, principal, payload)
        if previous:
            return previous
        conversation = await self._owned_conversation(
            principal, conversation_id, lock=True
        )
        if conversation.archived_at:
            raise AppError(409, "conversation_archived", "已归档会话不能继续发送消息")
        if payload.file_ids:
            raise AppError(410, "file_upload_disabled", "当前阶段不支持在会话中使用文件")
        current_scope = await persisted_scope(self._session, conversation)
        requested_scope = payload.organization_scope or current_scope
        normalized_scope, resolved_scope_ids = await normalize_scope(
            self._session, principal, requested_scope
        )
        active_harness = await active_harness_config(
            self._session, principal.enterprise_id
        )
        requested_model_id = await resolve_authorized_model(
            self._session,
            principal.enterprise_id,
            payload.model_id or conversation.selected_model_id,
        )
        conversation.selected_model_id = requested_model_id
        sequence = (
            await self._session.scalar(
                select(func.coalesce(func.max(Message.sequence), 0)).where(
                    Message.conversation_id == conversation.id
                )
            )
            or 0
        ) + 1
        if scope_changed(current_scope, normalized_scope):
            scope_event = Message(
                conversation_id=conversation.id,
                role="system",
                content=(
                    "查询范围已更新为全部授权事业部"
                    if normalized_scope.mode == "all_authorized"
                    else f"查询范围已更新为 {len(resolved_scope_ids)} 个事业部"
                ),
                content_json={
                    "event": "organization_scope_changed",
                    "organization_scope": normalized_scope.model_dump(mode="json"),
                    "resolved_organization_unit_ids": [
                        str(item) for item in resolved_scope_ids
                    ],
                },
                sequence=sequence,
                status="completed",
            )
            self._session.add(scope_event)
            sequence += 1
            await set_conversation_scope(self._session, conversation, normalized_scope)
        message_scope_snapshot = scope_snapshot(normalized_scope, resolved_scope_ids)
        message = Message(
            conversation_id=conversation.id,
            author_user_id=principal.user.id,
            role="user",
            content=payload.content,
            content_json={"organization_scope_snapshot": message_scope_snapshot},
            requested_model_id=requested_model_id,
            sequence=sequence,
            status="completed",
        )
        self._session.add(message)
        await self._session.flush()
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content="",
            content_json={},
            requested_model_id=requested_model_id,
            sequence=sequence + 1,
            status="queued",
        )
        self._session.add(assistant_message)
        await self._session.flush()
        job = Job(
            enterprise_id=principal.enterprise_id,
            created_by_user_id=principal.user.id,
            harness_version_id=active_harness.id,
            job_type="assistant_response",
            payload_json={
                "conversation_id": str(conversation.id),
                "message_id": str(message.id),
                "assistant_message_id": str(assistant_message.id),
                "organization_scope": normalized_scope.model_dump(mode="json"),
                "harness_version_id": str(active_harness.id),
                "model_id": requested_model_id,
            },
            scope_snapshot_json=message_scope_snapshot,
            status="queued",
            max_attempts=get_settings().worker_job_max_attempts,
        )
        await job_repo.save(self._session, job)
        conversation.last_message_at = utc_now()
        await self._session.flush()
        output = MessageOut.model_validate(message)
        await record_audit(
            self._session,
            request,
            "message.created",
            actor=principal.user,
            session=principal.session,
            target_type="message",
            target_id=message.id,
            metadata={
                "conversation_id": str(conversation.id),
                "job_id": str(job.id),
                "assistant_message_id": str(assistant_message.id),
                "scope_mode": normalized_scope.mode,
                "scope_count": len(resolved_scope_ids),
                "harness_version": active_harness.version,
                "model_id": requested_model_id,
            },
        )
        await save_response(self._session, request, principal, payload, 202, output)
        # NOTIFY worker 有新 job（与 commit 在同一事务内）
        await self._session.execute(text("NOTIFY new_job"))
        await self._session.commit()
        return output

    async def resolve_clarification(
        self,
        conversation_id: uuid.UUID,
        clarification_id: uuid.UUID,
        payload: ClarificationResolve,
        request: Request,
        principal: Principal,
    ) -> ClarificationOut:
        conversation = await self._owned_conversation(
            principal, conversation_id, lock=True
        )
        clarification = await self._session.scalar(
            select(Clarification)
            .where(
                Clarification.id == clarification_id,
                Clarification.conversation_id == conversation.id,
            )
            .with_for_update()
        )
        if clarification is None:
            raise AppError(404, "clarification_not_found", "范围确认不存在")
        if clarification.status != "pending":
            raise AppError(409, "clarification_resolved", "该范围确认已经处理")
        clarification.status = "resolved"
        option = next(
            (
                item
                for item in clarification.options_json
                if isinstance(item, dict) and str(item.get("value")) == payload.value
            ),
            None,
        )
        if option is None:
            raise AppError(
                422, "clarification_option_invalid", "请选择系统提供的有效查询范围"
            )
        try:
            selected_organization_id = uuid.UUID(payload.value)
        except ValueError as exc:
            raise AppError(
                422, "clarification_option_invalid", "查询范围格式无效"
            ) from exc
        await assert_org_scope(self._session, principal, selected_organization_id)
        clarification.selected_value = payload.value
        clarification.resolved_by_user_id = principal.user.id
        clarification.resolved_at = utc_now()
        original_message = await self._session.get(Message, clarification.message_id)
        original_question = original_message.content if original_message else ""
        current_scope = await persisted_scope(self._session, conversation)
        if option.get("action") == "add" and current_scope.mode == "selected":
            requested_scope = OrganizationScopeInput(
                mode="selected",
                organization_unit_ids=list(
                    dict.fromkeys(
                        [*current_scope.organization_unit_ids, selected_organization_id]
                    )
                ),
            )
        else:
            requested_scope = OrganizationScopeInput(
                mode="selected", organization_unit_ids=[selected_organization_id]
            )
        normalized_scope, resolved_scope_ids = await normalize_scope(
            self._session, principal, requested_scope
        )
        sequence = (
            await self._session.scalar(
                select(func.coalesce(func.max(Message.sequence), 0)).where(
                    Message.conversation_id == conversation.id
                )
            )
            or 0
        ) + 1
        if scope_changed(current_scope, normalized_scope):
            self._session.add(
                Message(
                    conversation_id=conversation.id,
                    role="system",
                    content=(
                        "查询范围已更新为全部授权事业部"
                        if normalized_scope.mode == "all_authorized"
                        else f"查询范围已更新为 {len(resolved_scope_ids)} 个事业部"
                    ),
                    content_json={
                        "event": "organization_scope_changed",
                        "organization_scope": normalized_scope.model_dump(mode="json"),
                        "resolved_organization_unit_ids": [
                            str(item) for item in resolved_scope_ids
                        ],
                    },
                    sequence=sequence,
                    status="completed",
                )
            )
            sequence += 1
            await set_conversation_scope(self._session, conversation, normalized_scope)
        message_scope_snapshot = scope_snapshot(normalized_scope, resolved_scope_ids)
        user_message = Message(
            conversation_id=conversation.id,
            author_user_id=principal.user.id,
            role="user",
            content=(
                f"{original_question}\n\n已确认查询范围：{option.get('label', payload.value)}"
                if original_question
                else payload.value
            ),
            content_json={
                "clarification_id": str(clarification.id),
                "selected_value": payload.value,
                "original_message_id": str(clarification.message_id),
                "organization_scope_snapshot": message_scope_snapshot,
            },
            sequence=sequence,
            status="completed",
        )
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content="",
            content_json={},
            sequence=sequence + 1,
            status="queued",
        )
        self._session.add_all([user_message, assistant_message])
        await self._session.flush()
        source_job = next(
            (
                item
                for item in await job_repo.list_by_conversation(
                    self._session, principal.enterprise_id, limit=100
                )
                if str(item.payload_json.get("message_id"))
                == str(clarification.message_id)
            ),
            None,
        )
        harness_version = (
            await self._session.get(HarnessConfigVersion, source_job.harness_version_id)
            if source_job and source_job.harness_version_id
            else await active_harness_config(self._session, principal.enterprise_id)
        )
        requested_model_id = await resolve_authorized_model(
            self._session,
            principal.enterprise_id,
            (
                str(source_job.payload_json.get("model_id"))
                if source_job and source_job.payload_json.get("model_id")
                else conversation.selected_model_id
            ),
        )
        conversation.selected_model_id = requested_model_id
        user_message.requested_model_id = requested_model_id
        assistant_message.requested_model_id = requested_model_id
        await job_repo.save(
            self._session,
            Job(
                enterprise_id=principal.enterprise_id,
                created_by_user_id=principal.user.id,
                harness_version_id=harness_version.id,
                job_type="assistant_response",
                payload_json={
                    "conversation_id": str(conversation.id),
                    "message_id": str(user_message.id),
                    "assistant_message_id": str(assistant_message.id),
                    "clarification_id": str(clarification.id),
                    "organization_scope": normalized_scope.model_dump(mode="json"),
                    "harness_version_id": str(harness_version.id),
                    "model_id": requested_model_id,
                },
                scope_snapshot_json=message_scope_snapshot,
                status="queued",
                max_attempts=get_settings().worker_job_max_attempts,
            ),
        )
        conversation.last_message_at = utc_now()
        await record_audit(
            self._session,
            request,
            "clarification.resolved",
            actor=principal.user,
            session=principal.session,
            target_type="clarification",
            target_id=clarification.id,
        )
        # NOTIFY worker 有新 job（与 commit 在同一事务内）
        await self._session.execute(text("NOTIFY new_job"))
        await self._session.commit()
        return ClarificationOut.model_validate(clarification)

    async def share_message_diagnostic(
        self,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        request: Request,
        principal: Principal,
    ) -> DiagnosticShareOut:
        conversation = await self._owned_conversation(principal, conversation_id)
        message = await self._session.scalar(
            select(Message).where(
                Message.id == message_id,
                Message.conversation_id == conversation.id,
                Message.role == "assistant",
            )
        )
        if message is None:
            raise AppError(404, "message_not_found", "回答不存在")
        expires_at = utc_now() + timedelta(hours=24)
        grant = await self._session.scalar(
            select(HarnessDiagnosticGrant)
            .where(HarnessDiagnosticGrant.message_id == message.id)
            .with_for_update()
        )
        if grant is None:
            grant = HarnessDiagnosticGrant(
                enterprise_id=principal.enterprise_id,
                conversation_id=conversation.id,
                message_id=message.id,
                granted_by_user_id=principal.user.id,
                expires_at=expires_at,
            )
            self._session.add(grant)
        else:
            grant.expires_at = expires_at
            grant.revoked_at = None
        await record_audit(
            self._session,
            request,
            "harness.diagnostic_shared",
            actor=principal.user,
            session=principal.session,
            target_type="message",
            target_id=message.id,
            metadata={"expires_at": expires_at.isoformat()},
        )
        await self._session.commit()
        return DiagnosticShareOut(
            message_id=message.id,
            expires_at=grant.expires_at,
            revoked_at=grant.revoked_at,
        )

    async def revoke_message_diagnostic(
        self,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        request: Request,
        principal: Principal,
    ) -> None:
        conversation = await self._owned_conversation(principal, conversation_id)
        grant = await self._session.scalar(
            select(HarnessDiagnosticGrant).where(
                HarnessDiagnosticGrant.message_id == message_id,
                HarnessDiagnosticGrant.conversation_id == conversation.id,
                HarnessDiagnosticGrant.granted_by_user_id == principal.user.id,
            )
        )
        if grant is None:
            raise AppError(404, "diagnostic_share_not_found", "诊断共享不存在")
        grant.revoked_at = utc_now()
        await record_audit(
            self._session,
            request,
            "harness.diagnostic_revoked",
            actor=principal.user,
            session=principal.session,
            target_type="message",
            target_id=message_id,
        )
        await self._session.commit()

    # ----------------------------------------------- SSE stream batch helper

    @staticmethod
    async def fetch_stream_batch(
        session: AsyncSession,
        conversation_id: uuid.UUID,
        enterprise_id: uuid.UUID,
        owner_user_id: uuid.UUID,
        cursor: int = 0,
    ) -> tuple[Conversation | None, list[Message]]:
        """Fetch one SSE polling batch for ``stream_conversation``.

        Returns ``(conversation, messages)`` where ``conversation`` is ``None``
        if the conversation vanished (e.g. archived by another session). The
        caller is responsible for emitting SSE events, deduping via
        ``seen_updates`` / resume markers, and advancing ``cursor``; this
        helper only performs the read queries so the router's
        ``SessionLocal()`` block can stay thin. ``cursor`` mirrors the original
        route's ``max(1, cursor)`` lower bound on ``Message.sequence``.
        """
        conversation = await conversation_repo.find_by_id_and_owner(
            session, conversation_id, enterprise_id, owner_user_id
        )
        if conversation is None:
            return None, []
        result = await session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.sequence >= max(1, cursor),
            )
            .order_by(Message.sequence)
        )
        rows = result.all()
        return conversation, list(rows)
