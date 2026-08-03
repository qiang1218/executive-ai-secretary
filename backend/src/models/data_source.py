"""数据源、调度、同步与领域状态模型."""

from __future__ import annotations

from .base import *  # noqa: F401,F403  Base / JSONType / new_uuid / mixins / sqlalchemy symbols


class DataSource(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "data_sources"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "key", name="uq_data_source_enterprise_key"),
        Index("ix_data_source_enterprise_enabled", "enterprise_id", "is_enabled"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), default="3.0", nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(
        JSONType, default=dict, nullable=False
    )
    secret_reference_key: Mapped[str | None] = mapped_column(String(200))
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_status: Mapped[str | None] = mapped_column(String(32))
    last_test_error: Mapped[str | None] = mapped_column(Text)


class ScheduledTask(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "scheduled_tasks"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "key", name="uq_scheduled_task_enterprise_key"),
        Index("ix_scheduled_task_due", "is_enabled", "next_run_at"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_sources.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(80), default="0 2 * * *", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai", nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_enqueued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    configuration_json: Mapped[dict[str, Any]] = mapped_column(
        JSONType, default=dict, nullable=False
    )


class ScheduleRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "schedule_runs"
    __table_args__ = (
        UniqueConstraint("scheduled_task_id", "window_key", name="uq_schedule_run_window"),
        Index("ix_schedule_run_status", "status", "created_at"),
    )

    scheduled_task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scheduled_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), index=True
    )
    window_key: Mapped[str] = mapped_column(String(160), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(32), default="schedule", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="enqueued", nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    enqueued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)


class DataSyncRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "data_sync_runs"
    __table_args__ = (
        Index("ix_data_sync_enterprise_started", "enterprise_id", "started_at"),
        Index("ix_data_sync_source_status", "data_source_id", "status"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), index=True
    )
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    dataset_version: Mapped[str | None] = mapped_column(String(80))
    source_schema_version: Mapped[str | None] = mapped_column(String(32))
    source_batch_id: Mapped[str | None] = mapped_column(String(160))
    source_data_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_read: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_written: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_schema_hashes_json: Mapped[dict[str, str]] = mapped_column(
        JSONType, default=dict, nullable=False
    )
    source_record_counts_json: Mapped[dict[str, int]] = mapped_column(
        JSONType, default=dict, nullable=False
    )
    source_content_hashes_json: Mapped[dict[str, str]] = mapped_column(
        JSONType, default=dict, nullable=False
    )
    cross_table_validation_json: Mapped[dict[str, Any]] = mapped_column(
        JSONType, default=dict, nullable=False
    )
    activation_mode: Mapped[str] = mapped_column(
        String(40), default="all_three_atomic", nullable=False
    )
    atomic_activation_status: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False
    )
    experience_weight_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("opportunity_experience_weight_policies.id", ondelete="SET NULL"),
        index=True,
    )
    activation_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    domain_results_json: Mapped[dict[str, Any]] = mapped_column(
        JSONType, default=dict, nullable=False
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)


class DataDomainStatus(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "data_domain_status"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "domain", name="uq_data_domain_enterprise"),
        Index("ix_data_domain_status_enterprise", "enterprise_id", "status"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="never_synced", nullable=False)
    active_sync_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_sync_runs.id", ondelete="SET NULL")
    )
    previous_sync_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_sync_runs.id", ondelete="SET NULL")
    )
    source_data_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dataset_version: Mapped[str | None] = mapped_column(String(80))
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    current_source_batch_id: Mapped[str | None] = mapped_column(String(160))
    contract_version: Mapped[str | None] = mapped_column(String(32))
    status_reason: Mapped[str | None] = mapped_column(Text)
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    last_error_message: Mapped[str | None] = mapped_column(Text)


class SourceCheckpoint(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "source_checkpoints"
    __table_args__ = (
        UniqueConstraint("data_source_id", "domain", name="uq_source_checkpoint_domain"),
    )

    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(String(40), nullable=False)
    cursor_value: Mapped[str | None] = mapped_column(String(500))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_batch_id: Mapped[str | None] = mapped_column(String(160))
    checksum: Mapped[str | None] = mapped_column(String(64))
