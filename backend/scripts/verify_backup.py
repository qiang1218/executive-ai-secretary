"""Verify the integrity, signature, and decryptability of a backup
produced by scripts/backup.py.

Replaces scripts/verify-backup.sh.  Reads ``manifest.env``, verifies the
Ed25519 signature against ``backup_signing_public_key``, checks the SHA-256
checksums of the encrypted artefacts, and dry-runs the AES-256-CBC decrypt
so any tampering or corruption is surfaced before restore is attempted.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND_DIR)

from scripts import runtime  # noqa: E402


_MANIFEST_LINE = re.compile(r"^([A-Za-z0-9_]+)=(.*)$")


def parse_manifest(path: Path) -> dict[str, str]:
    if not path.is_file():
        runtime.die(f"manifest missing: {path}")
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = _MANIFEST_LINE.match(raw_line.strip())
        if not match:
            continue
        key, value = match.group(1), match.group(2)
        values[key] = value
    return values


def openssl(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    runtime.require_command("openssl")
    cmd = ["openssl", *args]
    runtime.info(f"$ {' '.join(shlex.quote(part) for part in cmd)}")
    completed = subprocess.run(cmd, check=False, text=True, capture_output=True)
    if check and completed.returncode != 0:
        runtime.die(
            f"openssl {args[0]} failed: {completed.stderr.strip()}",
            code=completed.returncode,
        )
    return completed


def run(args: argparse.Namespace) -> int:
    ctx = runtime.load_context(args.environment)
    runtime.require_backup_key_files(ctx)
    backup_dir = args.backup_dir.resolve()
    if not backup_dir.is_dir():
        runtime.die(f"backup directory not found: {backup_dir}")

    manifest_path = backup_dir / "manifest.env"
    signature_path = backup_dir / "manifest.sig"
    manifest = parse_manifest(manifest_path)
    if not signature_path.is_file() or signature_path.stat().st_size == 0:
        runtime.die(f"manifest signature missing: {signature_path}")

    # 1. Ed25519 signature
    openssl(
        "pkeyutl",
        "-verify",
        "-pubin",
        "-rawin",
        "-inkey",
        str(ctx.backup_signing_public_key_file),
        "-in",
        str(manifest_path),
        "-sigfile",
        str(signature_path),
    )

    # 2. Manifest field semantics
    if manifest.get("environment") != ctx.environment:
        runtime.die(
            f"backup belongs to {manifest.get('environment')!r}, not {ctx.environment!r}"
        )
    if manifest.get("format_version") != "1":
        runtime.die("unsupported backup format")
    if manifest.get("consistency") != "application-quiesced":
        runtime.die("backup was not captured from a quiesced application")
    if not manifest.get("alembic_revision") or manifest.get("alembic_revision") == "unknown":
        runtime.die("backup does not identify its Alembic revision")
    if not re.fullmatch(r"[0-9]+", manifest.get("enterprise_count", "")):
        runtime.die("backup does not identify its enterprise count")

    # 3. Checksums
    database_file = backup_dir / manifest["database_file"]
    files_file = backup_dir / manifest["files_file"]
    if not database_file.is_file() or database_file.stat().st_size == 0:
        runtime.die("encrypted database artifact is missing")
    if not files_file.is_file() or files_file.stat().st_size == 0:
        runtime.die("encrypted files artifact is missing")
    if runtime.sha256_file(database_file) != manifest["database_sha256"]:
        runtime.die("database backup checksum mismatch")
    if runtime.sha256_file(files_file) != manifest["files_sha256"]:
        runtime.die("files backup checksum mismatch")

    # 4. Decrypt dry-runs (pipe to /dev/null via -- stdout discard)
    decrypt_dry_run(manifest, database_file, ctx.backup_encryption_key_file, "database")
    decrypt_dry_run(manifest, files_file, ctx.backup_encryption_key_file, "files")

    runtime.info(f"Backup verification passed: {backup_dir}")
    return 0


def decrypt_dry_run(
    manifest: dict[str, str], encrypted: Path, key_file: Path, label: str
) -> None:
    proc = subprocess.run(
        [
            "openssl",
            "enc",
            "-d",
            "-aes-256-cbc",
            "-pbkdf2",
            "-iter",
            "200000",
            "-pass",
            f"file:{key_file}",
            "-in",
            str(encrypted),
        ],
        check=False,
        capture_output=True,
    )
    if proc.returncode != 0:
        runtime.die(f"failed to decrypt {label} backup: {proc.stderr.decode(errors='ignore')}")
    if not manifest.get("files_file" if label == "files" else "database_file"):
        # extra paranoia: the dry-run must yield some bytes
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    runtime.add_environment_argument(parser)
    parser.add_argument("--backup-dir", type=Path, required=True)
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
