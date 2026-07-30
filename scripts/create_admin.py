"""Create the first enterprise administrator for a fresh local database.

Usage (PowerShell, from repo root):
    Get-Content .env-services-api -Raw  # copy to services/api/.env if missing
    "YourStrongP@ssw0rd" | .venv/Scripts/python.exe scripts/create_admin.py `
        --email admin@example.com `
        --display-name "Admin User" `
        --enterprise-name "Acme Inc" `
        --enterprise-slug acme

Or via the project venv from services/api:
    echo "YourStrongP@ssw0rd" | .venv/Scripts/python.exe ..\\..\\scripts\\create_admin.py ...

Notes:
- Password is read from STDIN to avoid leaking into shell history / process listings.
- Reads SESSION_SECRET / CSRF_SECRET / AUDIT_HMAC_KEY / FILE_ENCRYPTION_KEY from
  services/api/.env (pydantic Settings picks them up automatically when CWD is
  services/api).  Run from there, or pre-export the values in your shell.
- Idempotent on enterprise slug, refuses if an admin already exists for the
  enterprise (use the admin API to add additional users).
"""
from __future__ import annotations

import argparse
import os
import sys
from argparse import Namespace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "services" / "api"
API_SRC = API_DIR / "src"


def parse_args() -> Namespace:
    parser = argparse.ArgumentParser(
        description="Create the first enterprise administrator (re-uses executive_ai_api.cli.create_admin).",
    )
    parser.add_argument("--email", required=True, help="Login email for the new admin")
    parser.add_argument("--display-name", required=True, help="Display name shown in the UI")
    parser.add_argument("--enterprise-name", required=True, help="Human-readable enterprise name")
    parser.add_argument("--enterprise-slug", required=True, help="URL-safe enterprise identifier")
    parser.add_argument(
        "--force-password-change",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require the user to set a new password on first login (default: true)",
    )
    return parser.parse_args()


def main() -> int:
    if not (API_DIR / ".env").exists():
        print(
            f"ERROR: {API_DIR / '.env'} not found. "
            "Create it (DATABASE_URL, SESSION_SECRET, AUDIT_HMAC_KEY, FILE_ENCRYPTION_KEY, ...) first.",
            file=sys.stderr,
        )
        return 2

    # Make sure pydantic Settings finds .env in services/api/.
    os.chdir(API_DIR)
    sys.path.insert(0, str(API_SRC))

    from executive_ai_api.cli import create_admin  # noqa: E402  (import after path mutation)

    args = parse_args()
    # create_admin() reads the password from STDIN when password_stdin=True.
    setattr(args, "password_stdin", True)
    try:
        create_admin(args)
    except SystemExit as exc:
        # cli.create_admin raises SystemExit on validation failures; surface code.
        return int(exc.code) if isinstance(exc.code, int) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
