"""Background worker runner.

This module is the equivalent of ``new/services/worker/src/executive_ai_worker/main.py``.
It polls the ``jobs`` table, claims a job, runs the handler, and writes the
result back. ``backend/main.py`` calls ``run_worker()`` when started with
``--worker``.

启动方式:

- ``python main.py --worker``        启动 worker（占用当前进程，不启动 API）
- ``python main.py --worker --api``  同时启动 worker 线程 + API（开发用）
- ``python main.py``                 默认只启动 API
"""

from __future__ import annotations

import logging
import os
import signal
import socket
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, or_, select

from configs.settings import get_settings, Settings
from core.security import as_utc, utc_now
from db.session import SessionLocal
from logs.config import configure_logging
from models import (
    AuditEvent,
    Enterprise,
    FileExtraction,
    Job,
    JobAttempt,
    ScheduleRun,
    User,
)
from services.authz import scope_snapshot_is_current_for_user
from services.ingestion import IngestionError, run_data_sync_job
from services.job_state import (
    ASSISTANT_NOT_CONFIGURED_CONTENT,
    close_assistant_placeholder,
)

from worker_old.assistant_orchestrator import (
    OrchestrationPermanentError,
    run_assistant_job,
)
from worker_old.file_extraction import (
    FileExtractionPermanentError,
    run_file_extract_job,
)

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("executive_ai_worker")

stopping = False
worker_id = f"{socket.gethostname()}:{os.getpid()}"
RETRY_EXHAUSTED_CONTENT = "处理任务多次中断，请稍后重试"
SYSTEM_JOB_TYPES = {"data.sync", "system.noop"}


@dataclass(frozen=True)
class ClaimedJob:
    job_id: str
    lease_token: str


class PermanentJobError(Exception):
    def __init__(self, code: str, message: str, placeholder_content: str) -> None:
        self.code = code
        self.placeholder_content = placeholder_content
        super().__init__(message)


# 模块级变量：LISTEN 连接引用，供 stop() 关闭以立即中断阻塞
_listen_conn_ref: list = []


def stop(*_: object) -> None:
    global stopping
    stopping = True
    # 关闭 LISTEN 连接，中断 conn.notifies(timeout=60) 阻塞
    global _listen_conn_ref
    for conn in _listen_conn_ref:
        try:
            conn.close()
        except Exception:
            pass


def _database_now(db):
    value = db.scalar(select(func.now()))
    if value is None:
        raise RuntimeError("database clock is unavailable")
    return as_utc(value)


def authorization_is_current(db, job: Job | None) -> bool:
    if job is None:
        return False
    if job.job_type in SYSTEM_JOB_TYPES:
        enterprise = db.get(Enterprise, job.enterprise_id)
        if enterprise is None or not enterprise.is_active:
            return False
        if job.created_by_user_id is None:
            return (
                job.scope_snapshot_json.get("system") is True
                and job.scope_snapshot_json.get("enterprise_id") == str(job.enterprise_id)
            )
        user = db.get(User, job.created_by_user_id)
        return bool(
            user
            and user.is_active
            and user.enterprise_id == job.enterprise_id
            and user.role in {"enterprise_admin", "fde"}
        )
    if not job.created_by_user_id:
        return False
    user = db.get(User, job.created_by_user_id)
    if user is None or not user.is_active or user.role != "executive":
        return False
    enterprise = db.get(Enterprise, job.enterprise_id)
    if enterprise is None or not enterprise.is_active or user.enterprise_id != enterprise.id:
        return False
    return scope_snapshot_is_current_for_user(db, user, job.scope_snapshot_json)


def retry_delay_seconds(attempt_count: int) -> float:
    exponent = max(0, min(attempt_count - 1, 30))
    return min(
        settings.worker_retry_max_seconds,
        settings.worker_retry_base_seconds * (2**exponent),
    )


def _audit(db, job: Job, action: str, *, outcome: str, reason: str | None = None) -> None:
    db.add(
        AuditEvent(
            enterprise_id=job.enterprise_id,
            actor_user_id=job.created_by_user_id,
            action=action,
            target_type="job",
            target_id=str(job.id),
            outcome=outcome,
            failure_reason_code=reason,
            metadata_json={
                "job_type": job.job_type,
                "attempt": job.attempt_count,
                "max_attempts": job.max_attempts,
                "error_code": job.error_code,
            },
        )
    )


