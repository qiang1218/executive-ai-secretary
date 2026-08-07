"""数据源、同步与调度 schema."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from core.data_source_configuration import public_data_source_configuration


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel):
    items: list[Any]
    next_cursor: str | None = None



class DataSourceOut(ORMModel):
    id: uuid.UUID
    key: str
    display_name: str
    source_type: str
    schema_version: str
    is_enabled: bool
    configuration_json: dict[str, Any]
    last_tested_at: datetime | None
    last_test_status: str | None
    last_test_error: str | None
    created_at: datetime
    updated_at: datetime

    @field_validator("configuration_json", mode="before")
    @classmethod
    def redact_configuration(cls, value: object) -> dict[str, Any]:
        return public_data_source_configuration(value)


class DataSourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    is_enabled: bool | None = None
    configuration_json: dict[str, Any] | None = None


class DataSourceTestOut(BaseModel):
    ok: bool
    schema_version: str
    database_version: str
    current_user: str
    read_only: bool
    tls_active: bool
    latest_batch_id: str
    source_data_as_of: datetime
    duration_ms: int


class DataSyncRunOut(ORMModel):
    id: uuid.UUID
    data_source_id: uuid.UUID
    job_id: uuid.UUID | None
    trigger_type: str
    status: str
    dataset_version: str | None
    source_schema_version: str | None
    source_batch_id: str | None
    source_data_as_of: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    records_read: int
    records_written: int
    records_rejected: int
    source_schema_hashes_json: dict[str, str]
    source_record_counts_json: dict[str, int]
    source_content_hashes_json: dict[str, str]
    cross_table_validation_json: dict[str, Any]
    activation_mode: str
    atomic_activation_status: str
    experience_weight_policy_id: uuid.UUID | None
    activation_started_at: datetime | None
    activated_at: datetime | None
    domain_results_json: dict[str, Any]
    error_code: str | None
    error_message: str | None
    created_at: datetime


class FeishuFieldBindingOut(BaseModel):
    field_id: str
    field_name: str
    field_type: int
    required: bool


class FeishuTableBindingStatusOut(BaseModel):
    domain: Literal["opportunity", "delivery", "collection"]
    display_name: str
    configured: bool
    app_token_masked: str | None
    table_id: str | None
    fields: list[FeishuFieldBindingOut]
    schema_hash: str | None
    content_hash: str | None
    record_count: int | None
    validation_status: Literal["not_configured", "configured", "validated", "rejected"]
    last_validated_at: datetime | None
    warnings: list[str] = Field(default_factory=list)


class DataSourceOperationsStatusOut(BaseModel):
    source_id: uuid.UUID
    display_name: str
    source_type: str
    schema_version: str
    is_enabled: bool
    activation_policy: str
    bindings: list[FeishuTableBindingStatusOut]
    latest_successful_run: DataSyncRunOut | None
    latest_rejected_run: DataSyncRunOut | None


class ExperienceWeightValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    high: float = Field(ge=0, le=1)
    medium: float = Field(ge=0, le=1)
    low: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_order(self):
        if not self.high >= self.medium >= self.low:
            raise ValueError("经验权重必须满足高 ≥ 中 ≥ 低")
        return self


class OpportunityExperienceWeightPolicyOut(ORMModel):
    id: uuid.UUID
    version: int
    label: str
    weights_json: dict[str, float]
    observation_windows_json: list[int]
    observation_window_days: int
    is_active: bool
    activated_at: datetime
    notes: str | None
    created_at: datetime
    updated_at: datetime


class OpportunityExperienceWeightPolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_version: int = Field(ge=1)
    weights: ExperienceWeightValues
    label: str | None = Field(default=None, min_length=1, max_length=160)
    notes: str | None = Field(default=None, max_length=1000)


class ScheduledTaskOut(ORMModel):
    id: uuid.UUID
    data_source_id: uuid.UUID | None
    key: str
    task_type: str
    cron_expression: str
    timezone: str
    is_enabled: bool
    next_run_at: datetime | None
    last_enqueued_at: datetime | None
    configuration_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ManualRunOut(BaseModel):
    job_id: uuid.UUID
    status: str = "queued"
