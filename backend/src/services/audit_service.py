"""Audit service.

Follows the anspire service pattern: a class that receives the database
session in the constructor and exposes business methods.

This is a thin wrapper around :func:`repositories.audit.record_audit` that
demonstrates the class-based service convention. New code should prefer
``AuditService(db).record(request, action, ...)`` over the module-level
``record_audit(db, request, ...)`` function; both are equivalent.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuditEvent, User, UserSession
from repositories.audit import client_ip, record_audit


class AuditService:
    """Service for recording audit events.

    Mirrors the anspire ``Service`` convention: stateless business logic
    layered on top of a SQLAlchemy ``AsyncSession``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        request: Request,
        action: str,
        *,
        actor: User | None = None,
        session: UserSession | None = None,
        target_type: str | None = None,
        target_id: uuid.UUID | str | None = None,
        outcome: str = "success",
        failure_reason_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Record an audit event for the current request."""
        return await record_audit(
            self._session,
            request,
            action,
            actor=actor,
            session=session,
            target_type=target_type,
            target_id=target_id,
            outcome=outcome,
            failure_reason_code=failure_reason_code,
            metadata=metadata,
        )

    @staticmethod
    def client_ip(request: Request) -> str | None:
        """Extract the client IP from a request."""
        return client_ip(request)
