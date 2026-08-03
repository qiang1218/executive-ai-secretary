"""配置、模型授权、MCP 工具与 Harness 版本模型."""

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


class AppConfig(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "app_configs"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "key", name="uq_app_config_enterprise_key"),
    )

    enterprise_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    is_secret_reference: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SecretReference(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "secret_references"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "key", name="uq_secret_ref_enterprise_key"),
    )

    enterprise_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    reference: Mapped[str] = mapped_column(String(500), nullable=False)


class ModelProviderConfig(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "model_provider_configs"
    __table_args__ = (
        UniqueConstraint("enterprise_id", name="uq_model_provider_enterprise"),
        Index("ix_model_provider_enterprise_enabled", "enterprise_id", "is_enabled"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), default="anspire", nullable=False)
    endpoint_url: Mapped[str] = mapped_column(String(300), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key_ciphertext: Mapped[str | None] = mapped_column(Text)
    api_key_nonce: Mapped[str | None] = mapped_column(String(64))
    api_key_hint: Mapped[str | None] = mapped_column(String(16))
    encryption_key_version: Mapped[str] = mapped_column(String(64), default="v1", nullable=False)
    credential_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_status: Mapped[str | None] = mapped_column(String(32))
    last_test_latency_ms: Mapped[int | None] = mapped_column(Integer)
    last_test_error: Mapped[str | None] = mapped_column(Text)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class EnterpriseModelAuthorization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "enterprise_model_authorizations"
    __table_args__ = (
        UniqueConstraint(
            "enterprise_id", "model_id", name="uq_enterprise_model_authorization"
        ),
        Index(
            "ix_enterprise_model_authorization_state",
            "enterprise_id",
            "is_authorized",
            "is_default",
        ),
        Index(
            "uq_enterprise_default_model",
            "enterprise_id",
            unique=True,
            postgresql_where=text("is_default"),
            sqlite_where=text("is_default = 1"),
        ),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    test_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    tested_credential_version: Mapped[int | None] = mapped_column(Integer)
    is_authorized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_latency_ms: Mapped[int | None] = mapped_column(Integer)
    last_test_error: Mapped[str | None] = mapped_column(Text)
    authorized_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class McpToolConfig(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "mcp_tool_configs"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "tool_name", name="uq_mcp_tool_enterprise_name"),
        Index("ix_mcp_tool_enterprise_enabled", "enterprise_id", "is_enabled"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    planner_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    max_rows: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    operator_note: Mapped[str | None] = mapped_column(String(500))
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class McpToolDefinition(UUIDMixin, TimestampMixin, Base):
    """Enterprise-owned declarative tools composed from audited built-in tools."""

    __tablename__ = "mcp_tool_definitions"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "tool_name", name="uq_mcp_definition_enterprise_name"),
        Index("ix_mcp_definition_enterprise_type", "enterprise_id", "tool_type"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    tool_type: Mapped[str] = mapped_column(String(32), default="composite", nullable=False)
    component_tools_json: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    domains_json: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class HarnessConfigVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "harness_config_versions"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "version", name="uq_harness_enterprise_version"),
        Index("ix_harness_enterprise_active", "enterprise_id", "is_active"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), default="3.0", nullable=False)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("harness_config_versions.id", ondelete="SET NULL")
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OpportunityExperienceWeightPolicy(UUIDMixin, TimestampMixin, Base):
    """Versioned, auditable experience weights used for pipeline forecasting.

    These values are an operating convention rather than a claim about the
    statistical probability of winning an opportunity.  Only one policy may
    be active for an enterprise at a time.
    """

    __tablename__ = "opportunity_experience_weight_policies"
    __table_args__ = (
        UniqueConstraint(
            "enterprise_id",
            "version",
            name="uq_opportunity_weight_policy_enterprise_version",
        ),
        Index(
            "ix_opportunity_weight_policy_enterprise_active",
            "enterprise_id",
            "is_active",
        ),
        Index(
            "uq_opportunity_weight_policy_one_active",
            "enterprise_id",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active = 1"),
        ),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    weights_json: Mapped[dict[str, float]] = mapped_column(
        JSONType,
        default=lambda: {"high": 0.20, "medium": 0.10, "low": 0.05},
        nullable=False,
    )
    observation_windows_json: Mapped[list[int]] = mapped_column(
        JSONType, default=lambda: [30, 60, 90], nullable=False
    )
    observation_window_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(Text)
