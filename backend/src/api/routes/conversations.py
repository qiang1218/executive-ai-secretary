from __future__ import annotations

import asyncio
import json
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import ConversationServiceDep, ExecutivePrincipalDep
from db.session import AsyncSessionLocal, get_db_async
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
    Page,
)
from services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=Page)
async def list_conversations(
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    project_id: uuid.UUID | None = None,
    placement: Literal["unassigned", "project", "all"] = "all",
    include_archived: bool = False,
) -> Page:
    return await service.list_conversations(
        principal,
        cursor=cursor,
        limit=limit,
        project_id=project_id,
        placement=placement,
        include_archived=include_archived,
    )


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
):
    result = await service.create_conversation(payload, request, principal)
    if isinstance(result, tuple):
        return JSONResponse(status_code=result[0], content=result[1])
    return result


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: uuid.UUID,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
) -> ConversationOut:
    return await service.get_conversation(principal, conversation_id)


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
) -> ConversationOut:
    return await service.update_conversation(conversation_id, payload, request, principal)


@router.patch("/{conversation_id}/project", response_model=ConversationOut)
async def update_conversation_project(
    conversation_id: uuid.UUID,
    payload: ConversationProjectUpdate,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
) -> ConversationOut:
    return await service.update_conversation_project(
        conversation_id, payload, request, principal
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_conversation(
    conversation_id: uuid.UUID,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
):
    await service.archive_conversation(conversation_id, request, principal)


@router.post("/{conversation_id}/pin", response_model=ConversationOut)
async def pin_conversation(
    conversation_id: uuid.UUID,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
) -> ConversationOut:
    return await service.pin_conversation(conversation_id, request, principal)


@router.delete("/{conversation_id}/pin", response_model=ConversationOut)
async def unpin_conversation(
    conversation_id: uuid.UUID,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
) -> ConversationOut:
    return await service.unpin_conversation(conversation_id, request, principal)


@router.get("/{conversation_id}/messages", response_model=Page)
async def list_messages(
    conversation_id: uuid.UUID,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
    after_sequence: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> Page:
    return await service.list_messages(
        principal,
        conversation_id,
        after_sequence=after_sequence,
        limit=limit,
    )


@router.get(
    "/{conversation_id}/messages/{message_id}",
    response_model=MessageOut,
    summary="获取单条消息（轻量 polling）",
)
async def get_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
) -> MessageOut:
    return await service.get_message(principal, conversation_id, message_id)


@router.get("/{conversation_id}/stream")
async def stream_conversation(
    conversation_id: uuid.UUID,
    request: Request,
    principal: ExecutivePrincipalDep,
    db: Annotated[AsyncSession, Depends(get_db_async)],
    after_sequence: int = Query(default=0, ge=0),
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    # Initial ownership check on the request-scoped session; the long-lived
    # polling loop below uses its own ``AsyncSessionLocal()`` sessions.
    await ConversationService(db)._owned_conversation(principal, conversation_id)
    resume_sequence = 0
    resume_updated_ms = 0
    try:
        if last_event_id and ":" in last_event_id:
            resume_sequence_text, resume_updated_text = last_event_id.split(":", 1)
            resume_sequence = int(resume_sequence_text)
            resume_updated_ms = int(resume_updated_text)
        elif last_event_id:
            resume_sequence = int(last_event_id)
    except ValueError:
        resume_sequence = 0
        resume_updated_ms = 0
    cursor = max(after_sequence, resume_sequence)
    enterprise_id = principal.enterprise_id
    owner_user_id = principal.user.id

    async def events():
        nonlocal cursor
        seen_updates: dict[uuid.UUID, str] = {}
        idle_cycles = 0
        while not await request.is_disconnected():
            async with AsyncSessionLocal() as stream_db:
                conversation, rows = await ConversationService.fetch_stream_batch(
                    stream_db,
                    conversation_id,
                    enterprise_id,
                    owner_user_id,
                    cursor=cursor,
                )
                if conversation is None:
                    yield 'event: error\ndata: {"code":"conversation_not_found"}\n\n'
                    return
                emitted = False
                for item in rows:
                    updated_marker = item.updated_at.isoformat()
                    updated_ms = int(item.updated_at.timestamp() * 1000)
                    is_resumed_item = (
                        item.sequence == resume_sequence
                        and updated_ms <= resume_updated_ms
                    )
                    if (
                        item.sequence < cursor
                        or is_resumed_item
                        or seen_updates.get(item.id) == updated_marker
                    ):
                        continue
                    seen_updates[item.id] = updated_marker
                    cursor = item.sequence
                    emitted = True
                    payload = MessageOut.model_validate(item).model_dump(mode="json")
                    yield (
                        f"id: {cursor}:{updated_ms}\nevent: message\ndata: "
                        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                        + "\n\n"
                    )
            if emitted:
                idle_cycles = 0
            else:
                idle_cycles += 1
                if idle_cycles % 20 == 0:
                    yield "event: heartbeat\ndata: {}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/{conversation_id}/clarifications/{clarification_id}",
    response_model=ClarificationOut,
)
async def resolve_clarification(
    conversation_id: uuid.UUID,
    clarification_id: uuid.UUID,
    payload: ClarificationResolve,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
) -> ClarificationOut:
    return await service.resolve_clarification(
        conversation_id, clarification_id, payload, request, principal
    )


@router.get(
    "/{conversation_id}/messages/{message_id}/evidence",
    response_model=list[MessageEvidenceOut],
)
async def get_message_evidence(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
) -> list[MessageEvidenceOut]:
    return await service.get_message_evidence(principal, conversation_id, message_id)


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
):
    result = await service.create_message(conversation_id, payload, request, principal)
    if isinstance(result, tuple):
        return JSONResponse(status_code=result[0], content=result[1])
    return result


@router.post(
    "/{conversation_id}/messages/{message_id}/diagnostic-share",
    response_model=DiagnosticShareOut,
)
async def share_message_diagnostic(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
) -> DiagnosticShareOut:
    return await service.share_message_diagnostic(
        conversation_id, message_id, request, principal
    )


@router.delete(
    "/{conversation_id}/messages/{message_id}/diagnostic-share",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_message_diagnostic(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
):
    await service.revoke_message_diagnostic(
        conversation_id, message_id, request, principal
    )
