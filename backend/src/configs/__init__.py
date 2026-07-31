"""``configs`` — single source of truth for backend runtime configuration.

Settings are loaded from environment variables (and an optional
``backend/.env`` for local development) by Pydantic. Callers should always
go through :func:`get_settings` to benefit from the lru_cache that ensures
the env is read once per process.
"""
from .settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
