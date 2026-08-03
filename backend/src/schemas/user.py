"""用户、偏好与高管画像 schema."""

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



class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    display_name: str
    preferred_name: str | None
    role: str
    locale: str
    timezone: str
    memory_enabled: bool
    password_change_required: bool


class UserPreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_enabled: bool


class ExecutivePersonalProfileOut(BaseModel):
    salutation: str
    amount_unit: Literal["yuan", "wan", "yi"]
    response_style: Literal["concise", "balanced", "detailed"]
    locale: Literal["zh-CN", "zh-TW", "en-US"]
    memory_enabled: bool
    version: int
    updated_at: datetime | None


class ExecutivePersonalProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    salutation: str = Field(min_length=1, max_length=40)
    amount_unit: Literal["yuan", "wan", "yi"] = "wan"
    response_style: Literal["concise", "balanced", "detailed"] = "balanced"
    locale: Literal["zh-CN", "zh-TW", "en-US"] = "zh-CN"
    memory_enabled: bool = True


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=160)
    preferred_name: str | None = Field(default=None, max_length=100)
    role: Literal["executive", "enterprise_admin", "fde"] = "executive"
    temporary_password: str = Field(min_length=10, max_length=256)
    organization_unit_ids: list[uuid.UUID] = Field(default_factory=list)
    enterprise_wide_scope: bool = False

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized.count("@") != 1 or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("invalid email")
        return normalized


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    preferred_name: str | None = Field(default=None, max_length=100)
    role: Literal["executive", "enterprise_admin", "fde"] | None = None
    is_active: bool | None = None
    locale: Literal["zh-CN", "zh-TW", "en-US"] | None = None
    timezone: str | None = Field(default=None, max_length=64)


class TemporaryPasswordRequest(BaseModel):
    temporary_password: str = Field(min_length=10, max_length=256)
