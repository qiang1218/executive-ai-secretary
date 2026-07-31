"""Create the first enterprise administrator for a fresh local database.

Replaces scripts/create_admin.py.  Imports ``api.cli.create_admin`` so the
admin bootstrap uses exactly the same code path as the
``bootstrap-admin`` Compose service, but runs in the operator's shell so
the password can be read from STDIN without going through the Docker
event stream.

Usage (from repo root):
    cd backend
    echo "YourStrongP@ssw0rd" | uv run python scripts/create_admin.py \\
        --email admin@example.com \\
        --display-name "Admin User" \\
        --enterprise-name "Acme Inc" \\
        --enterprise-slug acme
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
BACKEND_SRC = BACKEND_DIR / "src"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
    )
    parser.add_argument("--email", required=True, help="Login email for the new admin")
    parser.add_argument("--display-name", required=True, help="Display name shown in the UI")
    parser.add_argument("--enterprise-name", required=True, help="Human-readable enterprise name")
    parser.add_argument(
        "--enterprise-slug", required=True, help="URL-safe enterprise identifier"
    )
    parser.add_argument(
        "--force-password-change",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require the user to set a new password on first login (default: true)",
    )
    return parser.parse_args(argv)


def main() -> int:
    if not (BACKEND_DIR / ".env").exists():
        print(
            f"ERROR: {BACKEND_DIR / '.env'} not found. "
            "Create it (DATABASE_URL, SESSION_SECRET, AUDIT_HMAC_KEY, FILE_ENCRYPTION_KEY, ...) first.",
            file=sys.stderr,
        )
        return 2

    # Make sure pydantic Settings finds .env in backend/.
    os.chdir(BACKEND_DIR)
    sys.path.insert(0, str(BACKEND_SRC))

    from api.cli import create_admin  # noqa: E402  (import after path mutation)

    args = parse_args()
    # create_admin() reads the password from STDIN when password_stdin=True.
    args.password_stdin = True  # type: ignore[attr-defined]
    try:
        create_admin(args)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
