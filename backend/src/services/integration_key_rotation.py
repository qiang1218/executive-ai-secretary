"""Integration-key rotation is **not yet implemented** in this revision.

Consumer contract
=================

* :data:`INTEGRATION_ROTATION_ADVISORY_LOCK` — stable string constant naming
  the PostgreSQL advisory lock; already exposed for tests today.
* :func:`rotate_integration_keys` / :func:`verify_integration_key_version`
  — not implemented yet; callers receive :class:`NotImplementedError`.

When the real implementation lands, replace this stub and drop the
``pytestmark = pytest.mark.skip`` headers from
``tests/test_*integration_key_rotation*.py``.
"""
from __future__ import annotations

from typing import Any

# Stable identifier used by the (future) Postgres advisory-lock acquisition flow
# and consumed by tests today via a constant lookup.
INTEGRATION_ROTATION_ADVISORY_LOCK = "integration_key_rotation_lock"

_REASON = (
    "rotate_integration_keys / verify_integration_key_version are not yet "
    "implemented. See services/integration_key_rotation.py docstring for context."
)


def rotate_integration_keys(*args: Any, **kwargs: Any) -> Any:
    """Pending implementation — raises :class:`NotImplementedError`.

    Signature kept permissively-typed to mirror the future contract while we
    have no concrete shape yet. See the module docstring for the migration
    plan.
    """
    raise NotImplementedError(_REASON)


def verify_integration_key_version(*args: Any, **kwargs: Any) -> Any:
    """Pending implementation — raises :class:`NotImplementedError`."""
    raise NotImplementedError(_REASON)


__all__ = [
    "INTEGRATION_ROTATION_ADVISORY_LOCK",
    "rotate_integration_keys",
    "verify_integration_key_version",
]
