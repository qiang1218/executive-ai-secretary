"""Pydantic schema for `backend/configs/` — single source of truth.

Phase 1 (current): skeleton. Only the field shapes are defined; the
existing `Settings` in `executive_ai_api.config` is the live source.

Phase 1 completion (future commits):
- This module becomes the **only** place where configuration field
  shapes are defined.
- `executive_ai_api.config.get_settings()` will be rewritten to
  delegate here (preserving the same import path for callers).
- All startup guards (default-key rejection, demo-seeding blocks,
  secure-cookie enforcement, etc.) live in `AppConfig.model_validator`.

See `docs/architecture/0004-refactor-plan.md` §4.1 and §5 Phase 1
for the full migration plan.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ProfileConfig(BaseModel):
    env: Literal["local-demo", "customer-template", "production", "test", "development"]
    mode: Literal["demo", "production"]
    seed_demo_data: bool
    debug: bool


class DatabaseConfig(BaseModel):
    url: str
    pool_size: int = Field(default=10, ge=1, le=100)
    max_overflow: int = Field(default=20, ge=0, le=200)


class CookieConfig(BaseModel):
    secure: bool
    samesite: Literal["lax", "strict", "none"]
    session_name: str = "exec_session"
    csrf_name: str = "exec_csrf"


class WorkerConfig(BaseModel):
    poll_seconds: float = Field(default=2.0, ge=0.1, le=60)
    lease_seconds: int = Field(default=60, ge=10, le=3600)
    heartbeat_seconds: int = Field(default=15, ge=5, le=600)
    job_max_attempts: int = Field(default=3, ge=1, le=20)
    retry_base_seconds: float = Field(default=5.0, ge=0.1, le=3600)
    retry_max_seconds: float = Field(default=300.0, ge=10.0, le=86400)


class ApiConfig(BaseModel):
    prefix: str = "/api/v1"
    cors_allowed_origins: list[str] = Field(default_factory=list)
    trusted_hosts: list[str] = Field(default_factory=list)
    # expected_alembic_revision is populated by scripts/generate-configs.sh
    # at deploy time so the live alembic head matches what was tested.
    expected_alembic_revision: str = ""


class SecretsConfig(BaseModel):
    """References to secret material. Values themselves come from secret
    files mounted into the container (e.g. via Docker secrets).

    Schema-level constraints on the secret FILES (paths, modes) are
    declared in `secrets.schema.yaml`; this Pydantic model only validates
    the path strings, not the file contents.
    """
    session_secret_file: Path
    csrf_secret_file: Path
    audit_hmac_key_file: Path
    audit_hmac_key_ring_file: Path | None = None
    file_encryption_key_file: Path
    file_encryption_key_ring_file: Path | None = None


class AppConfig(BaseModel):
    """Top-level config assembled by loader.load_active_profile()."""
    profile: ProfileConfig
    database: DatabaseConfig
    cookie: CookieConfig
    worker: WorkerConfig
    api: ApiConfig
    secrets: SecretsConfig

    # Startup guards: see Phase 1 completion plan.
    # - production refuses default keys / demo seeding
    # - cookie.secure must be true when samesite=none
    # - session/csrf/audit secrets must be distinct
