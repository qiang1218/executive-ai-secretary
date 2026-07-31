"""Create an encrypted + Ed25519-signed backup of the database and the
private file volume.

Replaces scripts/backup.sh.  Quiesces the application, runs
``pg_dump``/``tar`` through their respective Compose tool services, encrypts
the artefacts with ``openssl enc -aes-256-cbc -pbkdf2 -iter 200000`` using
the per-environment backup key, signs the manifest with the Ed25519
private key, and delegates to scripts/verify_backup.py for the
integrity check.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND_DIR)

from scripts import runtime  # noqa: E402
from scripts import verify_backup  # noqa: E402  (re-use the verifier)


def pg_dump(ctx: runtime.RuntimeContext, target: Path) -> None:
    cmd = [
        "docker",
        "compose",
        "--project-name",
        ctx.compose_project_name,
        "--env-file",
        str(ctx.backend_env_file),
        "--file",
        str(ctx.compose_file),
        "--profile",
        "tools",
        "run",
        "--rm",
        "-T",
        "db-backup-tool",
        "pg_dump",
        "--host",
        "postgres",
        "--username",
        ctx.postgres_backup_user,
        "--dbname",
        ctx.postgres_db,
        "--format=custom",
        "--no-owner",
        "--no-acl",
    ]
    runtime.info(f"$ {' '.join(shlex.quote(part) for part in cmd)} | openssl enc ...")
    dump = subprocess.run(cmd, check=False, capture_output=True)
    if dump.returncode != 0:
        runtime.die(
            f"pg_dump failed: {dump.stderr.decode(errors='ignore')}",
            code=dump.returncode,
        )
    enc = subprocess.run(
        [
            "openssl",
            "enc",
            "-aes-256-cbc",
            "-salt",
            "-pbkdf2",
            "-iter",
            "200000",
            "-pass",
            f"file:{ctx.backup_encryption_key_file}",
            "-out",
            str(target),
        ],
        input=dump.stdout,
        check=False,
    )
    if enc.returncode != 0:
        runtime.die(f"openssl enc failed (exit {enc.returncode})", code=enc.returncode)


def tar_files(target: Path) -> None:
    cmd = ["tar", "-C", "/data/files", "-cf", "-", "."]
    runtime.info(f"$ {' '.join(shlex.quote(part) for part in cmd)} | openssl enc ...")
    tar = subprocess.run(cmd, check=False, capture_output=True)
    if tar.returncode != 0:
        runtime.die(f"tar failed: {tar.stderr.decode(errors='ignore')}", code=tar.returncode)
    enc = subprocess.run(
        [
            "openssl",
            "enc",
            "-aes-256-cbc",
            "-salt",
            "-pbkdf2",
            "-iter",
            "200000",
            "-pass",
            f"file:{runtime.RUNTIME_DIR}/local-demo/secrets/backup_encryption_key",
            "-out",
            str(target),
        ],
        input=tar.stdout,
        check=False,
    )
    if enc.returncode != 0:
        runtime.die(f"openssl enc failed (exit {enc.returncode})", code=enc.returncode)


def run(args: argparse.Namespace) -> int:
    ctx = runtime.load_context(args.environment)
    runtime.validate_label(args.label)
    runtime.require_backup_key_files(ctx)
    runtime.require_command("docker")
    runtime.require_command("openssl")

    backup_root = runtime.REPO_ROOT / "backups" / ctx.environment
    timestamp = runtime.utc_timestamp()
    backup_dir = backup_root / f"{timestamp}-{args.label}"
    database_file = backup_dir / "database.dump.enc"
    files_file = backup_dir / "files.tar.enc"
    manifest_file = backup_dir / "manifest.env"
    signature_file = backup_dir / "manifest.sig"

    backup_dir.mkdir(parents=True, exist_ok=False, mode=0o700)

    # 1. Quiesce application if running (best-effort)
    running = runtime.compose(
        ctx, "ps", "--services", "--filter", "status=running", check=False
    )
    running_services = set(running.stdout.split())
    api_running = "api" in running_services
    worker_running = "worker" in running_services
    quiesced = False
    if api_running or worker_running:
        runtime.info("Quiescing API and Worker so database and private files share one consistency point...")
        runtime.compose(ctx, "stop", "api", "worker", check=False)
        quiesced = True

    try:
        runtime.info(f"Creating encrypted database backup for {ctx.environment}...")
        pg_dump(ctx, database_file)

        runtime.info("Creating encrypted private-file backup...")
        # We cannot reach the in-container /data/files from the host shell
        # without a privileged file tool, so defer to the file-tool service.
        cmd = [
            "docker",
            "compose",
            "--project-name",
            ctx.compose_project_name,
            "--env-file",
            str(ctx.backend_env_file),
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
            "-cf",
            "-",
            ".",
        ]
        runtime.info(f"$ {' '.join(shlex.quote(part) for part in cmd)} | openssl enc ...")
        tar = subprocess.run(cmd, check=False, capture_output=True)
        if tar.returncode != 0:
            runtime.die(
                f"file-tool tar failed: {tar.stderr.decode(errors='ignore')}",
                code=tar.returncode,
            )
        enc = subprocess.run(
            [
                "openssl",
                "enc",
                "-aes-256-cbc",
                "-salt",
                "-pbkdf2",
                "-iter",
                "200000",
                "-pass",
                f"file:{ctx.backup_encryption_key_file}",
                "-out",
                str(files_file),
            ],
            input=tar.stdout,
            check=False,
        )
        if enc.returncode != 0:
            runtime.die(f"openssl enc failed (exit {enc.returncode})", code=enc.returncode)

        database_sha = runtime.sha256_file(database_file)
        files_sha = runtime.sha256_file(files_file)
        git_revision = subprocess.run(
            ["git", "-C", str(runtime.REPO_ROOT), "rev-parse", "--verify", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        git_head = git_revision.stdout.strip() or "unknown"

        # alembic revision and enterprise slugs from the database
        alembic_revision = query_alembic_revision(ctx)
        enterprise_slugs = query_enterprise_slugs(ctx)
        enterprise_count = query_enterprise_count(ctx)

        manifest_lines = [
            "format_version=1",
            f"environment={ctx.environment}",
            f"app_mode={ctx.app_mode}",
            f"compose_project={ctx.compose_project_name}",
            f"postgres_database={ctx.postgres_db}",
            f"created_at_utc={timestamp}",
            f"git_revision={git_head}",
            f"alembic_revision={alembic_revision}",
            f"enterprise_count={enterprise_count}",
            f"enterprise_slugs={enterprise_slugs}",
            "consistency=application-quiesced",
            "database_file=database.dump.enc",
            f"database_sha256={database_sha}",
            "files_file=files.tar.enc",
            f"files_sha256={files_sha}",
            "encryption=aes-256-cbc-pbkdf2-iter200000",
        ]
        manifest_file.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
        os.chmod(manifest_file, 0o600)

        sign = subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-sign",
                "-rawin",
                "-inkey",
                str(ctx.backup_signing_key_file),
                "-in",
                str(manifest_file),
                "-out",
                str(signature_file),
            ],
            check=False,
        )
        if sign.returncode != 0:
            runtime.die(
                f"manifest signing failed (exit {sign.returncode})", code=sign.returncode
            )
        for path in (manifest_file, signature_file, database_file, files_file):
            os.chmod(path, 0o600)

        # Delegate to verify_backup for a uniform integrity report
        verify_backup.run(
            argparse.Namespace(environment=ctx.environment, backup_dir=backup_dir)
        )
    finally:
        if quiesced:
            to_restart = []
            if api_running:
                to_restart.append("api")
            if worker_running:
                to_restart.append("worker")
            if to_restart:
                runtime.compose(ctx, "up", "--detach", *to_restart, check=False)
    runtime.info(f"Backup completed and verified: {backup_dir}")
    print(backup_dir)
    return 0


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
        "--profile",
        "tools",
        "run",
        "--rm",
        "-T",
        "db-backup-tool",
        "psql",
        "--host",
        "postgres",
        "--username",
        ctx.postgres_backup_user,
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


def query_alembic_revision(ctx: runtime.RuntimeContext) -> str:
    value = _psql_value(ctx, "SELECT version_num FROM alembic_version LIMIT 1")
    return value or "unknown"


def query_enterprise_slugs(ctx: runtime.RuntimeContext) -> str:
    return _psql_value(
        ctx,
        "SELECT COALESCE(string_agg(slug, ',' ORDER BY slug), '') FROM enterprises",
    )


def query_enterprise_count(ctx: runtime.RuntimeContext) -> str:
    value = _psql_value(ctx, "SELECT count(*) FROM enterprises")
    return value or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    runtime.add_environment_argument(parser)
    parser.add_argument(
        "--label",
        default="manual",
        help="Free-form label appended to the backup directory name.",
    )
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
