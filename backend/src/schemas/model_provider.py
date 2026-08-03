"""模型供应商与授权 schema."""

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



class ModelCatalogItem(BaseModel):
    id: str
    name: str
    family: str
    profile: str
    capability: Literal["chat", "image", "video", "embedding", "rerank"]
    selectable: bool


class ModelProviderOut(BaseModel):
    provider: Literal["anspire"] = "anspire"
    endpoint_url: str
    documentation_url: str
    model_id: str
    is_enabled: bool
    is_configured: bool
    api_key_masked: str | None
    credential_version: int
    last_tested_at: datetime | None
    last_test_status: str | None
    last_test_latency_ms: int | None
    last_test_error: str | None
    models: list[ModelCatalogItem]
    updated_at: datetime | None


class ModelProviderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(min_length=1, max_length=100)
    api_key: SecretStr | None = Field(default=None)
    is_enabled: bool | None = None


class ModelProviderTestOut(BaseModel):
    status: Literal["success"] = "success"
    model: str
    latency_ms: int
    tested_at: datetime


class AuthorizedModelOut(BaseModel):
    model_id: str
    name: str
    family: str
    profile: str
    display_name: str
    is_default: bool


class AdminModelAuthorizationOut(AuthorizedModelOut):
    capability: str
    selectable: bool
    test_status: Literal["pending", "success", "failed"]
    tested_credential_version: int | None
    current_credential_version: int
    is_authorized: bool
    last_tested_at: datetime | None
    last_test_latency_ms: int | None
    last_test_error: str | None
    authorized_at: datetime | None


class AdminModelCatalogOut(BaseModel):
    provider: Literal["anspire"] = "anspire"
    credential_version: int
    is_configured: bool
    is_enabled: bool
    models: list[AdminModelAuthorizationOut]


class ModelAuthorizationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_authorized: bool
    display_name: str | None = Field(default=None, min_length=1, max_length=160)


class DefaultModelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_default: Literal[True] = True
