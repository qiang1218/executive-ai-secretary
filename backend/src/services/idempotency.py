from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from services.authz import Principal
from exceptions.errors import AppError
from models import IdempotencyRecord
from core.security import utc_now


def request_fingerprint(payload: Any) -> str:
    serialized = json.dumps(jsonable_encoder(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def _scope_filter(
    request: Request,
    principal: Principal,
    key: str,
) -> tuple[Any, ...]:
    return (
        IdempotencyRecord.user_id == principal.user.id,
        IdempotencyRecord.method == request.method,
        IdempotencyRecord.path == request.url.path,
        IdempotencyRecord.idempotency_key == key,
    )


async def _reserve(
    db: AsyncSession,
    request: Request,
    principal: Principal,
    key: str,
    fingerprint: str,
) -> bool:
    """Atomically reserve an idempotency scope in the current business transaction.

    PostgreSQL's unique-index conflict handling waits for an uncommitted competing
    reservation. Once that transaction commits, this statement either reclaims an
    expired record or returns no row so the caller can replay the committed response.
    The reservation and the business mutation are committed together, so a rollback
    releases both and lets the next request become the owner.
    """

    now = utc_now()
    record_id = uuid.uuid4()
    expires_at = now + timedelta(hours=24)
    values = {
        "id": record_id,
        "user_id": principal.user.id,
        "method": request.method,
        "path": request.url.path,
        "idempotency_key": key,
        "request_hash": fingerprint,
        "response_status": None,
        "response_json": None,
        "expires_at": expires_at,
        "created_at": now,
    }
    statement = postgresql_insert(IdempotencyRecord).values(**values)
    statement = statement.on_conflict_do_update(
        constraint="uq_idempotency_scope",
        set_={
            "request_hash": fingerprint,
            "response_status": None,
            "response_json": None,
            "expires_at": expires_at,
            "created_at": now,
        },
        where=IdempotencyRecord.expires_at <= now,
    )

    statement = statement.returning(IdempotencyRecord.id)
    return (await db.scalar(statement)) is not None


async def replay(
    db: AsyncSession,
    request: Request,
    principal: Principal,
    payload: Any,
) -> tuple[int, dict[str, Any]] | None:
    key = request.headers.get("Idempotency-Key")
    if not key:
        return None
    if len(key) > 200:
        raise AppError(422, "invalid_idempotency_key", "Idempotency-Key 过长")
    fingerprint = request_fingerprint(payload)
    if await _reserve(db, request, principal, key, fingerprint):
        return None
    record = await db.scalar(select(IdempotencyRecord).where(*_scope_filter(request, principal, key)))
    if record is None:
        raise AppError(409, "idempotency_retry", "幂等请求状态已变更，请重试")
    if record.request_hash != fingerprint:
        raise AppError(
            409,
            "idempotency_conflict",
            "相同 Idempotency-Key 已用于不同请求",
        )
    if record.response_status is None or record.response_json is None:
        raise AppError(409, "idempotency_in_progress", "相同请求正在处理中")
    return record.response_status, record.response_json


async def save_response(
    db: AsyncSession,
    request: Request,
    principal: Principal,
    payload: Any,
    status_code: int,
    response: Any,
) -> None:
    key = request.headers.get("Idempotency-Key")
    if not key:
        return
    record = await db.scalar(select(IdempotencyRecord).where(*_scope_filter(request, principal, key)))
    if record is None:
        raise AppError(500, "idempotency_reservation_missing", "幂等请求预占状态缺失")
    if record.request_hash != request_fingerprint(payload):
        raise AppError(409, "idempotency_conflict", "相同 Idempotency-Key 已用于不同请求")
    record.response_status = status_code
    record.response_json = jsonable_encoder(response)
    record.expires_at = utc_now() + timedelta(hours=24)
