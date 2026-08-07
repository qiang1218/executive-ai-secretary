"""Harness 配置与仿真 schema."""

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



class HarnessConfigOut(BaseModel):
    id: uuid.UUID
    version: int
    schema_version: str
    config_hash: str
    config: dict[str, Any]
    safety_kernel: dict[str, Any]
    activated_at: datetime
    updated_at: datetime


class HarnessConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_version: int = Field(ge=1)
    config: dict[str, Any]


class HarnessVersionOut(BaseModel):
    id: uuid.UUID
    version: int
    config_hash: str
    is_active: bool
    source_version_id: uuid.UUID | None
    created_by_user_id: uuid.UUID | None
    activated_at: datetime
    created_at: datetime


class HarnessSimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=12000)
    config: dict[str, Any] | None = None
    organization_scope: dict[str, Any] | None = None
    forced_rule_id: str | None = Field(
        default=None,
        max_length=64,
        description="强制走该 fast_rule,跳过 match_fast_rule 自动选择;仅供 admin 调试。",
    )


class HarnessSimulationOut(BaseModel):
    route: Literal["data", "general", "clarification"]
    route_source: Literal["fast_rule", "hermes", "validation", "forced"]
    matched_rule_id: str | None
    candidate_tools: list[str]
    query_spec: dict[str, Any]
    validation_issues: list[str]
    config_hash: str
    skipped_rule_ids: list[str] = Field(
        default_factory=list,
        description="本次匹配中被排除的 fast_rule id 列表。",
    )


class HarnessMetricsOut(BaseModel):
    window_days: int
    message_count: int
    intent_accuracy_sample_size: int
    structured_output_rate: float
    tool_success_rate: float
    route_counts: dict[str, int]
    stage_latency_p95_ms: dict[str, int]
    rule_hit_counts: dict[str, int] = Field(
        default_factory=dict,
        description="各 fast_rule 的命中次数;key = matched_rule_id,仅统计 route_source=fast_rule 的记录。",
    )
    last_rule_hit_at: dict[str, datetime] = Field(
        default_factory=dict,
        description="各 fast_rule 最近一次命中时间;key = matched_rule_id。",
    )


class HarnessTraceOut(BaseModel):
    message_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    route: str | None
    route_source: str | None
    query_spec_summary: dict[str, Any]
    harness_version: int | None
    organization_unit_count: int
    tools: list[str]
    stages: list[dict[str, Any]]
    diagnostic_shared_until: datetime | None = None
    shared_content: dict[str, Any] | None = None
