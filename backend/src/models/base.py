"""ORM 模型公共基础设施。

集中所有领域文件共用的基础类型、混入类与 SQLAlchemy 符号，避免在
``models/<domain>.py`` 中重复定义。各领域文件通过 ``from .base import *``
一次性拿到全部公共符号。
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from db.session import Base

# PostgreSQL 上用 JSONB，其它后端（如 SQLite 测试）退化为 JSON。
JSONType = JSON().with_variant(JSONB(), "postgresql")


def new_uuid() -> uuid.UUID:
    """Generate a new UUID4 (used as default for ``UUIDMixin.id``)."""
    return uuid.uuid4()


class TimestampMixin:
    """Adds ``created_at`` / ``updated_at`` columns with server-side defaults."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDMixin:
    """Adds a UUID primary key column with ``new_uuid`` default."""

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)


__all__ = [
    # stdlib / typing
    "uuid",
    "date",
    "datetime",
    "Any",
    # sqlalchemy
    "Vector",
    "BigInteger",
    "Boolean",
    "Date",
    "DateTime",
    "ForeignKey",
    "Index",
    "Integer",
    "Numeric",
    "String",
    "Text",
    "UniqueConstraint",
    "Uuid",
    "event",
    "func",
    "text",
    "JSONB",
    "Mapped",
    "mapped_column",
    "relationship",
    "JSON",
    # db
    "Base",
    # helpers
    "JSONType",
    "new_uuid",
    "TimestampMixin",
    "UUIDMixin",
]
