"""组织单元 schema."""

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



class OrganizationUnitOut(ORMModel):
    id: uuid.UUID
    name: str
    code: str
    parent_id: uuid.UUID | None
    unit_type: str
    enabled_for_analysis: bool
    data_connected: bool
    sort_order: int


class OrganizationUnitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    parent_id: uuid.UUID | None = None
    unit_type: str = Field(default="division", max_length=40)
    enabled_for_analysis: bool = False
    data_connected: bool = False
    sort_order: int = 0


class OrganizationUnitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: uuid.UUID | None = None
    enabled_for_analysis: bool | None = None
    data_connected: bool | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class OrganizationScopeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["all_authorized", "selected"]
    organization_unit_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_scope(self):
        unique_ids = list(dict.fromkeys(self.organization_unit_ids))
        if len(unique_ids) != len(self.organization_unit_ids):
            raise ValueError("organization_unit_ids must be unique")
        if self.mode == "all_authorized" and self.organization_unit_ids:
            raise ValueError("all_authorized must not include explicit organization units")
        if self.mode == "selected" and not self.organization_unit_ids:
            raise ValueError("selected scope requires at least one organization unit")
        return self


class OrganizationScopeOut(OrganizationScopeInput):
    resolved_organization_unit_ids: list[uuid.UUID] = Field(default_factory=list)


class DataScopeUpdate(BaseModel):
    enterprise_wide_scope: bool = False
    organization_unit_ids: list[uuid.UUID] = Field(default_factory=list)
