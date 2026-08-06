from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import Settings
from exceptions.errors import AppError
from services.storage import LocalEncryptedStorage
from starlette.concurrency import run_in_threadpool

EXPECTED_DATABASE_REVISION = "9d5a2b7c1e40"


class HealthService:
    """健康检查业务逻辑：DB 探活 + alembic 版本校验 + 加密存储自检。"""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def liveness(self) -> dict[str, str]:
        return {"status": "ok"}

    async def readiness(self) -> dict[str, str]:
        try:
            await self._session.execute(text("SELECT 1"))
            revision = await self._session.scalar(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            )
            if revision != EXPECTED_DATABASE_REVISION:
                raise RuntimeError(
                    f"database revision {revision!r} does not match {EXPECTED_DATABASE_REVISION}"
                )
            storage = LocalEncryptedStorage(
                self._settings.file_storage_root,
                current_key_version=self._settings.file_encryption_key_version,
                key_ring=self._settings.file_encryption_keys(),
            )
            await run_in_threadpool(storage.self_test)
        except Exception as exc:
            raise AppError(503, "not_ready", "服务尚未就绪") from exc
        return {
            "status": "ready",
            "database": "ok",
            "database_revision": EXPECTED_DATABASE_REVISION,
            "storage": "encrypted-round-trip-ok",
        }
