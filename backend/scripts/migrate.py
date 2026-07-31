"""Run the one-shot database-initialisation containers that ``start.sh``
used to drive through ``docker compose up db-role-init migrate db-permissions``.

Replaces the old bash loop in scripts/start.sh with a Python entry point
that surfaces the same three sequential Compose services (role bootstrap,
Alembic upgrade head, least-privilege re-grant).
"""

from __future__ import annotations

import argparse
import os
import sys

# Allow `python scripts/migrate.py` from anywhere: the ``scripts`` package
# sits next to ``src`` inside backend/, so the parent (backend/) is what we
# need on sys.path to import ``api.*`` if we ever inline the implementation.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND_DIR)

from scripts import runtime  # noqa: E402  (after path mutation)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    runtime.add_environment_argument(parser)
    parser.add_argument(
        "--compose-project-name",
        default=os.environ.get("COMPOSE_PROJECT_NAME"),
        help="Override the docker compose project name (default: $COMPOSE_PROJECT_NAME).",
    )
    args = parser.parse_args()

    ctx = runtime.load_context(args.environment)
    if args.compose_project_name:
        object.__setattr__(ctx, "compose_project_name", args.compose_project_name)

    runtime.require_backup_key_files(ctx)
    runtime.require_command("docker")
    runtime.compose(ctx, "build", "api")
    runtime.compose(ctx, "up", "--detach", "--wait", "postgres")

    for one_shot in ("db-role-init", "migrate", "db-permissions"):
        runtime.info(f"Running one-shot {one_shot} for {ctx.environment}...")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
