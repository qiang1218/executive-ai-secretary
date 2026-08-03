"""报告 schema."""

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



class ReportOut(ORMModel):
    id: uuid.UUID
    kind: str
    title: str
    status: str
    organization_unit_id: uuid.UUID | None
    period_start: date
    period_end: date
    data_as_of: datetime | None
    published_at: datetime | None
    created_at: datetime
    latest_version: int | None = None
    content: dict[str, Any] | None = None
