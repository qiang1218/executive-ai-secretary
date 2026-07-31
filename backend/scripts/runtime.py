"""Shared runtime helpers for the database-operation scripts in this directory.

These wrappers keep behaviour identical to the old ``scripts/*.sh`` Bash
scripts while moving the orchestration into Python.  Each script is a thin
``subprocess`` driver around the same Docker Compose services the Bash
wrappers invoked, so the underlying containers (api / worker / migrate /
seed-demo / db-backup-tool / file-tool / db-role-init / db-permissions)
remain the single source of truth for the actual database and file-system
work.

All scripts source this file the same way:

    from scripts import runtime  # type: ignore  # noqa: PTH201
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
BACKEND_DIR: Final[Path] = Path(__file__).resolve().parents[1]
COMPOSE_FILE: Final[Path] = REPO_ROOT / "compose.yml"
BACKEND_ENV_FILE: Final[Path] = BACKEND_DIR / ".env"
RUNTIME_DIR: Final[Path] = REPO_ROOT / "runtime"
SUPPORTED_ENVIRONMENTS: Final[tuple[str, ...]] = ("local-demo", "customer-template")
ENTERPRISE_SLUG_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LABEL_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class RuntimeContext:
    """Parsed backend/.env and resolved runtime paths for one operation."""

    environment: str
    app_env: str
    app_mode: str
    compose_project_name: str
    backend_env_file: Path
    compose_file: Path
    runtime_dir: Path
    backup_key_dir: Path
    database_url: str
    postgres_db: str
    postgres_user: str
    postgres_backup_user: str
    postgres_migrator_user: str
    postgres_runtime_user: str

    @property
    def backup_encryption_key_file(self) -> Path:
        return self.backup_key_dir / "backup_encryption_key"

    @property
    def backup_signing_key_file(self) -> Path:
        return self.backup_key_dir / "backup_signing_key"

    @property
    def backup_signing_public_key_file(self) -> Path:
        return self.backup_key_dir / "backup_signing_public_key"


def die(message: str, *, code: int = 1) -> "None":
    """Print an error to stderr and exit with a non-zero code."""

    print(f"Error: {message}", file=sys.stderr)
    sys.exit(code)


def info(message: str) -> None:
    """Print a status line to stderr so stdout stays parseable."""

    print(message, file=sys.stderr)


def require_command(name: str) -> None:
    if shutil.which(name) is None:
        die(f"required command not found: {name}")


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a ``KEY=VALUE`` env file.  Honors ``#`` comments and shell quoting."""

    if not path.is_file():
        die(f"{path} is missing; copy backend/.env.example and fill in the secrets")
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            die(f"invalid line in {path}: {raw_line!r}")
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if value.startswith(("'", '"')) and value.endswith(value[0]) and len(value) >= 2:
            value = value[1:-1]
        values[key] = value
    return values


def require_env(values: Mapping[str, str], key: str) -> str:
    value = values.get(key, "").strip()
    if not value:
        die(f"{key} is required in {BACKEND_ENV_FILE}")
    return value


def validate_environment(value: str) -> str:
    if value not in SUPPORTED_ENVIRONMENTS:
        die(
            f"environment must be one of {', '.join(SUPPORTED_ENVIRONMENTS)} (got {value!r})"
        )
    return value


def validate_label(value: str) -> str:
    if not LABEL_PATTERN.fullmatch(value):
        die("backup label may contain only letters, numbers, dot, underscore and dash")
    return value


def validate_enterprise_slug(value: str) -> str:
    if not ENTERPRISE_SLUG_PATTERN.fullmatch(value):
        die("enterprise slug must use only lowercase letters, numbers, and dashes")
    return value


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_context(environment: str) -> RuntimeContext:
    """Load and cross-validate ``backend/.env`` for a given environment."""

    validate_environment(environment)
    values = parse_env_file(BACKEND_ENV_FILE)
    app_env = require_env(values, "APP_ENV")
    if app_env != environment:
        die(
            f"APP_ENV in {BACKEND_ENV_FILE} is {app_env!r}, expected {environment!r}"
        )
    compose_project_name = require_env(values, "COMPOSE_PROJECT_NAME")
    if compose_project_name not in {
        "executive-ai-local-demo",
        "executive-ai-customer-template",
    }:
        die(
            f"unexpected COMPOSE_PROJECT_NAME: {compose_project_name!r} "
            "(phase 1 permits only the documented local-demo / customer-template projects)"
        )
    return RuntimeContext(
        environment=environment,
        app_env=app_env,
        app_mode=require_env(values, "APP_MODE"),
        compose_project_name=compose_project_name,
        backend_env_file=BACKEND_ENV_FILE,
        compose_file=COMPOSE_FILE,
        runtime_dir=RUNTIME_DIR / environment,
        backup_key_dir=RUNTIME_DIR / environment / "secrets",
        database_url=require_env(values, "DATABASE_URL"),
        postgres_db=require_env(values, "POSTGRES_DB"),
        postgres_user=require_env(values, "POSTGRES_USER"),
        postgres_backup_user=values.get("POSTGRES_BACKUP_USER", "executive_ai_backup"),
        postgres_migrator_user=values.get("POSTGRES_MIGRATOR_USER", "executive_ai_migrator"),
        postgres_runtime_user=values.get("POSTGRES_RUNTIME_USER", "executive_ai_runtime"),
    )


def require_backup_key_files(ctx: RuntimeContext) -> None:
    for path in (
        ctx.backup_encryption_key_file,
        ctx.backup_signing_key_file,
        ctx.backup_signing_public_key_file,
    ):
        if not path.is_file() or path.stat().st_size == 0:
            die(
                f"missing backup key: {path}; generate with openssl genpkey or ed25519 "
                "and place the file at this path"
            )


def compose(ctx: RuntimeContext, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run ``docker compose`` for the configured project."""

    require_command("docker")
    cmd = [
        "docker",
        "compose",
        "--project-name",
        ctx.compose_project_name,
        "--env-file",
        str(ctx.backend_env_file),
        "--file",
        str(ctx.compose_file),
        *args,
    ]
    info(f"$ {' '.join(shlex.quote(part) for part in cmd)}")
    completed = subprocess.run(cmd, check=False, text=True)
    if check and completed.returncode != 0:
        die(f"docker compose {args[0] if args else '...'} failed", code=completed.returncode)
    return completed


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_environment_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--environment",
        choices=SUPPORTED_ENVIRONMENTS,
        default=os.environ.get("APP_ENV") or "local-demo",
        help="Target deployment environment (default: $APP_ENV or local-demo).",
    )


__all__ = [
    "BACKEND_DIR",
    "BACKEND_ENV_FILE",
    "COMPOSE_FILE",
    "ENTERPRISE_SLUG_PATTERN",
    "LABEL_PATTERN",
    "REPO_ROOT",
    "RUNTIME_DIR",
    "RUNTIME_DIR",
    "RuntimeContext",
    "SUPPORTED_ENVIRONMENTS",
    "add_environment_argument",
    "compose",
    "die",
    "info",
    "load_context",
    "parse_env_file",
    "require_backup_key_files",
    "require_command",
    "require_env",
    "sha256_file",
    "utc_timestamp",
    "validate_enterprise_slug",
    "validate_environment",
    "validate_label",
]