def _running_attempt(db, job: Job) -> JobAttempt | None:
    statement = select(JobAttempt).where(
        JobAttempt.job_id == job.id,
        JobAttempt.status == "running",
    )
    if job.lease_token:
        statement = statement.where(JobAttempt.lease_token == job.lease_token)
    return db.scalar(statement.order_by(JobAttempt.attempt.desc()).limit(1))


def _clear_lease(job: Job) -> None:
    job.lease_owner = None
    job.lease_token = None
    job.lease_expires_at = None
    job.heartbeat_at = None


def _update_file_extraction_status(
    db,
    job: Job,
    *,
    status: str,
    error_code: str | None,
    error_message: str | None,
    completed_at=None,
) -> None:
    if job.job_type != "file.extract":
        return
    try:
        file_id = uuid.UUID(str(job.payload_json["file_id"]))
    except (KeyError, TypeError, ValueError):
        return
    extraction = db.scalar(select(FileExtraction).where(FileExtraction.file_id == file_id))
    if extraction is None:
        return
    extraction.status = status
    extraction.error_code = error_code
    extraction.error_message = error_message[:2000] if error_message else None
    extraction.completed_at = completed_at


def _close_attempt(
    attempt: JobAttempt | None,
    *,
    status: str,
    error_code: str | None,
    error_message: str | None,
    completed_at=None,
) -> None:
    if attempt is None:
        return
    attempt.status = status
    attempt.completed_at = completed_at or utc_now()
    attempt.error_code = error_code
    attempt.error_message = error_message


def _terminal_failure(
    db,
    job: Job,
    attempt: JobAttempt | None,
    *,
    error_code: str,
    error_message: str,
    placeholder_content: str,
    dead_lettered: bool,
) -> None:
    now = _database_now(db)
    job.status = "failed"
    job.error_code = error_code
    job.error_message = error_message[:2000]
    job.completed_at = now
    job.dead_lettered_at = now if dead_lettered else None
    _update_file_extraction_status(
        db,
        job,
        status="failed",
        error_code=error_code,
        error_message=error_message,
        completed_at=now,
    )
    _close_attempt(
        attempt,
        status="failed",
        error_code=error_code,
        error_message=job.error_message,
        completed_at=now,
    )
    _clear_lease(job)
    for schedule_run in db.scalars(select(ScheduleRun).where(ScheduleRun.job_id == job.id)).all():
        schedule_run.status = "failed"
        schedule_run.completed_at = now
        schedule_run.error_code = error_code
        schedule_run.error_message = error_message[:2000]
    close_assistant_placeholder(db, job, status="failed", content=placeholder_content)
    _audit(
        db,
        job,
        "job.dead_lettered" if dead_lettered else "job.failed",
        outcome="failure",
        reason="max_attempts_exhausted" if dead_lettered else error_code,
    )


def _retry_or_dead_letter(
    db,
    job: Job,
    attempt: JobAttempt | None,
    *,
    error_code: str,
    error_message: str,
    attempt_status: str,
) -> None:
    if job.attempt_count >= job.max_attempts:
        _terminal_failure(
            db,
            job,
            attempt,
            error_code=error_code,
            error_message=error_message,
            placeholder_content=RETRY_EXHAUSTED_CONTENT,
            dead_lettered=True,
        )
        return
    now = _database_now(db)
    delay = retry_delay_seconds(job.attempt_count)
    job.status = "queued"
    job.scheduled_at = now + timedelta(seconds=delay)
    job.completed_at = None
    job.error_code = error_code
    job.error_message = error_message[:2000]
    _update_file_extraction_status(
        db,
        job,
        status="queued",
        error_code=error_code,
        error_message=error_message,
    )
    _close_attempt(
        attempt,
        status=attempt_status,
        error_code=error_code,
        error_message=job.error_message,
        completed_at=now,
    )
    _clear_lease(job)
    close_assistant_placeholder(db, job, status="queued")
    _audit(db, job, "job.retry_scheduled", outcome="failure", reason=error_code)


def fail_revoked_job(db, job: Job) -> None:
    _terminal_failure(
        db,
        job,
        _running_attempt(db, job),
        error_code="authorization_revoked",
        error_message="User or data scope authorization is no longer valid",
        placeholder_content="请求权限已变更，未执行处理",
        dead_lettered=False,
    )


