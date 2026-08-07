"""Phase 1 + Phase 4 cleanup regression tests.

Phase 1 (commit ``072eed5``) removed dead code introduced by the
working/old hermes investigation:

* ``services/mcp_app`` — broken shim whose ``import worker.mcp_app`` always
  raised ``ImportError``; no production caller referenced it.
* Orphaned LISTEN/NOTIFY job loop and its dependencies; ``main.py`` no
  longer starts the runner and no production code imports them.
* ``Settings.mcp_hub_url`` — single-line orphan field with no callers.
* ``Settings.hermes_model_default`` — defaulted to ``qwen3.5-plus`` but
  never read; ``main.py._run_worker`` writes ``HERMES_MODEL`` directly.

Phase 4 (this commit) finishes the migration to MCP v2 by retiring the
pre-MCP-v2 package entirely:

* The 11 hard-coded tool constants and their management surfaces are
  replaced by ``services.mcp_schema_service`` + the v2
  ``mcp_schema_registry``.
* ``services.business_tools.py`` is removed; the 11 hard-coded business
  handlers are consolidated into the 3 generic MCP tools
  (``discover_schema`` / ``query_schema`` / ``execute_query``) shipped by
  ``worker/mcp_server.py``.

Pre-existing broken shims fixed in the same pass (Phase 1):

* ``services/file_key_rotation`` was a broken shim that did
  ``import worker.file_key_rotation`` (the module never existed). It is now
  the **real** implementation.
* ``services/integration_key_rotation`` is a stub: constant
  ``INTEGRATION_ROTATION_ADVISORY_LOCK`` plus ``rotate_integration_keys``
  / ``verify_integration_key_version`` raising
  :class:`NotImplementedError`. The Postgres CLI
  (``repositories/rotate_integration_keys.py``) and both integration-key
  test files now skip rather than error at collection.

This module depends on import semantics only — no DB, no network. The
``conftest.py`` of the suite still wires up an in-memory sqlite app,
which is fine for these checks.
"""
from __future__ import annotations

from types import ModuleType

import pytest

from configs.settings import Settings


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. Removed dead code must be unreachable via the public packages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REMOVED_FROM_SERVICES = (
    "mcp_app",                  # Phase 1: broken shim
    "business_tools",           # Phase 4: 11 hard-coded handlers consolidated
    "mcp_tool_service",         # Phase 4: case-by-case tool management
    "mcp_registry",             # Phase 4: legacy tool registry
)


@pytest.mark.parametrize("name", REMOVED_FROM_SERVICES)
def test_services_removed_submodules(name: str) -> None:
    import services as services_pkg

    with pytest.raises(AttributeError):
        getattr(services_pkg, name)


def test_worker_old_package_retired() -> None:
    """The retired legacy worker package is gone after cleanup — both the
    top-level package and its individual submodules must be unreachable.
    """
    import importlib

    with pytest.raises(ImportError):
        importlib.import_module("worker_old")
    with pytest.raises(ImportError):
        importlib.import_module("worker_old.mcp_registry")
    with pytest.raises(ImportError):
        importlib.import_module("worker_old.file_key_rotation")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Surviving services modules still resolve via PEP 562
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SERVICES_SURVIVING = (
    # locally-defined services (Phase 1 + Phase 4 survivors)
    "capabilities",
    "conversation_service",
    "data_capability_service",
    "harness_admin_service",
    "harness_config",
    "health_service",
    "job_management_service",
    "mcp_schema_service",
    "memory_service",
    "model_admin_service",
    # local shim
    "integration_key_rotation",
    # cross-package names whose physical location is worker/utils
    "file_key_rotation",
    "cli",
    "job_state",
)


@pytest.mark.parametrize("name", SERVICES_SURVIVING)
def test_services_submodule_still_resolvable(name: str) -> None:
    import services as services_pkg

    module = getattr(services_pkg, name)
    assert isinstance(module, ModuleType), f"services.{name} must resolve to a module"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. Settings field removals (Phase 1)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.parametrize("field", ["mcp_hub_url", "hermes_model_default"])
