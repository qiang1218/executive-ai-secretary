"""审计 schema."""

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



class AuditEventOut(ORMModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    target_type: str | None
    target_id: str | None
    outcome: str
    environment: str
    actor_role: str | None
    failure_reason_code: str | None
    request_id: str | None
    metadata_json: dict[str, Any]
    scope_summary_json: dict[str, Any]
    chain_scope: str | None
    chain_sequence: int | None
    previous_integrity_hash: str | None
    integrity_hash: str
    created_at: datetime


class AuditVerification(BaseModel):
    valid: bool
    checked_count: int
    invalid_event_ids: list[uuid.UUID]
    errors: list[str] = Field(default_factory=list)
