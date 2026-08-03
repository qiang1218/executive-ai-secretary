"""数仓维度表与事实表模型."""

from __future__ import annotations

from .base import *  # noqa: F401,F403  Base / JSONType / new_uuid / mixins / sqlalchemy symbols


class DimPerson(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "dim_person"
    __table_args__ = (
        UniqueConstraint(
            "enterprise_id", "data_source_id", "source_record_id", name="uq_dim_person_source"
        ),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False
    )
    organization_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organization_units.id", ondelete="SET NULL"), index=True
    )
    source_record_id: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(String(200))
    identity_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    role_types_json: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    role_title: Mapped[str | None] = mapped_column(String(160))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source_system: Mapped[str] = mapped_column(String(80), nullable=False)
    dataset_version: Mapped[str | None] = mapped_column(String(80))
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DimCustomer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "dim_customer"
    __table_args__ = (
        UniqueConstraint(
            "enterprise_id", "data_source_id", "source_record_id", name="uq_dim_customer_source"
        ),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False
    )
    organization_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organization_units.id", ondelete="SET NULL"), index=True
    )
    owner_person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dim_person.id", ondelete="SET NULL")
    )
    source_record_id: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(240), nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(String(240))
    identity_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    aliases_json: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    customer_value_level: Mapped[str | None] = mapped_column(String(40))
    industry: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120))
    source_system: Mapped[str] = mapped_column(String(80), nullable=False)
    dataset_version: Mapped[str | None] = mapped_column(String(80))
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FactOpportunity(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "fact_opportunity"
    __table_args__ = (
        UniqueConstraint("sync_run_id", "source_record_id", name="uq_fact_opportunity_run_source"),
        Index(
            "ix_fact_opportunity_scope_current",
            "enterprise_id",
            "organization_unit_id",
            "is_current",
        ),
        Index("ix_fact_opportunity_stage_close", "stage", "expected_close_date"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False
    )
    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sync_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_unit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization_units.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dim_customer.id", ondelete="SET NULL")
    )
    owner_person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dim_person.id", ondelete="SET NULL")
    )
    source_record_id: Mapped[str] = mapped_column(String(160), nullable=False)
    upstream_record_id: Mapped[str | None] = mapped_column(String(160))
    opportunity_code: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    stage: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    stage_label: Mapped[str | None] = mapped_column(String(80))
    status_code: Mapped[str | None] = mapped_column(String(40), index=True)
    reliability_level: Mapped[str | None] = mapped_column(String(24), index=True)
    customer_value_level: Mapped[str | None] = mapped_column(String(40))
    industry: Mapped[str | None] = mapped_column(String(120))
    probability: Mapped[int | None] = mapped_column(Integer)
    expected_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    signed_amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    expected_gross_profit: Mapped[float | None] = mapped_column(Numeric(18, 2))
    created_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_close_date: Mapped[date] = mapped_column(Date, nullable=False)
    closed_date: Mapped[date | None] = mapped_column(Date)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latest_progress: Mapped[str | None] = mapped_column(Text)
    source_system: Mapped[str] = mapped_column(String(80), nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dataset_version: Mapped[str | None] = mapped_column(String(80))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class FactOpportunityParticipant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "fact_opportunity_participant"
    __table_args__ = (
        UniqueConstraint(
            "opportunity_id",
            "person_id",
            "participant_role",
            name="uq_fact_opportunity_participant_role",
        ),
        Index(
            "ix_fact_opportunity_participant_lookup",
            "enterprise_id",
            "participant_role",
            "person_id",
        ),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sync_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fact_opportunity.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dim_person.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    participant_role: Mapped[str] = mapped_column(String(32), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class FactOpportunityProduct(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "fact_opportunity_product"
    __table_args__ = (
        UniqueConstraint(
            "opportunity_id",
            "normalized_product_name",
            name="uq_fact_opportunity_product_name",
        ),
        Index(
            "ix_fact_opportunity_product_lookup",
            "enterprise_id",
            "normalized_product_name",
        ),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sync_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fact_opportunity.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_name: Mapped[str] = mapped_column(String(240), nullable=False)
    normalized_product_name: Mapped[str] = mapped_column(String(240), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class FactDelivery(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "fact_delivery"
    __table_args__ = (
        UniqueConstraint("sync_run_id", "source_record_id", name="uq_fact_delivery_run_source"),
        Index(
            "ix_fact_delivery_scope_current", "enterprise_id", "organization_unit_id", "is_current"
        ),
        Index("ix_fact_delivery_risk_status", "risk_level", "status"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False
    )
    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sync_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_unit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization_units.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dim_customer.id", ondelete="SET NULL")
    )
    manager_person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dim_person.id", ondelete="SET NULL")
    )
    delivery_owner_person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dim_person.id", ondelete="SET NULL")
    )
    opportunity_fact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("fact_opportunity.id", ondelete="CASCADE"), index=True
    )
    source_record_id: Mapped[str] = mapped_column(String(160), nullable=False)
    opportunity_source_record_id: Mapped[str] = mapped_column(String(160), nullable=False)
    project_code: Mapped[str] = mapped_column(String(120), nullable=False)
    project_name: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(40), nullable=False)
    completion_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    contract_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    recognized_revenue: Mapped[float | None] = mapped_column(Numeric(18, 2))
    gross_margin_rate: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    planned_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    planned_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_start_date: Mapped[date | None] = mapped_column(Date)
    actual_end_date: Mapped[date | None] = mapped_column(Date)
    current_milestone: Mapped[str | None] = mapped_column(String(200))
    delay_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latest_progress: Mapped[str | None] = mapped_column(Text)
    source_system: Mapped[str] = mapped_column(String(80), nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dataset_version: Mapped[str | None] = mapped_column(String(80))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class FactFinanceCollection(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "fact_finance_collection"
    __table_args__ = (
        UniqueConstraint("sync_run_id", "source_record_id", name="uq_fact_collection_run_source"),
        Index(
            "ix_fact_collection_scope_current",
            "enterprise_id",
            "organization_unit_id",
            "is_current",
        ),
        Index("ix_fact_collection_due_status", "planned_collection_date", "status"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False
    )
    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sync_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_unit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization_units.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dim_customer.id", ondelete="SET NULL")
    )
    opportunity_fact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("fact_opportunity.id", ondelete="CASCADE"), index=True
    )
    delivery_fact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("fact_delivery.id", ondelete="CASCADE"), index=True
    )
    collection_owner_person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dim_person.id", ondelete="SET NULL")
    )
    source_record_id: Mapped[str] = mapped_column(String(160), nullable=False)
    project_source_record_id: Mapped[str] = mapped_column(String(160), nullable=False)
    invoice_amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    receivable_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    collected_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    outstanding_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    planned_collection_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_collection_date: Mapped[date | None] = mapped_column(Date)
    overdue_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    aging_bucket: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    payment_type: Mapped[str | None] = mapped_column(String(80))
    payment_milestone: Mapped[str | None] = mapped_column(String(160))
    invoice_status: Mapped[str | None] = mapped_column(String(40))
    invoice_number: Mapped[str | None] = mapped_column(String(120))
    latest_follow_up: Mapped[str | None] = mapped_column(Text)
    source_system: Mapped[str] = mapped_column(String(80), nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dataset_version: Mapped[str | None] = mapped_column(String(80))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class FactTarget(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "fact_target"
    __table_args__ = (
        UniqueConstraint("sync_run_id", "source_record_id", name="uq_fact_target_run_source"),
        Index(
            "ix_fact_target_scope_current", "enterprise_id", "organization_unit_id", "is_current"
        ),
        Index("ix_fact_target_metric_period", "metric_code", "period_start", "period_end"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False
    )
    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sync_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_unit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization_units.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_record_id: Mapped[str] = mapped_column(String(160), nullable=False)
    metric_code: Mapped[str] = mapped_column(String(80), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(160), nullable=False)
    period_type: Mapped[str] = mapped_column(String(32), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    target_value: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    source_system: Mapped[str] = mapped_column(String(80), nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dataset_version: Mapped[str | None] = mapped_column(String(80))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class DailySnapshot(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "daily_snapshot"
    __table_args__ = (
        Index(
            "uq_daily_snapshot_org_date_batch",
            "enterprise_id",
            "organization_unit_id",
            "snapshot_date",
            text("coalesce(source_batch_id, '')"),
            unique=True,
            postgresql_where=text("organization_unit_id IS NOT NULL"),
            sqlite_where=text("organization_unit_id IS NOT NULL"),
        ),
        Index(
            "uq_daily_snapshot_enterprise_date_batch",
            "enterprise_id",
            "snapshot_date",
            text("coalesce(source_batch_id, '')"),
            unique=True,
            postgresql_where=text("organization_unit_id IS NULL"),
            sqlite_where=text("organization_unit_id IS NULL"),
        ),
        Index("ix_daily_snapshot_enterprise_date", "enterprise_id", "snapshot_date"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organization_units.id", ondelete="CASCADE"), index=True
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_data_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dataset_version: Mapped[str | None] = mapped_column(String(80))
    source_batch_id: Mapped[str | None] = mapped_column(String(160), index=True)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    anomalies_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONType, default=list, nullable=False
    )
