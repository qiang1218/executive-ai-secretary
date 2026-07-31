"""Restore a previously produced backup into the configured environment.

Replaces scripts/restore.sh.  Verifies the backup, runs the
Alembic-migration compatibility check (delegated to
``api.migration_compatibility.supported_upgrade_head`` running inside the
``migrate`` Compose service), takes a pre-restore safety backup, then
``pg_restore`` and re-tars the file volume.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND_DIR)

from scripts import runtime  # noqa: E402
from scripts import verify_backup  # noqa: E402


_MANIFEST_LINE = __import__("re").compile(r"^([A-Za-z0-9_]+)=(.*)$")


def parse_manifest(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = _MANIFEST_LINE.match(raw_line.strip())
        if not match:
            continue
        values[match.group(1)] = match.group(2)
    return values


def _psql_value(ctx: runtime.RuntimeContext, sql: str) -> str:
    cmd = [
        "docker",
        "compose",
        "--project-name",
        ctx.compose_project_name,
        "--env-file",
        str(ctx.backend_env_file),
        "--file",
        str(ctx.compose_file),
        "exec",
        "-T",
        "postgres",
        "psql",
        "--username",
        ctx.postgres_user,
        "--dbname",
        ctx.postgres_db,
        "--tuples-only",
        "--no-align",
        "--command",
        sql,
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return ""
    return result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""


def migration_supported_head(ctx: runtime.RuntimeContext, backup_revision: str) -> str:
    cmd = [
        "docker",
        "compose",
        "--project-name",
        ctx.compose_project_name,
        "--env-file",
        str(ctx.backend_env_file),
        "--file",
        str(ctx.compose_file),
        "run",
        "--rm",
        "--no-deps",
        "-T",
        "migrate",
        "python",
        "-m",
        "api.migration_compatibility",
        "--",
        backup_revision,
    ]
    runtime.info(f"$ {' '.join(shlex.quote(part) for part in cmd)}")
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        runtime.die(
            f"migration compatibility check failed: {proc.stderr.strip()}",
            code=proc.returncode,
        )
    head = proc.stdout.strip()
    if not head:
        runtime.die("migration compatibility check returned no supported head")
    return head


def run(args: argparse.Namespace) -> int:
    ctx = runtime.load_context(args.environment)
    runtime.require_backup_key_files(ctx)
    runtime.require_command("docker")
    runtime.require_command("openssl")
    backup_dir = args.backup_dir.resolve()
    if not backup_dir.is_dir():
        runtime.die(f"backup directory not found: {backup_dir}")
    if not args.yes:
        expected = f"RESTORE {ctx.environment}"
        runtime.info(
            f"This is a destructive operation. To confirm non-interactively, pass --yes or "
            f"re-run with the literal confirmation string {expected!r} as the last argument."
        )
        try:
            typed = input(f"Type {expected!r} to continue: ")
        except EOFError as exc:
            raise SystemExit(f"aborted: {exc}") from exc
        if typed != expected:
            runtime.die("confirmation string did not match")

    # 1. Verify the backup before touching anything
    verify_backup.run(
        argparse.Namespace(environment=ctx.environment, backup_dir=backup_dir)
    )

    manifest = parse_manifest(backup_dir / "manifest.env")
    source_environment = manifest.get("environment")
    if source_environment == "local-demo" and ctx.environment == "customer-template":
        runtime.die("a local-demo backup can never be restored into customer-template")
    if source_environment != ctx.environment and not args.allow_cross_environment:
        runtime.die(
            f"backup belongs to {source_environment!r}; pass --allow-cross-environment "
            "only after a reviewed migration"
        )
    if source_environment != ctx.environment:
        runtime.die(
            "cross-environment restore requires re-encryption with the target key; "
            "use the reviewed migration runbook"
        )

    backup_revision = manifest.get("alembic_revision", "")
    runtime.info(
        f"Checking that backup revision {backup_revision} can upgrade on this release..."
    )
    supported_head = migration_supported_head(ctx, backup_revision)

    runtime.info("Creating a pre-restore safety backup...")
    safety = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.backup",
            "--environment",
            ctx.environment,
            "--label",
            "pre-restore",
        ],
        check=False,
        cwd=str(_BACKEND_DIR),
    )
    if safety.returncode != 0:
        runtime.die(
            f"pre-restore safety backup failed (exit {safety.returncode})",
            code=safety.returncode,
        )

    database_file = backup_dir / manifest["database_file"]
    files_file = backup_dir / manifest["files_file"]

    runtime.compose(ctx, "stop", "api", "worker", check=False)

    runtime.info(f"Restoring PostgreSQL for {ctx.environment}...")
    dec = subprocess.Popen(
        [
            "openssl",
            "enc",
            "-d",
            "-aes-256-cbc",
            "-pbkdf2",
            "-iter",
            "200000",
            "-pass",
            f"file:{ctx.backup_encryption_key_file}",
            "-in",
            str(database_file),
        ],
        stdout=subprocess.PIPE,
    )
    assert dec.stdout is not None
    restore = subprocess.run(
        [
            "docker",
            "compose",
            "--project-name",
            ctx.compose_project_name,
            "--env-file",
            str(ctx.backend_env_file,
            ),
            "--file",
            str(ctx.compose_file),
            "exec",
            "-T",
            "postgres",
            "pg_restore",
            "--username",
            ctx.postgres_user,
            "--dbname",
            ctx.postgres_db,
            "--clean",
            "--if-exists",
            "--no-owner",
            "--exit-on-error",
        ],
        stdin=dec.stdout,
        check=False,
    )
    dec.stdout.close()
    dec.wait()
    if restore.returncode != 0:
        runtime.die(
            f"pg_restore failed (exit {restore.returncode})", code=restore.returncode
        )

    for one_shot in ("db-role-init", "migrate", "db-permissions"):
        runtime.info(f"Replaying {one_shot} after restore...")
        runtime.compose(
            ctx,
            "up",
            "--no-deps",
            "--force-recreate",
            "--abort-on-container-exit",
            "--exit-code-from",
            one_shot,
            one_shot,
        )

    restored_revision = _psql_value(
        ctx, "SELECT version_num FROM alembic_version LIMIT 1"
    )
    if restored_revision != supported_head:
        runtime.die(
            f"restored database revision {restored_revision!r} does not match "
            f"supported head {supported_head!r}"
        )

    runtime.info("Replacing the isolated private-file volume...")
    runtime.compose(
        ctx,
        "--profile",
        "tools",
        "run",
        "--rm",
        "file-tool",
        "sh",
        "-ec",
        "find /data/files -mindepth 1 -depth -delete",
        check=False,
    )
    dec_files = subprocess.Popen(
        [
            "openssl",
            "enc",
            "-d",
            "-aes-256-cbc",
            "-pbkdf2",
            "-iter",
            "200000",
            "-pass",
            f"file:{ctx.backup_encryption_key_file}",
            "-in",
            str(files_file),
        ],
        stdout=subprocess.PIPE,
    )
    assert dec_files.stdout is not None
    untar = subprocess.run(
        [
            "docker",
            "compose",
            "--project-name",
            ctx.compose_project_name,
            "--env-file",
            str(ctx.backend_env_file,
            ),
            "--file",
            str(ctx.compose_file),
            "--profile",
            "tools",
            "run",
            "--rm",
            "-T",
            "file-tool",
            "tar",
            "-C",
            "/data/files",
            "-xf",
            "-",
        ],
        stdin=dec_files.stdout,
        check=False,
    )
    dec_files.stdout.close()
    dec_files.wait()
    if untar.returncode != 0:
        runtime.die(f"file untar failed (exit {untar.returncode})", code=untar.returncode)

    runtime.compose(ctx, "up", "--detach", "--no-deps", "api", "worker", "nginx", check=False)

    restore_log = runtime.RUNTIME_DIR / ctx.environment / "restore.log"
    restore_log.parent.mkdir(parents=True, exist_ok=True)
    with restore_log.open("a", encoding="utf-8") as handle:
        handle.write(
            f"{datetime.now(timezone.utc).isoformat()} environment={ctx.environment} "
            f"source={backup_dir} operator={os.environ.get('USERNAME', 'unknown')}\n"
        )
    os.chmod(restore_log, 0o600)
    runtime.info("Restore completed. Safety backup is retained under backups/.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    runtime.add_environment_argument(parser)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument(
        "--allow-cross-environment",
        action="store_true",
        help="Allow restoring a backup from a different environment (requires a reviewed migration).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the explicit-confirmation prompt.",
    )
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
