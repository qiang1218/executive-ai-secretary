"""站内通知路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from api.deps import NotificationServiceDep
from schemas import (
    DigestGenerateOut,
    MarkReadRequest,
    MarkReadResult,
    NotificationOut,
    UnreadCountOut,
)
from services.authz import Principal, get_executive_principal

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    principal: Annotated[Principal, Depends(get_executive_principal)],
    notification_service: NotificationServiceDep,
    unread_only: bool = False,
    type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[NotificationOut]:
    return await notification_service.list_notifications(
        principal,
        unread_only=unread_only,
        type_filter=type,
        limit=limit,
    )


@router.get("/unread-count", response_model=UnreadCountOut)
async def unread_count(
    principal: Annotated[Principal, Depends(get_executive_principal)],
    notification_service: NotificationServiceDep,
) -> UnreadCountOut:
    return await notification_service.unread_count(principal)


@router.post(
    "/mark-read",
    response_model=MarkReadResult,
    status_code=status.HTTP_200_OK,
)
async def mark_read(
    payload: MarkReadRequest,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    notification_service: NotificationServiceDep,
) -> MarkReadResult:
    return await notification_service.mark_read(principal, payload)


@router.post("/digest", response_model=DigestGenerateOut)
async def generate_digest(
    principal: Annotated[Principal, Depends(get_executive_principal)],
    notification_service: NotificationServiceDep,
) -> DigestGenerateOut:
    return await notification_service.enqueue_digest(principal)
