"""异步任务 schema."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from services.data_source_configuration import public_data_source_configuration


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel):
    items: list[Any]
    next_cursor: str | None = None



class JobCreate(BaseModel):
    job_type: str = Field(min_length=1, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)
    scheduled_at: datetime | None = None


class JobOut(ORMModel):
    id: uuid.UUID
    job_type: str
    status: str
    payload_json: dict[str, Any]
    scope_snapshot_json: dict[str, Any]
    result_json: dict[str, Any]
    error_code: str | None
    error_message: str | None
    attempt_count: int
    max_attempts: int
    scheduled_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    dead_lettered_at: datetime | None
    created_at: datetime
