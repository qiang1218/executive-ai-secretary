"""站内通知服务。

负责通知的查询、未读计数、批量标记已读、手动触发每日摘要入队。
通知的创建由 :mod:`services.email_sync_service`（email_urgent）和
:mod:`services.daily_digest_service`（email_digest/daily_brief）负责。
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import Settings
from core.security import utc_now
from exceptions.errors import AppError
from models import Job, Notification
from repositories import notification as notif_repo
from schemas import (
    DigestGenerateOut,
    MarkReadRequest,
    MarkReadResult,
    NotificationOut,
    UnreadCountOut,
)
from services.authz import Principal


class NotificationService:
    """站内通知查询与已读管理。"""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def list_notifications(
        self,
        principal: Principal,
        *,
        unread_only: bool = False,
        type_filter: str | None = None,
        limit: int = 50,
    ) -> list[NotificationOut]:
        rows = await notif_repo.list_for_user(
            self._session,
            principal.user.id,
            unread_only=unread_only,
            type_filter=type_filter,
            limit=limit,
        )
        # ORM 返回的 id/user_id 是 UUID，NotificationOut 用 str 表示。
        # 使用 from_attributes 显式映射，避免 model_validate 默认 strict 校验失败。
        return [
            NotificationOut.model_validate(
                {
                    "id": str(item.id),
                    "user_id": str(item.user_id),
                    "type": item.type,
                    "title": item.title,
                    "body": item.body,
                    "importance": item.importance,
                    "is_read": item.is_read,
                    "created_at": item.created_at,
                }
            )
            for item in rows
        ]

    async def unread_count(
        self, principal: Principal
    ) -> UnreadCountOut:
        count = await notif_repo.unread_count(self._session, principal.user.id)
        return UnreadCountOut(unread=count)

    async def mark_read(
        self, principal: Principal, payload: MarkReadRequest
    ) -> MarkReadResult:
        ids: list[uuid.UUID] | None = None
        if payload.ids and not payload.all:
            try:
                ids = [uuid.UUID(x) for x in payload.ids]
            except ValueError as exc:
                raise AppError(
                    400, "notification_id_invalid", "通知 id 格式无效"
                ) from exc
        updated = await notif_repo.mark_read(
            self._session,
            principal.user.id,
            ids=ids,
            all_unread=payload.all,
        )
        await self._session.commit()
        return MarkReadResult(updated=updated)

    async def enqueue_digest(
        self, principal: Principal
    ) -> DigestGenerateOut:
        """手动触发每日邮件摘要生成 job。"""
        job = Job(
            enterprise_id=principal.enterprise_id,
            created_by_user_id=principal.user.id,
            job_type="daily_digest",
            status="queued",
            max_attempts=self._settings.worker_job_max_attempts,
            payload_json={
                "user_id": str(principal.user.id),
                "trigger_type": "manual",
            },
            scope_snapshot_json={
                "enterprise_id": str(principal.enterprise_id),
            },
            scheduled_at=utc_now(),
        )
        self._session.add(job)
        await self._session.commit()
        await self._session.refresh(job)
        return DigestGenerateOut(job_id=str(job.id), status=job.status)
