"""认证 schema."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, computed_field, field_validator, model_validator

from core.data_source_configuration import public_data_source_configuration


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel):
    items: list[Any]
    next_cursor: str | None = None



class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized.count("@") != 1 or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("invalid email")
        return normalized


class LoginResponse(BaseModel):
    user: UserOut
    csrf_token: str
    expires_at: datetime
    app_env: str
    app_mode: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=10, max_length=256)


class MeResponse(BaseModel):
    user: UserOut
    enterprise: EnterpriseOut
    scopes: list[OrganizationUnitOut]
    csrf_token: str
    app_env: str
    app_mode: str


class SessionOut(ORMModel):
    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    ip_address: str | None
    user_agent: str | None
    is_current: bool = False


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=12000)
    file_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    organization_scope: OrganizationScopeInput | None = None
    model_id: str | None = Field(default=None, min_length=1, max_length=100)


class MessageOut(ORMModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    content_json: dict[str, Any]
    sequence: int
    status: str
    requested_model_id: str | None
    model_name: str | None
    output_contract_version: str | None
    output_template_id: str | None
    source_data_as_of: datetime | None
    created_at: datetime

    @computed_field  # type: ignore[misc]
    @property
    def tool_steps(self) -> list[dict[str, Any]]:
        """从 ``content_json.tool_steps`` 派生，便于前端在刷新会话后
        仍能看到本轮的工具调用轨迹。

        写入侧在 ``conversation_service.save_assistant_message`` 完成；
        读出侧在本 schema 派生。这样 SSE 流与历史回放走同一条字段。
        """
        if not isinstance(self.content_json, dict):
            return []
        steps = self.content_json.get("tool_steps")
        return list(steps) if isinstance(steps, list) else []


class MemoryCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=20000)
    kind: str = Field(default="preference", max_length=50)
    organization_unit_id: uuid.UUID | None = None
    source_conversation_id: uuid.UUID | None = None


class MemoryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    content: str | None = Field(default=None, min_length=1, max_length=20000)
    status: Literal["active", "disabled", "deleted"] | None = None


class MemoryOut(ORMModel):
    id: uuid.UUID
    title: str
    content: str
    kind: str
    organization_unit_id: uuid.UUID | None
    source_conversation_id: uuid.UUID | None
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class MessageEvidenceOut(ORMModel):
    id: uuid.UUID
    evidence_key: str
    domain: str
    title: str
    value_json: dict[str, Any]
    source_type: str
    source_display_name: str
    source_data_as_of: datetime
    dataset_version: str | None
    scope_json: dict[str, Any]
    query_json: dict[str, Any]
    row_references_json: list[dict[str, Any]]
    created_at: datetime
