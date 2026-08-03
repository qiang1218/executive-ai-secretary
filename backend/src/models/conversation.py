"""会话、消息、Harness 运行模型."""

from __future__ import annotations

from .base import *  # noqa: F401,F403  Base / JSONType / new_uuid / mixins / sqlalchemy symbols


class Conversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversation_enterprise_owner", "enterprise_id", "owner_user_id"),
        Index("ix_conversation_enterprise_org", "enterprise_id", "organization_unit_id"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    organization_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organization_units.id", ondelete="SET NULL")
    )
    scope_mode: Mapped[str] = mapped_column(
        String(32), default="all_authorized", nullable=False
    )
    selected_model_id: Mapped[str | None] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(300), nullable=False, default="新会话")
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    pinned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)


class ConversationOrganizationScope(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "conversation_organization_scopes"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "organization_unit_id",
            name="uq_conversation_organization_scope",
        ),
        Index("ix_conversation_scope_conversation", "conversation_id"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    organization_unit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization_units.id", ondelete="CASCADE"), nullable=False
    )


class ProjectConversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "project_conversations"
    __table_args__ = (
        UniqueConstraint("project_id", "conversation_id", name="uq_project_conversation"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )


class Message(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence", name="uq_message_conversation_sequence"),
        Index("ix_message_conversation_created", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="completed", nullable=False)
    requested_model_id: Mapped[str | None] = mapped_column(String(100))
    model_name: Mapped[str | None] = mapped_column(String(160))
    output_contract_version: Mapped[str | None] = mapped_column(String(32))
    output_template_id: Mapped[str | None] = mapped_column(String(64))
    source_data_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MessageRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "message_runs"

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="queued", nullable=False)
    provider: Mapped[str | None] = mapped_column(String(80))
    requested_model_id: Mapped[str | None] = mapped_column(String(100))
    model_name: Mapped[str | None] = mapped_column(String(160))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)


class MessageRoute(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "message_routes"
    __table_args__ = (UniqueConstraint("message_id", name="uq_message_route_message"),)

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    route: Mapped[str] = mapped_column(String(40), nullable=False)
    profile: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)
    rewritten_query: Mapped[str] = mapped_column(Text, nullable=False)
    query_spec_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    harness_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("harness_config_versions.id", ondelete="SET NULL"), index=True
    )
    route_source: Mapped[str] = mapped_column(String(40), default="hermes", nullable=False)
    matched_rule_id: Mapped[str | None] = mapped_column(String(100))
    scope_status: Mapped[str] = mapped_column(String(40), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String(160))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HarnessStageRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "harness_stage_runs"
    __table_args__ = (
        Index("ix_harness_stage_message_created", "message_id", "created_at"),
        Index("ix_harness_stage_enterprise_created", "enterprise_id", "created_at"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    harness_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("harness_config_versions.id", ondelete="SET NULL"), index=True
    )
    stage: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    route_source: Mapped[str | None] = mapped_column(String(40))
    model_name: Mapped[str | None] = mapped_column(String(160))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    tool_names_json: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))


class HarnessDiagnosticGrant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "harness_diagnostic_grants"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_harness_diagnostic_message"),
        Index("ix_harness_diagnostic_expiry", "expires_at", "revoked_at"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Clarification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "clarifications"
    __table_args__ = (Index("ix_clarification_conversation_status", "conversation_id", "status"),)

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONType, default=list, nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    selected_value: Mapped[str | None] = mapped_column(String(500))
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MessageEvidence(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "message_evidence"
    __table_args__ = (
        UniqueConstraint("message_id", "evidence_key", name="uq_message_evidence_key"),
        Index("ix_message_evidence_message", "message_id", "created_at"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_key: Mapped[str] = mapped_column(String(80), nullable=False)
    domain: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    metric_code: Mapped[str | None] = mapped_column(String(100))
    metric_value: Mapped[float | None] = mapped_column(Numeric(24, 6))
    metric_unit: Mapped[str | None] = mapped_column(String(40))
    value_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_data_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dataset_version: Mapped[str | None] = mapped_column(String(80))
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    query_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    row_references_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONType, default=list, nullable=False
    )
