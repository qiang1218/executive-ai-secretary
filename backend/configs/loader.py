"""Configuration loader for `backend/configs/`.

Phase 1 (current): skeleton. Defines the public API that
`executive_ai_api.config` will call once Phase 1 is complete.

Phase 1 completion (future commits):
- `load_active_profile()` reads APP_ENV (or APP_PROFILE) from env,
  picks the matching `profile.<env>.yaml`, layers in secret-file
  references, returns a validated `AppConfig` instance.
- `validate_only` flag is used by container entrypoint
  `python -m executive_ai_api.configs.loader --validate` to fail
  fast on bad config without starting the app.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .schema import AppConfig

CONFIG_DIR = Path(__file__).resolve().parent
PROFILES_DIR = CONFIG_DIR


def profile_path(env: str) -> Path:
    return PROFILES_DIR / f"profile.{env}.yaml"


def load_active_profile(env: str | None = None) -> AppConfig:  # pragma: no cover - skeleton
    """Load the profile for the given env. Implemented in Phase 1 completion."""
    raise NotImplementedError(
        "load_active_profile() is a Phase 1 skeleton. "
        "Until Phase 1 is complete, configuration continues to be read "
        "by executive_ai_api.config.Settings from environment variables."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the active profile and exit (used by container entrypoint).",
    )
    parser.add_argument(
        "--env",
        help="Override APP_ENV for this invocation (default: read from environment).",
    )
    args = parser.parse_args(argv)
    if args.validate:
        # Phase 1 skeleton: surface a clear error so users know the migration
        # is in progress, not silently falling back to legacy behavior.
        print(
            "ERROR: --validate is a Phase 1 completion target. "
            "Until then, configuration is loaded by executive_ai_api.config.Settings.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
