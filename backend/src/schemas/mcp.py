"""MCP 工具 schema."""

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



class McpToolOut(BaseModel):
    tool_name: str
    display_name: str
    description: str
    category: str
    domains: list[str]
    parameters: dict[str, Any]
    source_type: Literal["built_in", "composite"]
    component_tools: list[str]
    definition_version: int
    is_enabled: bool
    planner_enabled: bool
    timeout_seconds: int
    max_rows: int
    operator_note: str | None
    configured: bool
    readiness: Literal["ready", "disabled", "data_unavailable"]
    readiness_issues: list[str]
    updated_at: datetime | None


class McpToolCatalogOut(BaseModel):
    tools: list[McpToolOut]
    enabled_count: int
    planner_count: int
    generated_at: datetime


class McpToolUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    is_enabled: bool | None = None
    planner_enabled: bool | None = None
    timeout_seconds: int | None = Field(default=None, ge=3, le=60)
    max_rows: int | None = Field(default=None, ge=1, le=100)
    operator_note: str | None = Field(default=None, max_length=500)


class McpCompositeToolCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(
        min_length=8,
        max_length=64,
        pattern=r"^custom_[a-z0-9_]+$",
    )
    display_name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=12, max_length=2000)
    category: str = Field(min_length=1, max_length=80)
    component_tools: list[str] = Field(min_length=1, max_length=4)
    operator_note: str | None = Field(default=None, max_length=500)


class McpToolValidationOut(BaseModel):
    tool: McpToolOut
    ready: bool
    issues: list[str]
