"""会话、消息、澄清与诊断 schema."""

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



class ConversationCreate(BaseModel):
    title: str = Field(default="新会话", min_length=1, max_length=300)
    organization_unit_id: uuid.UUID | None = None
    organization_scope: OrganizationScopeInput | None = None
    project_id: uuid.UUID | None = None
    model_id: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="before")
    @classmethod
    def reject_mixed_scope_fields(cls, value):
        if (
            isinstance(value, dict)
            and "organization_scope" in value
            and "organization_unit_id" in value
        ):
            raise ValueError("organization_scope and organization_unit_id cannot be used together")
        return value


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    organization_unit_id: uuid.UUID | None = None
    organization_scope: OrganizationScopeInput | None = None
    status: Literal["active", "archived"] | None = None
    model_id: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="before")
    @classmethod
    def reject_mixed_scope_fields(cls, value):
        if (
            isinstance(value, dict)
            and "organization_scope" in value
            and "organization_unit_id" in value
        ):
            raise ValueError("organization_scope and organization_unit_id cannot be used together")
        return value


class ConversationOut(ORMModel):
    id: uuid.UUID
    title: str
    organization_unit_id: uuid.UUID | None
    organization_scope: OrganizationScopeOut
    project_id: uuid.UUID | None = None
    selected_model_id: str | None = None
    status: str
    pinned_at: datetime | None
    archived_at: datetime | None
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConversationProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID | None


class ClarificationResolve(BaseModel):
    value: str = Field(min_length=1, max_length=500)


class ClarificationOut(ORMModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    question: str
    options_json: list[dict[str, Any]]
    status: str
    selected_value: str | None
    resolved_at: datetime | None


class DiagnosticShareOut(BaseModel):
    message_id: uuid.UUID
    expires_at: datetime
    revoked_at: datetime | None
