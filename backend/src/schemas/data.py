"""数据域与每日简报 schema."""

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



class DataDomainStatusOut(ORMModel):
    domain: str
    status: str
    source_data_as_of: datetime | None
    last_success_at: datetime | None
    record_count: int
    dataset_version: str | None
    source_type: str
    source_display_name: str
    last_error_code: str | None
    last_error_message: str | None


class DataCapabilitiesOut(BaseModel):
    source_kind: str
    source_label: str
    organization_unit_ids: list[uuid.UUID]
    capabilities: dict[str, bool]
    domains: list[DataDomainStatusOut]
    overall_status: str
    generated_at: datetime


class DailyBriefItemOut(BaseModel):
    rule_id: Literal["delivery_delayed", "collection_overdue"]
    domain: Literal["delivery", "collection"]
    severity: Literal["attention"] = "attention"
    title: str
    detail: str
    affected_count: int = Field(ge=0)
    amount: float | None = Field(default=None, ge=0)
    unit: Literal["元"] | None = None


class DailyBriefDomainReadinessOut(BaseModel):
    domain: Literal["opportunity", "delivery", "collection", "target"]
    readiness: str
    data_as_of: datetime | None
    record_count: int = Field(ge=0)


class DailyBriefOut(BaseModel):
    brief_date: date | None
    data_as_of: datetime | None
    source_batch_id: str | None
    readiness: Literal["ready", "stale", "partial", "unavailable"]
    attention_count: int = Field(ge=0)
    items: list[DailyBriefItemOut]
    domains: list[DailyBriefDomainReadinessOut]
    organization_unit_ids: list[uuid.UUID]
    uses_enterprise_snapshot: bool
    generated_at: datetime


class DataOperationsV3OverviewOut(BaseModel):
    sources: list[DataSourceOperationsStatusOut]
    experience_weight_policy: OpportunityExperienceWeightPolicyOut
    generated_at: datetime
