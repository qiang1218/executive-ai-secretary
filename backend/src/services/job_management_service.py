"""Job management service.

Follows the anspire service pattern: a class that receives the database
session in the constructor and exposes business methods. The ``/jobs`` router
delegates all job lifecycle operations (list, create, get, cancel, retry) to
:class:`JobManagementService`.
"""

from __future__ import annotations

import json
import uuid

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import Settings
from exceptions.errors import AppError
from models import Job, JobAttempt, Message
from repositories import conversation as conversation_repo
from repositories import file_asset as file_asset_repo
from repositories import job as job_repo
from repositories import message as message_repo
from repositories import report as report_repo
from repositories.audit import record_audit
from schemas import JobCreate, JobOut, Page
from services.audit_service import AuditService
from services.authz import (
    Principal,
    build_scope_snapshot,
    scope_snapshot_is_current_for_user,
)
from services.job_state import JobStateService
from core.security import utc_now

EXTERNAL_JOB_TYPES = {"report.generate", "file.extract"}


class JobManagementService:
    """Service for managing the job lifecycle (list/create/get/cancel/retry).

    Mirrors the anspire ``Service`` convention: stateless business logic
    layered on top of a SQLAlchemy ``AsyncSession``.
    """

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def visible_job(
        self,
        principal: Principal,
        job_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> Job:
        """Return a job owned by the principal, enforcing scope-snapshot validity."""
        item = await job_repo.find_owned(self._session, principal, job_id, lock=lock)
        if item is None:
            raise AppError(404, "job_not_found", "任务不存在")
        if not await scope_snapshot_is_current_for_user(
            self._session, principal.user, item.scope_snapshot_json
        ):
            raise AppError(403, "data_scope_forbidden", "任务的事业部授权已失效")
        return item

    async def list_jobs(self, principal: Principal) -> Page:
        """List the principal's jobs, filtered by current scope validity."""
        rows = await job_repo.list_by_owner(self._session, principal, limit=100)
        visible = [
            item
            for item in rows
            if await scope_snapshot_is_current_for_user(
                self._session, principal.user, item.scope_snapshot_json
            )
        ]
        return Page(items=[JobOut.model_validate(item) for item in visible])

    async def create_job(
        self,
        payload: JobCreate,
        request: Request,
        principal: Principal,
    ) -> JobOut:
        """Validate, resolve resources, persist a new job, and record audit."""
        if payload.job_type not in EXTERNAL_JOB_TYPES:
            raise AppError(403, "job_type_forbidden", "当前角色不能创建此类任务")
        if len(json.dumps(payload.payload, ensure_ascii=False)) > 100_000:
            raise AppError(413, "job_payload_too_large", "任务参数过大")
        try:
            if payload.job_type == "report.generate":
                resource_id = uuid.UUID(str(payload.payload.get("report_id", "")))
                report = await report_repo.find_owned(self._session, principal, resource_id)
                if report is None:
                    raise AppError(404, "report_not_found", "简报不存在")
                snapshot = await build_scope_snapshot(
                    self._session, principal, report.organization_unit_id
                )
            else:
                resource_id = uuid.UUID(str(payload.payload.get("file_id", "")))
                file_asset = await file_asset_repo.find_owned(
                    self._session, principal, resource_id
                )
                if file_asset is None:
                    raise AppError(404, "file_not_found", "文件不存在")
                snapshot = await build_scope_snapshot(self._session, principal)
        except ValueError as exc:
            raise AppError(422, "invalid_job_resource", "任务必须关联有效资源") from exc
        item = Job(
            enterprise_id=principal.enterprise_id,
            created_by_user_id=principal.user.id,
            job_type=payload.job_type,
            payload_json=payload.payload,
            scope_snapshot_json=snapshot,
            scheduled_at=payload.scheduled_at,
            status="queued",
            max_attempts=self._settings.worker_job_max_attempts,
        )
        await job_repo.save(self._session, item)
        await record_audit(
            self._session,
            request,
            "job.created",
            actor=principal.user,
            session=principal.session,
            target_type="job",
            target_id=item.id,
            metadata={"job_type": item.job_type},
        )
        await self._session.commit()
        return JobOut.model_validate(item)

    async def get_job(self, principal: Principal, job_id: uuid.UUID) -> JobOut:
        """Return a single job owned by the principal."""
        return JobOut.model_validate(await self.visible_job(principal, job_id))

    async def cancel_job(
        self,
        job_id: uuid.UUID,
        request: Request,
        principal: Principal,
        audit: AuditService,
    ) -> JobOut:
        """Cancel a queued/running job, clean up leases/attempts, and record audit."""
        item = await self.visible_job(principal, job_id, lock=True)
        if item.status not in {"queued", "running"}:
            raise AppError(409, "job_not_cancelable", "当前任务状态不能取消")
        active_lease_token = item.lease_token
        item.status = "canceled"
        item.completed_at = utc_now()
        item.lease_owner = None
        item.lease_token = None
        item.lease_expires_at = None
        item.heartbeat_at = None
        attempt_statement = select(JobAttempt).where(
            JobAttempt.job_id == item.id,
            JobAttempt.status == "running",
        )
        if active_lease_token:
            attempt_statement = attempt_statement.where(
                JobAttempt.lease_token == active_lease_token
            )
        result = await self._session.scalars(attempt_statement)
        for attempt in result.all():
            attempt.status = "canceled"
            attempt.completed_at = item.completed_at
            attempt.error_message = "Canceled by user"
        await JobStateService(self._session).close_assistant_placeholder(
            item, status="failed", content="请求已取消"
        )
        await audit.record(
            request,
            "job.canceled",
            actor=principal.user,
            session=principal.session,
            target_type="job",
            target_id=item.id,
        )
        await self._session.commit()
        await self._session.refresh(item)
        return JobOut.model_validate(item)

    async def retry_job(
        self,
        job_id: uuid.UUID,
        request: Request,
        principal: Principal,
    ) -> JobOut:
        """Retry a failed/canceled assistant_response job by creating a new one."""
        previous = await self.visible_job(principal, job_id, lock=True)
        if previous.job_type != "assistant_response":
            raise AppError(409, "job_not_retryable", "仅支持重试问答任务")
        if previous.status not in {"failed", "canceled"}:
            raise AppError(409, "job_not_retryable", "当前任务状态不能重试")
        try:
            conversation_id = uuid.UUID(str(previous.payload_json["conversation_id"]))
            message_id = uuid.UUID(str(previous.payload_json["message_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise AppError(409, "job_not_retryable", "原任务缺少可重试的会话信息") from exc
        conversation = await conversation_repo.find_owned_active(
            self._session, principal, conversation_id
        )
        source_message = await message_repo.find_by_id(
            self._session,
            message_id,
            conversation_id=conversation_id,
        )
        # 原查询额外过滤 Message.role == "user"，find_by_id 不带 role 过滤，
        # 这里补做角色校验以保持原有行为。
        if source_message is not None and source_message.role != "user":
            source_message = None
        if conversation is None or source_message is None:
            raise AppError(409, "job_not_retryable", "原会话已不可继续")
        sequence = (
            await self._session.scalar(
                select(func.coalesce(func.max(Message.sequence), 0)).where(
                    Message.conversation_id == conversation.id
                )
            )
            or 0
        ) + 1
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content="",
            content_json={"retry_of_job_id": str(previous.id)},
            sequence=sequence,
            status="queued",
            requested_model_id=(
                str(previous.payload_json.get("model_id"))
                if previous.payload_json.get("model_id")
                else source_message.requested_model_id
            ),
        )
        self._session.add(assistant_message)
        await self._session.flush()
        payload = dict(previous.payload_json)
        payload["assistant_message_id"] = str(assistant_message.id)
        payload["retry_of_job_id"] = str(previous.id)
        retried = Job(
            enterprise_id=principal.enterprise_id,
            created_by_user_id=principal.user.id,
            harness_version_id=previous.harness_version_id,
            job_type="assistant_response",
            payload_json=payload,
            # A retry is the same question under the same authority and Harness
            # snapshot. Re-resolving current conversation state would change history.
            scope_snapshot_json=dict(previous.scope_snapshot_json),
            status="queued",
            max_attempts=self._settings.worker_job_max_attempts,
        )
        await job_repo.save(self._session, retried)
        conversation.last_message_at = utc_now()
        await self._session.flush()
        await record_audit(
            self._session,
            request,
            "job.retried",
            actor=principal.user,
            session=principal.session,
            target_type="job",
            target_id=retried.id,
            metadata={"retry_of_job_id": str(previous.id)},
        )
        await self._session.commit()
        await self._session.refresh(retried)
        return JobOut.model_validate(retried)
