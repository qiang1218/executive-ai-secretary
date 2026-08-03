"""审计链与事件模型."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from db.session import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)


class AuditChainHead(Base):
    """Mutable, HMAC-protected anchor for one enterprise audit chain."""

    __tablename__ = "audit_chain_heads"

    chain_scope: Mapped[str] = mapped_column(String(64), primary_key=True)
    legacy_event_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    legacy_root_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    last_sequence: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    last_integrity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    anchor_key_version: Mapped[str | None] = mapped_column(String(64))
    anchor_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AuditEvent(UUIDMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_enterprise_created", "enterprise_id", "created_at"),
        Index("ix_audit_actor_created", "actor_user_id", "created_at"),
        UniqueConstraint("chain_scope", "chain_sequence", name="uq_audit_chain_sequence"),
    )

    enterprise_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("enterprises.id", ondelete="SET NULL")
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_sessions.id", ondelete="SET NULL")
    )
    environment: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_role: Mapped[str | None] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(80))
    target_id: Mapped[str | None] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(24), default="success", nullable=False)
    failure_reason_code: Mapped[str | None] = mapped_column(String(100))
    request_id: Mapped[str | None] = mapped_column(String(80))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    scope_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSONType, default=dict, nullable=False
    )
    chain_scope: Mapped[str | None] = mapped_column(String(64))
    chain_sequence: Mapped[int | None] = mapped_column(BigInteger)
    previous_integrity_hash: Mapped[str | None] = mapped_column(String(64))
    audit_key_version: Mapped[str | None] = mapped_column(String(64))
    integrity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IdempotencyRecord(UUIDMixin, Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "method", "path", "idempotency_key", name="uq_idempotency_scope"
        ),
        Index("ix_idempotency_expires", "expires_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    method: Mapped[str] = mapped_column(String(12), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


@event.listens_for(AuditEvent, "before_insert")
def sign_audit_event(_mapper, connection, target: "AuditEvent") -> None:
    # Imported lazily to keep the model module free of settings initialization cycles.
    from repositories.audit_integrity import prepare_audit_event

    prepare_audit_event(connection, target)
