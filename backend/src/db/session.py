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
from sqlalchemy.pool import StaticPool

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
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite+pysqlite://", 1)
    return url


# ---------------------------------------------------------------------------
# 同步引擎（worker / migration / seed 仍使用）
# ---------------------------------------------------------------------------
_sync_url = _to_sync_url(settings.database_url)
engine_kwargs: dict[str, object] = {"pool_pre_ping": True}
if _sync_url.startswith("sqlite"):
    # SQLite (used by tests) does not accept ``pool_size`` / ``max_overflow``.
    #
    # ``sqlite:///``:memory:`` defaults to a per-connection DB. Test fixtures
    # populate ``Base.metadata.create_all(engine)`` once on the test thread,
    # but ``fastapi.testclient.TestClient`` spins the ASGI lifespan up on a
    # separate thread; without ``StaticPool + check_same_thread=False`` the
    # lifespan sees an empty :memory: and the very first query fails with
    # ``no such table: …``. The same fix also lets worker / job-runner code
    # that runs in an executor's worker thread share tables with the test
    # session.
    engine_kwargs.update(
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
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
# SQLite (used by tests) drives its async path through ``aiosqlite`` so the
# generic ``AsyncSession`` infrastructure is available for both production
# (asyncpg) and tests (aiosqlite) without any caller having to fork on
# ``settings.database_url``.
_async_url = settings.database_url
_async_engine_kwargs: dict[str, object] = {"pool_pre_ping": True}
if _async_url.startswith("sqlite"):
    # ``StaticPool + check_same_thread=False`` so TestClient's lifespan portal
    # (which spawns ASGI on a worker thread) and the test-fixture thread see
    # the same :memory: database and the same ``Base.metadata`` state.
    _async_engine_kwargs.update(
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    _async_engine_kwargs.update(
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )

async_engine = create_async_engine(_async_url, **_async_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine, expire_on_commit=False, autoflush=False
)


async def get_db_async() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
