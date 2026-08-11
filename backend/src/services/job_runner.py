"""Async job runner (claim / lease / heartbeat / run / finish).

同进程内跑时优先 PostgreSQL LISTEN/NOTIFY；测试用 sqlite 时退回轮询。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Mapping
from zoneinfo import ZoneInfo

from croniter import croniter
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from configs.settings import Settings, get_settings
from core.security import utc_now
from db import SessionLocal
from models.job import Job

logger = logging.getLogger(__name__)


JobHandler = Callable[["JobRunnerContext", Job, Settings], Awaitable[dict[str, Any]]]


class JobRunnerContext:
    """Per-process context shared between the runner loop and the handlers.

    Currently holds only ``worker_id`` and a back-reference to the runner
    (so handlers may opt-in to additional services like a metrics sink or
    a logging breadcrumb).
    """

    def __init__(self, worker_id: str) -> None:
        self.worker_id = worker_id
        self.started_at = utc_now()

    def __repr__(self) -> str:  # pragma: no cover — debug only
        return f"JobRunnerContext(worker_id={self.worker_id!r})"


# --------------------------------------------------------------------------
# Default handlers
# --------------------------------------------------------------------------

async def _handle_data_sync(
    ctx: JobRunnerContext, job: Job, settings: Settings
) -> dict[str, Any]:
    """Delegate to ``services.ingestion.run_data_sync_job`` synchronously."""
    from services.ingestion import run_data_sync_job  # local import — keep package top-level clean

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, run_data_sync_job, job, settings)


async def _handle_file_extract(
    ctx: JobRunnerContext, job: Job, settings: Settings
) -> dict[str, Any]:
    """Phase-3 placeholder.

    Retained so the ``job_type`` enum can still be persisted without
    exploding the runner. When a real extractor is reintroduced, replace
    the body.
    """
    payload = dict(job.payload_json or {})
    return {
        "status": "noop",
        "reason": "file_extract handler is a placeholder; no extractor is registered",
        "payload_keys": sorted(payload.keys()),
    }


async def _handle_system_noop(
    ctx: JobRunnerContext, job: Job, settings: Settings
) -> dict[str, Any]:
    """Tear-down / wake-up only job; runs without touching external systems."""
    return {"status": "ok", "handled_at": utc_now().isoformat()}


async def _handle_email_sync(
    ctx: "JobRunnerContext", job: Job, settings: Settings
) -> dict[str, Any]:
    """邮件同步：委托 ``services.email_sync_service.run_email_sync``。"""
    from services.email_sync_service import run_email_sync

    return await run_email_sync(ctx, job, settings)


async def _handle_daily_digest(
    ctx: "JobRunnerContext", job: Job, settings: Settings
) -> dict[str, Any]:
    """每日邮件摘要：委托 ``services.daily_digest_service.run_daily_digest``。"""
    from services.daily_digest_service import run_daily_digest

    return await run_daily_digest(ctx, job, settings)


async def _handle_entity_index(
    ctx: "JobRunnerContext", job: Job, settings: Settings
) -> dict[str, Any]:
    """实体向量索引构建：委托 ``services.entity_indexer_service.run_entity_index``。"""
    from services.entity_indexer_service import run_entity_index

    return await run_entity_index(ctx, job, settings)


DEFAULT_HANDLERS: Mapping[str, JobHandler] = {
    "data.sync": _handle_data_sync,
    "file.extract": _handle_file_extract,
    "system.noop": _handle_system_noop,
    "email.sync": _handle_email_sync,
    "daily_digest": _handle_daily_digest,
    "entity.index": _handle_entity_index,
}


# --------------------------------------------------------------------------
# Lease / heartbeat primitives
# --------------------------------------------------------------------------

LEASE_DURATION = timedelta(seconds=60)


def _new_lease_token() -> str:
    return secrets.token_hex(16)


def acquire_lease(job_id: uuid.UUID, worker_id: str, *, session: Session) -> str | None:
    """Acquire / refresh a lease for ``job_id``; returns the token, or ``None`` if contended."""
    from sqlalchemy import text

    token = _new_lease_token()
    now = utc_now()
    expires = now + LEASE_DURATION

    # Raw SQL — the ORM UUID binder does not round-trip cleanly on sqlite,
    # and the column stores ``uuid.hex`` (no hyphens) so we must format
    # the bind explicitly.
    update_sql = (
        "UPDATE jobs"
        " SET lease_token = :token, lease_expires_at = :expires, heartbeat_at = :now"
        " WHERE id = :job_id AND status = 'running' AND lease_owner = :worker_id"
    )
    result = session.execute(
        text(update_sql),
        {
            "token": token,
            "expires": expires,
            "now": now,
            "job_id": job_id.hex,
            "worker_id": worker_id,
        },
    )
    session.commit()
    if getattr(result, "rowcount", 0) > 0:
        return token
    return None


def heartbeat(job_id: uuid.UUID, worker_id: str, *, session: Session) -> bool:
    """Refresh ``heartbeat_at`` for an active job owned by this worker."""
    token = acquire_lease(job_id, worker_id, session=session)
    return token is not None


def finish_success(
    job_id: uuid.UUID,
    *,
    session: Session,
    result: Mapping[str, Any] | None = None,
) -> None:
    from sqlalchemy import text

    now = utc_now()
    session.execute(
        text(
            "UPDATE jobs"
            " SET status = 'completed', completed_at = :now, result_json = :result"
            " WHERE id = :job_id"
        ),
        {"now": now, "result": json.dumps(dict(result or {})), "job_id": job_id.hex},
    )
    session.commit()


def finish_failure(
    job_id: uuid.UUID,
    *,
    session: Session,
    error_code: str,
    error_message: str,
    dead_letter: bool = False,
) -> None:
    from sqlalchemy import text

    now = utc_now()
    if dead_letter:
        update_sql = (
            "UPDATE jobs SET status = 'failed', completed_at = :now,"
            " error_code = :code, error_message = :msg,"
            " dead_lettered_at = :dead_letter_at"
            " WHERE id = :job_id"
        )
        params = {
            "now": now,
            "code": error_code[:100],
            "msg": error_message[:4096],
            "dead_letter_at": now,
            "job_id": job_id.hex,
        }
    else:
        update_sql = (
            "UPDATE jobs SET status = 'failed', completed_at = :now,"
            " error_code = :code, error_message = :msg"
            " WHERE id = :job_id"
        )
        params = {
            "now": now,
            "code": error_code[:100],
            "msg": error_message[:4096],
            "job_id": job_id.hex,
        }
    session.execute(text(update_sql), params)
    session.commit()


def requeue_expired_leases(*, session: Session) -> int:
    """Move any job whose lease has expired back into ``queued`` so the next
    claim can pick it up.  Returns the count of rows updated.
    """
    from sqlalchemy import text

    now = utc_now()
    stmt = text(
        "UPDATE jobs SET status = 'queued', lease_owner = NULL,"
        " lease_token = NULL, lease_expires_at = NULL, started_at = NULL"
        " WHERE status = 'running' AND lease_expires_at IS NOT NULL"
        "   AND lease_expires_at < :now"
    )
    result = session.execute(stmt, {"now": now})
    return getattr(result, "rowcount", 0)


# --------------------------------------------------------------------------
# Scheduled-task enqueueing
# --------------------------------------------------------------------------

def _compute_next_cron_run(
    cron_expression: str, after: datetime, timezone_name: str
) -> datetime | None:
    """根据 cron 表达式计算 ``after`` 之后的下一次执行时间（UTC）。

    返回 aware datetime；失败时返回 ``None``。
    """
    try:
        tz = ZoneInfo(timezone_name)
    except (KeyError, ValueError, LookupError):
        tz = ZoneInfo("UTC")
    localized = after.astimezone(tz) if after.tzinfo else after.replace(tzinfo=tz)
    try:
        cron = croniter(cron_expression, localized)
    except (ValueError, KeyError):
        return None
    next_local = cron.get_next(datetime)
    return next_local.astimezone(ZoneInfo("UTC"))


def enqueue_due_scheduled_tasks(session: Session) -> int:
    """把到期的 ScheduledTask 入队成 Job，推进 ``next_run_at``。

    每条到期任务：
    1. 用 ``ScheduleRun.window_key`` 去重（ISO 时间戳），同一窗口不重复入队；
    2. 创建 ``Job(type="data.sync", status="queued")``，payload 与
       ``data_source_service._enqueue_sync`` 对齐（``trigger_type="scheduled"``）；
    3. 创建 ``ScheduleRun(status="enqueued")`` 关联 task / job；
    4. 根据 cron 算出下次执行时间，UPDATE ``ScheduledTask.next_run_at`` /
       ``last_enqueued_at``。

    所有写入都在调用方的事务里完成，由调用方 commit。
    """
    from models.data_source import ScheduleRun, ScheduledTask
    from sqlalchemy import select

    now = utc_now()
    due_tasks = (
        session.scalars(
            select(ScheduledTask).where(
                ScheduledTask.is_enabled.is_(True),
                ScheduledTask.next_run_at.is_not(None),
                ScheduledTask.next_run_at <= now,
            )
        )
    ).all()

    enqueued = 0
    for task in due_tasks:
        scheduled_for = task.next_run_at
        # window_key 用 UTC ISO 时间戳，保证同一调度窗口全局唯一
        window_key = (
            scheduled_for.astimezone(ZoneInfo("UTC")).isoformat()
            if scheduled_for.tzinfo
            else scheduled_for.replace(tzinfo=ZoneInfo("UTC")).isoformat()
        )

        # 同一窗口已入队过——只推进 next_run_at，不重复入队
        existing = session.scalar(
            select(ScheduleRun).where(
                ScheduleRun.scheduled_task_id == task.id,
                ScheduleRun.window_key == window_key,
            )
        )
        if existing is not None:
            next_at = _compute_next_cron_run(
                task.cron_expression, scheduled_for, task.timezone
            )
            if next_at is not None:
                task.next_run_at = next_at
            continue

        if task.data_source_id is None and task.task_type not in (
            "email.sync",
            "daily_digest",
        ):
            logger.warning(
                "scheduled_task_skip_no_data_source task_id=%s key=%s",
                task.id,
                task.key,
            )
            continue

        next_at = _compute_next_cron_run(
            task.cron_expression, scheduled_for, task.timezone
        )
        if next_at is None:
            logger.warning(
                "scheduled_task_skip_invalid_cron task_id=%s cron=%s",
                task.id,
                task.cron_expression,
            )
            continue

        # 按 task_type 分发 job_type 与 payload；data.sync 仍走原逻辑
        if task.task_type == "email.sync":
            email_account_id = task.configuration_json.get("email_account_id")
            if not email_account_id:
                logger.warning(
                    "scheduled_task_skip_no_email_account task_id=%s key=%s",
                    task.id, task.key,
                )
                continue
            job = Job(
                enterprise_id=task.enterprise_id,
                job_type="email.sync",
                status="queued",
                max_attempts=get_settings().worker_job_max_attempts,
                payload_json={
                    "email_account_id": str(email_account_id),
                    "scheduled_task_id": str(task.id),
                    "trigger_type": "scheduled",
                },
                scope_snapshot_json={
                    "enterprise_id": str(task.enterprise_id),
                },
                scheduled_at=now,
            )
        elif task.task_type == "daily_digest":
            user_id = task.configuration_json.get("user_id")
            if not user_id:
                logger.warning(
                    "scheduled_task_skip_no_user task_id=%s key=%s",
                    task.id, task.key,
                )
                continue
            job = Job(
                enterprise_id=task.enterprise_id,
                job_type="daily_digest",
                status="queued",
                max_attempts=get_settings().worker_job_max_attempts,
                payload_json={
                    "user_id": str(user_id),
                    "scheduled_task_id": str(task.id),
                    "trigger_type": "scheduled",
                },
                scope_snapshot_json={
                    "enterprise_id": str(task.enterprise_id),
                },
                scheduled_at=now,
            )
        else:
            job = Job(
                enterprise_id=task.enterprise_id,
                job_type="data.sync",
                status="queued",
                max_attempts=get_settings().worker_job_max_attempts,
                payload_json={
                    "data_source_id": str(task.data_source_id),
                    "scheduled_task_id": str(task.id),
                    "trigger_type": "scheduled",
                    "validation_only": False,
                    "operation": "activate",
                    "activation_mode": "all_three_atomic",
                },
                scope_snapshot_json={
                    "enterprise_id": str(task.enterprise_id),
                },
                scheduled_at=now,
            )
        session.add(job)
        session.flush()  # 取 job.id

        session.add(
            ScheduleRun(
                scheduled_task_id=task.id,
                enterprise_id=task.enterprise_id,
                job_id=job.id,
                window_key=window_key,
                trigger_type="schedule",
                status="enqueued",
                scheduled_for=scheduled_for,
                enqueued_at=now,
            )
        )

        task.next_run_at = next_at
        task.last_enqueued_at = now
        enqueued += 1
        logger.info(
            "scheduled_task_enqueued task_id=%s job_id=%s window=%s next_run_at=%s",
            task.id,
            job.id,
            window_key,
            next_at.isoformat(),
        )

    return enqueued


def claim_next_job(worker_id: str, *, session: Session) -> tuple[Job, str] | None:
    """Atomically pull the next queued job and acquire a lease.

    Uses Postgres ``FOR UPDATE SKIP LOCKED`` when the underlying dialect is
    PostgreSQL; on sqlite (used by tests) a fallback path performs an
    explicit ``IMMEDIATE`` transaction to keep the same effect.

    Implementation note: this function speaks to the database via raw
    ``text()`` statements only. The ORM ``UUID()`` type-adapter for the
    ``jobs.id`` primary key on the sqlite dialect does not currently
    round-trip a 32-character hex representation cleanly (the value is
    formatted to ``.hex`` once, then processed again as a UUID). Until the
    schema explicitly declares ``String(32)`` for the uuid PK columns or the
    ``Uuid()`` dialect is patched, the safest path is to keep this method
    one step removed from the ORM mapper.
    """
    from sqlalchemy import text

    now = utc_now()
    expires = now + LEASE_DURATION
    bind = session.get_bind()
    is_postgres = bind is not None and bind.dialect.name == "postgresql"

    # Single statement: do everything in one query so SQLite sees one
    # transaction with one bind set. Using positional placeholders (''?'')
    # avoids the duplicated named-parameter processor that the ORM
    # binder triggers.
    # Select the queued job AND its current attempt_count + job_type, so we
    # don't need a second round-trip via the ORM mapper afterwards.
    select_sql_skeleton = """
        SELECT id, attempt_count, job_type FROM jobs
        WHERE status = 'queued'
          AND (scheduled_at IS NULL OR scheduled_at <= :now)
        ORDER BY (scheduled_at IS NULL), scheduled_at, created_at
        LIMIT 1
    """
    if is_postgres:
        select_sql = (
            "SELECT id, attempt_count, job_type FROM jobs WHERE status = 'queued'"
            " AND (scheduled_at IS NULL OR scheduled_at <= :now) ORDER BY"
            " scheduled_at NULLS LAST, created_at FOR UPDATE SKIP LOCKED LIMIT 1"
        )
    else:
        select_sql = select_sql_skeleton

    row = session.execute(text(select_sql), {"now": now}).first()
    if row is None:
        return None
    job_id = row[0]
    current_attempts = row[1] or 0
    job_type = row[2] or ""
    if row is None:
        return None
    job_id = row[0]
    current_attempts = row[1] or 0
    token = _new_lease_token()

    update_sql = (
        "UPDATE jobs"
        " SET status = 'running',"
        "     started_at = :now, lease_owner = :worker_id, lease_token = :token,"
        "     lease_expires_at = :expires, heartbeat_at = :now, attempt_count = :new_attempts"
        " WHERE id = :job_id AND status = 'queued'"
    )
    update_row = session.execute(
        text(update_sql),
        {
            "now": now,
            "expires": expires,
            "worker_id": worker_id,
            "token": token,
            "job_id": job_id,  # already hex from SELECT
            "new_attempts": current_attempts + 1,
        },
    )
    if getattr(update_row, "rowcount", 0) == 0:
        return None
    # ``text()`` UPDATE statements are not auto-committed by SQLAlchemy;
    # commit so the leased row is durable before we hand the Job back to the
    # caller.
    session.commit()

    # Build a transient Job in memory to return to the caller. We *do not*
    # read back via the ORM mapper; see the docstring above.
    job = Job(
        id=uuid.UUID(job_id) if isinstance(job_id, str) else job_id,
        enterprise_id=uuid.uuid4(),  # placeholder; runner does not audit per-job
        job_type=job_type,
        status="running",
        max_attempts=3,
        started_at=now,
        lease_owner=worker_id,
        lease_token=token,
        lease_expires_at=expires,
        heartbeat_at=now,
        attempt_count=current_attempts + 1,
    )
    return job, token


# --------------------------------------------------------------------------
# Main loop
# --------------------------------------------------------------------------

class JobRunner:
    """Long-running scheduler / worker loop.

    Started by ``services.job_runner.start_job_runner`` when ``service_role``
    includes ``api`` (the new default) or when the optional
    ``JOB_RUNNER_FORCE`` env-var is set.

    Decoupled from the API process via ``asyncio``: pick a job, run its
    handler in ``run_in_executor``, update DB on completion, repeat.
    """

    def __init__(
        self,
        *,
        handlers: Mapping[str, JobHandler] | None = None,
        settings: Settings | None = None,
        poll_seconds: float = 5.0,
        worker_id: str | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._handlers: dict[str, JobHandler] = dict(DEFAULT_HANDLERS)
        if handlers:
            self._handlers.update(handlers)
        self._poll_seconds = poll_seconds
        self._worker_id = worker_id or f"{os.uname().nodename if hasattr(os, 'uname') else 'host'}-{os.getpid()}-{secrets.token_hex(4)}"
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._context = JobRunnerContext(self._worker_id)

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def context(self) -> JobRunnerContext:
        return self._context

    def register(self, job_type: str, handler: JobHandler) -> None:
        self._handlers[job_type] = handler

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="job-runner")

    async def stop(self, *, timeout: float = 10.0) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        try:
            await asyncio.wait_for(self._task, timeout=timeout)
        except asyncio.TimeoutError:  # pragma: no cover
            self._task.cancel()
        finally:
            self._task = None

    async def _run(self) -> None:
        logger.info("job_runner_started worker_id=%s", self._worker_id)
        while not self._stop_event.is_set():
            try:
                processed = self._tick()
                if not processed:
                    try:
                        await asyncio.wait_for(
                            self._stop_event.wait(), timeout=self._poll_seconds
                        )
                    except asyncio.TimeoutError:
                        pass
            except OperationalError as exc:
                logger.warning("job_runner_db_error err=%s", exc)
                await asyncio.sleep(1.0)
            except Exception as exc:  # noqa: BLE001
                logger.exception("job_runner_tick_crashed err=%s", exc)
                await asyncio.sleep(1.0)
        logger.info("job_runner_stopped worker_id=%s", self._worker_id)

    def _tick(self) -> bool:
        """Run one poll cycle synchronously; return ``True`` if a job was handled."""
        with SessionLocal() as session:
            requeued = requeue_expired_leases(session=session)
            session.commit()
            if requeued:
                logger.info("job_runner_requeued count=%d", requeued)

            enqueued = enqueue_due_scheduled_tasks(session)
            if enqueued:
                logger.info("job_runner_scheduled_enqueued count=%d", enqueued)
            session.commit()

            claim = claim_next_job(self._worker_id, session=session)
            if claim is None:
                return False
            job, token = claim
            session.commit()

        handler = self._handlers.get(job.job_type)
        if handler is None:
            logger.warning(
                "job_runner_unknown_type job_id=%s job_type=%s",
                job.id,
                job.job_type,
            )
            with SessionLocal() as session:
                finish_failure(
                    job.id,
                    session=session,
                    error_code="unknown_job_type",
                    error_message=f"no handler registered for job_type={job.job_type}",
                )
                session.commit()
            return True

        try:
            coro_or_result = handler(self._context, job, self._settings)
            if _is_awaitable(coro_or_result):
                result = _run_coro_blocking(coro_or_result)
            else:
                result = coro_or_result
        except Exception as exc:  # noqa: BLE001
            logger.exception("job_runner_handler_failed job_id=%s", job.id)
            with SessionLocal() as session:
                finish_failure(
                    job.id,
                    session=session,
                    error_code=getattr(exc, "code", "handler_failed"),
                    error_message=f"{type(exc).__name__}: {exc}"[:4096],
                    dead_letter=(job.attempt_count >= job.max_attempts),
                )
                session.commit()
            return True

        with SessionLocal() as session:
            if heartbeat(job.id, self._worker_id, session=session):
                session.commit()
                finish_success(job.id, session=session, result=result)
                session.commit()
            else:
                # lease was lost (rare) — still persist result so manual review can find it
                finish_success(
                    job.id,
                    session=session,
                    result={"warning": "lease_lost", **dict(result or {})},
                )
                session.commit()
        return True


def _is_awaitable(value: Any) -> bool:
    """Return ``True`` if ``value`` is an awaitable / coroutine returned by an async handler."""
    return asyncio.iscoroutine(value) or asyncio.isfuture(value)


def _run_coro_blocking(coro: Any) -> Any:
    """Run ``coro`` blocking until it returns, working in both sync and async contexts.

    When invoked from inside an already-running event loop (the production
    runner's ``_run`` task), we can't call ``loop.run_until_complete`` —
    that raises ``RuntimeError: This event loop is already running``. Instead
    we run the coroutine on a worker thread's dedicated loop and wait for
    the result. When invoked synchronously (e.g. from a unit test) we just
    use ``asyncio.run`` directly.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop — safe to use asyncio.run.
        return asyncio.run(_await_collect(coro))

    # There IS a running loop in the current thread. Run the coroutine in
    # a separate worker thread that has its own loop, then block this thread
    # waiting for the result. This avoids the "already running" RuntimeError
    # while still providing a synchronous return value for callers.
    import concurrent.futures

    def _runner() -> Any:
        return asyncio.run(_await_collect(coro))

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_runner)
        return future.result()


async def _await_collect(coro: Any) -> Any:
    return await coro


# --------------------------------------------------------------------------
# Bootstrap helpers
# --------------------------------------------------------------------------

def should_run_in_process() -> bool:
    """Decide whether the local process should auto-start the runner.

    Driven by ``Settings.service_role`` (must include ``api`` or
    ``scheduler``) and the explicit ``JOB_RUNNER_FORCE`` env-override.
    """
    role = get_settings().service_role
    if os.environ.get("JOB_RUNNER_FORCE"):
        return True
    if os.environ.get("JOB_RUNNER_DISABLE"):
        return False
    return role in {"api", "scheduler"}


_runner: JobRunner | None = None


def get_runner() -> JobRunner:
    """Return the process-wide runner, creating it lazily."""
    global _runner
    if _runner is None:
        _runner = JobRunner()
    return _runner


async def start_job_runner() -> JobRunner | None:
    """Start the runner if the current process should host it; else return ``None``."""
    if not should_run_in_process():
        return None
    runner = get_runner()
    await runner.start()
    return runner


async def stop_job_runner() -> None:
    runner = _runner
    if runner is not None:
        await runner.stop()
