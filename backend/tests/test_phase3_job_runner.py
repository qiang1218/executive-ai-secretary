"""Phase 3 job runner tests.

Uses an in-memory sqlite via ``conftest.py`` and exercises ``services.job_runner``
end-to-end without bringing up the API or worker.

Coverage:

* ``requeue_expired_leases`` brings stale ``running`` rows back to ``queued``.
* ``claim_next_job`` returns ``None`` when no jobs are pending and the
  correct job + token otherwise.
* ``acquire_lease`` / ``finish_success`` / ``finish_failure`` mutate the
  row exactly as expected.
* ``JobRunner._tick`` invokes a registered handler when a queued job is
  available.
"""
from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select, text

from core.security import utc_now
from db import SessionLocal
from models.job import Job
from services import job_runner as job_runner_mod
from services.job_runner import (
    DEFAULT_HANDLERS,
    JobRunner,
    acquire_lease,
    claim_next_job,
    finish_failure,
    finish_success,
    heartbeat,
    requeue_expired_leases,
)


# ── auto-clean fixture: the in-memory sqlite is shared across the
# entire pytest session, so each test must start with a clean jobs
# table to remain deterministic. ──────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_jobs_table():
    with SessionLocal() as session:
        session.execute(text("DELETE FROM jobs"))
        session.commit()
    yield
    with SessionLocal() as session:
        session.execute(text("DELETE FROM jobs"))
        session.commit()


# ── helpers ─────────────────────────────────────────────────────────────


def _make_job(job_type: str = "system.noop", payload: dict | None = None) -> Job:
    payload = payload or {"hello": "world"}
    job_id = uuid.uuid4()
    job = Job(
        id=job_id,
        enterprise_id=uuid.uuid4(),
        created_by_user_id=None,
        harness_version_id=None,
        job_type=job_type,
        status="queued",
        payload_json=payload,
        scope_snapshot_json={},
        result_json={},
        max_attempts=3,
        attempt_count=0,
    )
    with SessionLocal() as session:
        session.add(job)
        session.commit()
        session.refresh(job)
    return job_id


def _row(job_id: uuid.UUID) -> Job | None:
    with SessionLocal() as session:
        return session.scalar(select(Job).where(Job.id == job_id))


# ── claim / lease / finish ──────────────────────────────────────────────


def test_claim_next_job_returns_none_when_queue_is_empty() -> None:
    with SessionLocal() as session:
        out = claim_next_job("worker-A", session=session)
    assert out is None


def test_claim_next_job_moves_queued_to_running() -> None:
    job_id = _make_job()
    with SessionLocal() as session:
        out = claim_next_job("worker-A", session=session)
    assert out is not None
    job, token = out
    assert job.id == job_id
    assert isinstance(token, str) and len(token) > 0

    row = _row(job_id)
    assert row is not None
    assert row.status == "running"
    assert row.lease_owner == "worker-A"
    assert row.attempt_count == 1
    assert row.started_at is not None
    assert row.lease_expires_at is not None
    assert row.heartbeat_at is not None


def test_acquire_lease_returns_token_for_owner() -> None:
    job_id = _make_job()
    with SessionLocal() as session:
        assert claim_next_job("worker-A", session=session) is not None
        token = acquire_lease(job_id, "worker-A", session=session)
    assert token is not None
    row = _row(job_id)
    assert row.lease_token == token
    assert row.lease_expires_at > utc_now()


def test_acquire_lease_returns_none_for_other_worker() -> None:
    job_id = _make_job()
    with SessionLocal() as session:
        claim_next_job("worker-A", session=session)
    with SessionLocal() as session:
        token = acquire_lease(job_id, "worker-B", session=session)
    assert token is None


def test_heartbeat_is_a_noop_when_lease_is_lost() -> None:
    job_id = _make_job()
    with SessionLocal() as session:
        claim_next_job("worker-A", session=session)
    with SessionLocal() as session:
        ok = heartbeat(job_id, "worker-B", session=session)
    assert ok is False


def test_finish_success_marks_completed() -> None:
    job_id = _make_job()
    with SessionLocal() as session:
        claim_next_job("worker-A", session=session)
    with SessionLocal() as session:
        finish_success(job_id, session=session, result={"y": 1})
    row = _row(job_id)
    assert row.status == "completed"
    assert row.completed_at is not None
    assert row.result_json == {"y": 1}


def test_finish_failure_marks_failed() -> None:
    job_id = _make_job()
    with SessionLocal() as session:
        claim_next_job("worker-A", session=session)
    with SessionLocal() as session:
        finish_failure(
            job_id,
            session=session,
            error_code="upstream",
            error_message="something broke",
        )
    row = _row(job_id)
    assert row.status == "failed"
    assert row.error_code == "upstream"
    assert row.error_message == "something broke"
    assert row.dead_lettered_at is None


def test_finish_failure_can_dead_letter() -> None:
    job_id = _make_job()
    with SessionLocal() as session:
        claim_next_job("worker-A", session=session)
    with SessionLocal() as session:
        finish_failure(
            job_id,
            session=session,
            error_code="dlq",
            error_message="x",
            dead_letter=True,
        )
    row = _row(job_id)
    assert row.status == "failed"
    assert row.dead_lettered_at is not None


def test_requeue_expired_leases_requeues_stale_running_jobs() -> None:
    job_id = _make_job()
    with SessionLocal() as session:
        claim_next_job("worker-A", session=session)
    # Force the lease into the past.
    with SessionLocal() as session:
        row = session.scalar(select(Job).where(Job.id == job_id))
        row.lease_expires_at = utc_now() - timedelta(seconds=10)
        session.commit()
    with SessionLocal() as session:
        n = requeue_expired_leases(session=session)
        session.commit()
    assert n >= 1
    row = _row(job_id)
    assert row.status == "queued"
    assert row.lease_owner is None


# ── JobRunner._tick ─────────────────────────────────────────────────────


def test_runner_tick_invokes_registered_handler() -> None:
    job_id = _make_job(job_type="system.noop")

    seen: dict[str, Job] = {}

    async def handler(ctx, job, settings):
        seen["job_id"] = job.id
        seen["worker_id"] = ctx.worker_id
        return {"ok": True}

    runner = JobRunner(handlers={"system.noop": handler})
    assert runner._tick() is True

    assert seen.get("job_id") == job_id
    assert seen.get("worker_id") == runner.worker_id

    row = _row(job_id)
    assert row.status == "completed"
    assert row.result_json == {"ok": True}


def test_runner_tick_returns_false_when_no_jobs() -> None:
    runner = JobRunner()
    assert runner._tick() is False


def test_runner_tick_marks_unknown_job_type_failed() -> None:
    job_id = _make_job(job_type="this.does.not.exist")
    runner = JobRunner()
    assert runner._tick() is True
    row = _row(job_id)
    assert row.status == "failed"
    assert row.error_code == "unknown_job_type"


def test_runner_tick_is_idempotent_when_handler_raises() -> None:
    job_id = _make_job(job_type="system.noop")

    async def boom(ctx, job, settings):
        raise RuntimeError("nope")

    runner = JobRunner(handlers={"system.noop": boom})
    assert runner._tick() is True
    row = _row(job_id)
    assert row.status == "failed"
    assert "RuntimeError" in row.error_message


def test_default_handlers_cover_known_job_types() -> None:
    for job_type in ("data.sync", "file.extract", "system.noop"):
        assert job_type in DEFAULT_HANDLERS