def recover_expired_leases(limit: int = 100) -> int:
    recovered = 0
    with SessionLocal.begin() as db:
        now = _database_now(db)
        jobs = db.scalars(
            select(Job)
            .where(
                Job.status == "running",
                or_(Job.lease_expires_at.is_(None), Job.lease_expires_at <= now),
            )
            .order_by(Job.lease_expires_at, Job.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        for job in jobs:
            _retry_or_dead_letter(
                db,
                job,
                _running_attempt(db, job),
                error_code="lease_expired",
                error_message="Worker lease expired before the attempt completed",
                attempt_status="lease_expired",
            )
            recovered += 1
    return recovered


def claim_one() -> ClaimedJob | None:
    recover_expired_leases()
    with SessionLocal.begin() as db:
        now = _database_now(db)
        statement = select(Job).where(
            Job.status == "queued",
            or_(Job.scheduled_at.is_(None), Job.scheduled_at <= now),
        )
        if "*" not in settings.worker_job_types:
            statement = statement.where(Job.job_type.in_(settings.worker_job_types))
        job = db.scalar(
            statement.order_by(Job.created_at).limit(1).with_for_update(skip_locked=True)
        )
        if job is None:
            return None
        if job.attempt_count >= job.max_attempts:
            _terminal_failure(
                db,
                job,
                None,
                error_code="max_attempts_exhausted",
                error_message="Job reached its maximum attempt count before claim",
                placeholder_content=RETRY_EXHAUSTED_CONTENT,
                dead_lettered=True,
            )
            return None
        if not authorization_is_current(db, job):
            fail_revoked_job(db, job)
            return None

        lease_token = uuid.uuid4().hex
        lease_expires_at = now + timedelta(seconds=settings.worker_lease_seconds)
        job.status = "running"
        job.started_at = job.started_at or now
        job.completed_at = None
        job.scheduled_at = None
        job.error_code = None
        job.error_message = None
        job.attempt_count += 1
        job.lease_owner = worker_id
        job.lease_token = lease_token
        job.lease_expires_at = lease_expires_at
        job.heartbeat_at = now
        db.add(
            JobAttempt(
                job_id=job.id,
                attempt=job.attempt_count,
                worker_id=worker_id,
                lease_token=lease_token,
                status="running",
                started_at=now,
                heartbeat_at=now,
                lease_expires_at=lease_expires_at,
            )
        )
        close_assistant_placeholder(db, job, status="running")
        _audit(db, job, "job.started", outcome="success")
        return ClaimedJob(job_id=str(job.id), lease_token=lease_token)


def renew_lease(job_id: str, lease_token: str) -> bool:
    """Heartbeat contract for current and future long-running production handlers."""

    with SessionLocal.begin() as db:
        now = _database_now(db)
        job = db.scalar(select(Job).where(Job.id == uuid.UUID(job_id)).with_for_update())
        if (
            job is None
            or job.status != "running"
            or job.lease_owner != worker_id
            or job.lease_token != lease_token
            or job.lease_expires_at is None
            or as_utc(job.lease_expires_at) <= now
        ):
            return False
        attempt = _running_attempt(db, job)
        if attempt is None:
            return False
        deadline = now + timedelta(seconds=settings.worker_lease_seconds)
        job.heartbeat_at = now
        job.lease_expires_at = deadline
        attempt.heartbeat_at = now
        attempt.lease_expires_at = deadline
        return True


heartbeat = renew_lease


def execute_job_handler(job: Job) -> dict:
    if job.job_type == "system.noop":
        return {"ok": True}
    if job.job_type == "data.sync":
        try:
            return run_data_sync_job(job, settings)
        except IngestionError as exc:
            if exc.code in {
                "99991672",
                "feishu_binding_incomplete",
                "feishu_schema_drift",
                "feishu_reliability_invalid",
                "source_contract_invalid",
                "source_schema_version_mismatch",
            }:
                raise PermanentJobError(exc.code, str(exc), "数据同步失败") from exc
            raise
    if job.job_type == "assistant_response":
        try:
            return run_assistant_job(job, settings)
        except OrchestrationPermanentError as exc:
            raise PermanentJobError(exc.code, str(exc), exc.placeholder) from exc
    if job.job_type == "file.extract":
        try:
            return run_file_extract_job(job, settings)
        except FileExtractionPermanentError as exc:
            raise PermanentJobError(exc.code, str(exc), "文件解析失败") from exc
    raise PermanentJobError(
        "integration_not_configured",
        "No production handler is configured for this job type",
        ASSISTANT_NOT_CONFIGURED_CONTENT,
    )


def _owned_running_job(db, job_id: str, lease_token: str, *, unexpired: bool) -> Job | None:
    job = db.scalar(select(Job).where(Job.id == uuid.UUID(job_id)).with_for_update())
    if (
        job is None
        or job.status != "running"
        or job.lease_owner != worker_id
        or job.lease_token != lease_token
    ):
        return None
    if unexpired and (
        job.lease_expires_at is None or as_utc(job.lease_expires_at) <= _database_now(db)
    ):
        return None
    return job


def _finish_success(job_id: str, lease_token: str, result: dict) -> bool:
    with SessionLocal.begin() as db:
        job = _owned_running_job(db, job_id, lease_token, unexpired=True)
        if job is None:
            return False
        if not authorization_is_current(db, job):
            fail_revoked_job(db, job)
            return True
        attempt = _running_attempt(db, job)
        job.status = "completed"
        job.result_json = result
        now = _database_now(db)
        job.completed_at = now
        job.dead_lettered_at = None
        _close_attempt(
            attempt,
            status="completed",
            error_code=None,
            error_message=None,
            completed_at=now,
        )
        _clear_lease(job)
        for schedule_run in db.scalars(
            select(ScheduleRun).where(ScheduleRun.job_id == job.id)
        ).all():
            schedule_run.status = "completed"
            schedule_run.completed_at = now
        content = result.get("content")
        close_assistant_placeholder(
            db,
            job,
            status="completed",
            content=content if isinstance(content, str) else None,
        )
        _audit(db, job, "job.completed", outcome="success")
        return True


def _finish_permanent_failure(
    job_id: str,
    lease_token: str,
    error: PermanentJobError,
) -> bool:
    with SessionLocal.begin() as db:
        job = _owned_running_job(db, job_id, lease_token, unexpired=True)
        if job is None:
            return False
        _terminal_failure(
            db,
            job,
            _running_attempt(db, job),
            error_code=error.code,
            error_message=str(error),
            placeholder_content=error.placeholder_content,
            dead_lettered=False,
        )
        return True


def _finish_unexpected_failure(job_id: str, lease_token: str, error: Exception) -> bool:
    with SessionLocal.begin() as db:
        job = _owned_running_job(db, job_id, lease_token, unexpired=True)
        if job is None:
            return False
        message = f"{type(error).__name__}: {error}"[:2000]
        _retry_or_dead_letter(
            db,
            job,
            _running_attempt(db, job),
            error_code="processing_error",
            error_message=message,
            attempt_status="failed",
        )
        return True


def _heartbeat_loop(
    job_id: str,
    lease_token: str,
    stop_event: threading.Event,
    lease_lost: threading.Event,
) -> None:
    while not stop_event.wait(settings.worker_heartbeat_seconds):
        try:
            if not renew_lease(job_id, lease_token):
                lease_lost.set()
                return
        except Exception:
            # A transient heartbeat database failure is retried. Final writes remain
            # fenced by the database lease deadline even if every renewal fails.
            logger.exception(
                "job_heartbeat_failed", extra={"structured": {"job_id": job_id}}
            )


def process(job_id: str, lease_token: str) -> bool:
    with SessionLocal.begin() as db:
        job = _owned_running_job(db, job_id, lease_token, unexpired=True)
        if job is None:
            return False
        if not authorization_is_current(db, job):
            fail_revoked_job(db, job)
            return True
    stop_event = threading.Event()
    lease_lost = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(job_id, lease_token, stop_event, lease_lost),
        name=f"job-heartbeat-{job_id}",
        daemon=True,
    )
    heartbeat_thread.start()
    result: dict | None = None
    permanent_error: PermanentJobError | None = None
    unexpected_error: Exception | None = None
    try:
        result = execute_job_handler(job)
    except PermanentJobError as error:
        permanent_error = error
    except Exception as error:
        logger.exception(
            "job_handler_failed", extra={"structured": {"job_id": job_id}}
        )
        unexpected_error = error
    finally:
        stop_event.set()
        heartbeat_thread.join(timeout=max(1.0, settings.worker_heartbeat_seconds))
    if lease_lost.is_set():
        return False
    if permanent_error is not None:
        return _finish_permanent_failure(job_id, lease_token, permanent_error)
    if unexpected_error is not None:
        return _finish_unexpected_failure(job_id, lease_token, unexpected_error)
    if result is None:
        return _finish_unexpected_failure(
            job_id,
            lease_token,
            RuntimeError("job handler returned no result"),
        )
    return _finish_success(job_id, lease_token, result)


def run_worker() -> None:
    """Main worker loop. Blocks until SIGTERM/SIGINT.

    使用 PostgreSQL LISTEN/NOTIFY 事件驱动：job 入队时 API 发 NOTIFY，
    worker 收到通知才 claim，无 job 时阻塞等待，不轮询数据库。

    实现：用 psycopg 在独立线程中 LISTEN，收到通知后通过 threading.Event
    唤醒主线程 claim。这样主线程保持同步代码，避免 asyncio 引入。

    claim_one 拿到 job 后丢进 ThreadPoolExecutor 异步执行，主线程立即
    下一轮 claim。并发度由 ``settings.worker_concurrency`` 控制。
    """
    if settings.service_role == "assistant_worker":
        settings.integration_encryption_keys()
    import threading as _threading
    if _threading.current_thread() is _threading.main_thread():
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
    logger.info(
        "worker_started",
        extra={
            "structured": {
                "worker_id": worker_id,
                "concurrency": settings.worker_concurrency,
            }
        },
    )

    from concurrent.futures import Future, ThreadPoolExecutor

    pool = ThreadPoolExecutor(
        max_workers=settings.worker_concurrency,
        thread_name_prefix="job-exec",
    )
    in_flight: set[Future] = set()

    def _drain_done() -> None:
        """清理已完成的 future，记录未捕获异常。"""
        done = {f for f in in_flight if f.done()}
        in_flight.difference_update(done)
        for f in done:
            exc = f.exception()
            if exc is not None:
                logger.exception(
                    "job_future_crashed",
                    extra={"structured": {"error": repr(exc)}},
                )

    # psycopg 同步连接在独立线程中 LISTEN，用 Event 唤醒主线程
    notify_event = _threading.Event()
    listen_error: list[str] = []

    def _listen_thread() -> None:
        """独立线程：用 psycopg 同步连接 LISTEN new_job，收到通知时 set Event。"""
        import psycopg

        conn = None
        try:
            dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
            conn = psycopg.connect(dsn, autocommit=True)
            global _listen_conn_ref
            _listen_conn_ref.append(conn)
            conn.execute("LISTEN new_job")
            logger.info(
                "worker_listening", extra={"structured": {"channel": "new_job"}}
            )
            while not stopping:
                # 阻塞等待通知，最多 60s 超时（兜底）
                gen = conn.notifies(timeout=60.0)
                for _notification in gen:
                    notify_event.set()
        except Exception as exc:
            if not stopping:
                listen_error.append(str(exc))
                logger.exception("listen_thread_failed")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            _listen_conn_ref.clear()
            notify_event.set()  # 出错或关闭时唤醒主线程，让它检测 stopping

    listen_t = _threading.Thread(target=_listen_thread, daemon=True)
    listen_t.start()

    try:
        idle_rounds = 0
        while not stopping:
            # 等待通知（收到 NOTIFY 或 60s 超时兜底，或 listen 线程异常）
            notify_event.wait(timeout=settings.worker_poll_seconds)
            notify_event.clear()
            if listen_error:
                logger.error(
                    "listen_thread_error",
                    extra={"structured": {"error": listen_error[0]}},
                )
                # 回退到轮询模式
                time.sleep(settings.worker_poll_seconds)
                _drain_done()
                if len(in_flight) >= settings.worker_concurrency:
                    continue
                claimed = claim_one()
                if claimed is not None:
                    future = pool.submit(process, claimed.job_id, claimed.lease_token)
                    in_flight.add(future)
                continue

            _drain_done()
            if len(in_flight) >= settings.worker_concurrency:
                continue
            claimed = claim_one()
            if claimed is not None:
                idle_rounds = 0
                future = pool.submit(process, claimed.job_id, claimed.lease_token)
                in_flight.add(future)
            else:
                # 无 job 时指数退避（处理 NOTIFY 后 job 已被其他 worker claim 的情况）
                idle_rounds += 1
                sleep_sec = min(2 ** idle_rounds, 60)
                time.sleep(sleep_sec)
    finally:
        logger.info(
            "worker_draining",
            extra={"structured": {"in_flight": len(in_flight)}},
        )
        pool.shutdown(wait=True, cancel_futures=False)
        _drain_done()
        logger.info(
            "worker_stopped", extra={"structured": {"worker_id": worker_id}}
        )


def run_worker_in_thread() -> threading.Thread:
    """Start the worker in a daemon thread. Used when API + worker run together."""
    thread = threading.Thread(target=run_worker, name="executive-ai-worker", daemon=True)
    thread.start()
    return thread


__all__ = [
    "ClaimedJob",
    "PermanentJobError",
    "authorization_is_current",
    "claim_one",
    "execute_job_handler",
    "fail_revoked_job",
    "process",
    "recover_expired_leases",
    "renew_lease",
    "heartbeat",
    "run_worker",
    "run_worker_in_thread",
    "stop",
    "worker_id",
]


if __name__ == "__main__":
    run_worker()
