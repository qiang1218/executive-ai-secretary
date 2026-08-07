"""通用 schema (ORMModel / Page)."""

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

