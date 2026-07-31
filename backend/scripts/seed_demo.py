"""Seed sanitized local-demo business fixtures for a given enterprise.

Replaces scripts/seed-demo.sh.  The real seeding work is performed by
``api.seed.seed()`` running inside the ``seed-demo`` Compose profile.
This script only validates the operator's intent and dispatches the
one-shot service.
"""

from __future__ import annotations

import argparse
import os
import sys

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND_DIR)

from scripts import runtime  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--environment",
        choices=runtime.SUPPORTED_ENVIRONMENTS,
        default="local-demo",
    )
    parser.add_argument(
        "--enterprise-slug",
        required=True,
        help="Existing enterprise slug under which fixtures are seeded.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the explicit-confirmation prompt (NOT recommended in shared scripts).",
    )
    args = parser.parse_args()

    if args.environment != "local-demo":
        runtime.die("demo seed is permitted only for local-demo")
    runtime.validate_enterprise_slug(args.enterprise_slug)
    expected_confirmation = f"SEED {args.environment}/{args.enterprise_slug}"
    if not args.yes:
        runtime.info(
            "This will seed sanitized demo fixtures. To confirm non-interactively, "
            f"pass --yes or re-run with the literal confirmation string "
            f"\"{expected_confirmation}\" as the last argument."
        )
        try:
            typed = input(f"Type {expected_confirmation!r} to continue: ")
        except EOFError as exc:
            raise SystemExit(f"aborted: {exc}") from exc
        if typed != expected_confirmation:
            runtime.die("confirmation string did not match")

    ctx = runtime.load_context(args.environment)
    runtime.compose(
        ctx,
        "--profile",
        "demo-seed",
        "run",
        "--rm",
        "-e",
        f"DEMO_ENTERPRISE_SLUG={args.enterprise_slug}",
        "seed-demo",
    )
    runtime.info(
        "Sanitized demo fixtures seeded. This command does not create a default password."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
