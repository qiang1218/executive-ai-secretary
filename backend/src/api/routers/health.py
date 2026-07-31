from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from configs.settings import Settings, get_settings
from ..database import get_db
from ..errors import AppError
from ..storage import LocalEncryptedStorage

router = APIRouter(tags=["health"])


@router.get("/health/live", include_in_schema=False)
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", include_in_schema=False)
def ready(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    expected_revision = settings.expected_alembic_revision
    try:
        db.execute(text("SELECT 1"))
        if db.bind is not None and db.bind.dialect.name != "sqlite":
            revision = db.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
            if revision != expected_revision:
                raise RuntimeError(
                    f"database revision {revision!r} does not match {expected_revision}"
                )
        storage = LocalEncryptedStorage(
            settings.file_storage_root,
            current_key_version=settings.file_encryption_key_version,
            key_ring=settings.file_encryption_keys(),
        )
        storage.self_test()
    except Exception as exc:
        raise AppError(503, "not_ready", "服务尚未就绪") from exc
    return {
        "status": "ready",
        "database": "ok",
        "database_revision": expected_revision,
        "storage": "encrypted-round-trip-ok",
    }
