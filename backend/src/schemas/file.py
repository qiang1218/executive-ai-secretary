"""文件 schema."""

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



class FileOut(ORMModel):
    id: uuid.UUID
    original_name: str
    media_type: str
    size_bytes: int
    sha256: str
    encryption_key_version: str
    status: str
    metadata_json: dict[str, Any]
    created_at: datetime
    deleted_at: datetime | None


class FileExtractionOut(ORMModel):
    file_id: uuid.UUID
    status: str
    parser_name: str | None
    parser_version: str | None
    page_count: int | None
    chunk_count: int
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
