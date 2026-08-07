from __future__ import annotations

from collections.abc import AsyncIterator, Generator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from configs.settings import get_settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


settings = get_settings()


def _to_sync_url(url: str) -> str:
    """将异步 database_url (asyncpg) 转换为同步驱动 URL (psycopg)。

    worker / migration / seed 等同步链路使用 psycopg 驱动。
    """
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return url


# ---------------------------------------------------------------------------
# 同步引擎（worker / migration / seed 仍使用）
# ---------------------------------------------------------------------------
_sync_url = _to_sync_url(settings.database_url)
engine_kwargs: dict[str, object] = {"pool_pre_ping": True}
if not _sync_url.startswith("sqlite"):
    # SQLite (used by tests) does not accept ``pool_size`` / ``max_overflow``.
    engine_kwargs.update(
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )

engine = create_engine(_sync_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 异步引擎（API 链路使用）
# ---------------------------------------------------------------------------
_async_engine_kwargs: dict[str, object] = {"pool_pre_ping": True}
if not settings.database_url.startswith("sqlite"):
    _async_engine_kwargs.update(
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )

async_engine: AsyncEngine | None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None
if settings.database_url.startswith("sqlite"):
    # SQLite (used by tests) only supports the sync driver; the AsyncEngine
    # is therefore disabled in test environments. Routes that require async
    # access must be skipped or rewritten to use the sync session.
    async_engine = None
    AsyncSessionLocal = None
else:
    async_engine = create_async_engine(
        settings.database_url, **_async_engine_kwargs
    )
    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine, expire_on_commit=False, autoflush=False
    )


async def get_db_async() -> AsyncIterator[AsyncSession]:
    if async_engine is None or AsyncSessionLocal is None:
        raise RuntimeError(
            "Async DB session is not available in this environment "
            "(sqlite is used). Use get_db() instead."
        )
    async with AsyncSessionLocal() as session:
        yield session