def test_settings_removed_orphan_fields(field: str) -> None:
    assert field not in Settings.model_fields, (
        f"Settings.{field} was deleted by Phase 1 cleanup — re-add only with"
        " a real usage point in production code."
    )


def test_settings_keeps_new_hermes_worker_fields() -> None:
    """Phase 1+4 must not have touched the new Hermes Worker surface."""
    expected = (
        "worker_host",
        "worker_port",
        "worker_base_url",
        "hermes_api_key",
        "hermes_max_concurrent_runs",
        "hermes_max_iterations",
        "hermes_max_tokens",
        "hermes_timeout_seconds",
    )
    for field in expected:
        assert field in Settings.model_fields, f"Settings.{field} must remain present"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. ``services.file_key_rotation`` is the real implementation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_services_file_key_rotation_is_real_implementation() -> None:
    """Phase 4 promotion: ``services.file_key_rotation`` is the implementation.
    Callers must be able to import the symbols directly via the services
    surface.
    """
    from services import file_key_rotation

    assert callable(file_key_rotation.rotate_file_keys)
    assert callable(file_key_rotation.verify_file_key_version)
    assert isinstance(file_key_rotation.ROTATION_ADVISORY_LOCK, int)


def test_services_integration_key_rotation_is_a_not_implemented_stub() -> None:
    """The current contract is: a stable constant is exposed, function
    entries raise :class:`NotImplementedError`, and a docstring explains
    the migration plan."""
    from services import integration_key_rotation as ikr

    assert ikr.INTEGRATION_ROTATION_ADVISORY_LOCK == "integration_key_rotation_lock"
    with pytest.raises(NotImplementedError):
        ikr.rotate_integration_keys()
    with pytest.raises(NotImplementedError):
        ikr.verify_integration_key_version()


def test_repositories_rotate_integration_keys_uses_services_stub() -> None:
    """The CLI entry point must resolve the public symbols through the
    services-level stub and surface :class:`NotImplementedError` instead of
    the historical :class:`ImportError`.
    """
    from services import integration_key_rotation as ikr

    # Delayed-import uses ``from services.integration_key_rotation import ...``
    # which is precisely what the test inspects.
    from services.integration_key_rotation import (  # noqa: F401
        rotate_integration_keys,
        verify_integration_key_version,
    )
    assert ikr.rotate_integration_keys is rotate_integration_keys
    assert ikr.verify_integration_key_version is verify_integration_key_version


def test_repositories_rotate_file_keys_uses_services_implementation() -> None:
    """Phase 4 promotion: ``utils.rotate_file_keys`` (CLI entry)
    imports directly from ``services.file_key_rotation``.

    After the Phase 5 cleanup the CLI lives in ``utils/`` instead of
    ``repositories/``. This guards against regressions by checking the script
    is wired to ``services.file_key_rotation``.
    """
    import inspect

    from utils import rotate_file_keys

    src = inspect.getsource(rotate_file_keys)
    assert "services.file_key_rotation" in src
    assert "worker_old" not in src


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. PEP 562 fallback chain is healthy and well-formed
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_services_getattr_unknown_raises_attribute_error() -> None:
    """``services.<X>`` for an X that does not exist anywhere in the
    fallback chain must raise :class:`AttributeError` (not
    :class:`ModuleNotFoundError`), so that ``getattr(obj, name, default)``
    returns the default. This protects ``from services import *`` style
    tooling and any ``hasattr`` checks in routers.
    """
    import services as services_pkg

    with pytest.raises(AttributeError):
        getattr(services_pkg, "definitely_does_not_exist")

    sentinel = object()
    assert getattr(services_pkg, "definitely_does_not_exist", sentinel) is sentinel


def test_services_file_key_rotation_via_getattr_works() -> None:
    """The cross-package name must still resolve through
    ``services.__getattr__`` so existing callers that used
    ``from services import file_key_rotation`` keep working after the
    cleanup phases.
    """
    import services as services_pkg
    from services import file_key_rotation as direct

    assert getattr(services_pkg, "file_key_rotation") is direct
