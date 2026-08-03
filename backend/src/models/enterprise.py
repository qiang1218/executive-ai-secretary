"""企业与组织单元模型."""

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


class Enterprise(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "enterprises"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    settings_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)


class OrganizationUnit(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organization_units"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "code", name="uq_org_unit_enterprise_code"),
        Index("ix_org_unit_enterprise_parent", "enterprise_id", "parent_id"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organization_units.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    unit_type: Mapped[str] = mapped_column(String(40), default="division", nullable=False)
    enabled_for_analysis: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    data_connected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)

    parent: Mapped[OrganizationUnit | None] = relationship(remote_side="OrganizationUnit.id")


class DataScopeGrant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "data_scope_grants"
    __table_args__ = (
        UniqueConstraint("user_id", "scope_kind", "organization_unit_id", name="uq_user_scope"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="organization_unit")
    organization_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organization_units.id", ondelete="CASCADE"), nullable=True
    )
    can_read: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
