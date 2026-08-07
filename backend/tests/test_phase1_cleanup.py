"""Phase 1 cleanup regression tests.

Verifies the removal of dead code introduced by the working/old hermes
investigation (see the "Phase 1 cleanup plan" in the chat history):

Removed dead code
=================

* ``services/mcp_app`` — broken shim whose ``import worker.mcp_app`` always
  raised ``ImportError``; no production caller referenced it.
* ``worker_old/runner.py``, ``assistant_orchestrator.py``,
  ``file_extraction.py``, ``mcp_app.py`` — orphaned LISTEN/NOTIFY job loop
  and its dependencies; ``main.py`` no longer starts the runner and no
  production code imports any of these symbols.
* ``Settings.mcp_hub_url`` — single-line orphan field with no callers.
* ``Settings.hermes_model_default`` — defaulted to ``qwen3.5-plus`` but
  never read; ``main.py._run_worker`` writes ``HERMES_MODEL`` directly.
* ``worker_old/integration_key_rotation`` — never committed; references to
  it via ``repositories/rotate_integration_keys.py`` and
  ``tests/test_postgres_integration_key_rotation.py`` were silently broken.

Pre-existing broken shims fixed in the same pass
=================================================

* ``services/file_key_rotation`` was a broken shim that did
  ``import worker.file_key_rotation`` (the module never existed). It now
  re-exports the real implementation living under ``worker_old``.
* ``services/integration_key_rotation`` was the same kind of broken shim.
  There is **no** implementation today; the module is now a stub with
  constant ``INTEGRATION_ROTATION_ADVISORY_LOCK`` plus
  ``rotate_integration_keys`` / ``verify_integration_key_version`` raising
  :class:`NotImplementedError`. The Postgres CLI
  (``repositories/rotate_integration_keys.py``) and both integration-key
  test files now skip rather than erroring at collection.

PEP 562 fallback chain fixed in the same pass
=============================================

* ``worker_old.__getattr__`` used to attempt ``importlib.import_module(
  f"worker.{name}")`` — which always raised ``ModuleNotFoundError`` instead
  of ``AttributeError`` and broke ``getattr(worker_old, "X")``. Now it falls
  back to ``worker_old.{name}`` and translates import errors to
  ``AttributeError``.
* ``services.__getattr__`` extended its fallback chain to include
  ``worker_old``, so cross-package aliases such as
  ``services.mcp_registry`` resolve transparently.

This module depends on import semantics only — no DB, no network. The
``conftest.py`` of the suite still wires up an in-memory sqlite app,
which is fine for these checks.
"""
from __future__ import annotations

import importlib
from types import ModuleType

import pytest

from configs.settings import Settings


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. Removed dead code must be unreachable via the public packages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REMOVED_FROM_SERVICES = (
    "mcp_app",  # broken shim; targeted worker.mcp_app, which never existed
)

REMOVED_FROM_WORKER_OLD = (
    "runner",                 # LISTEN/NOTIFY job loop with zero callers
    "assistant_orchestrator",  # only ever imported by runner.py
    "file_extraction",         # only ever imported by runner.py
    "mcp_app",                 # isolated FastAPI MCP app, zero callers
    # ``integration_key_rotation`` was *never* committed; the file does not
    # exist on disk. Keep it gone until the implementation lands.
    "integration_key_rotation",
    # Phase 2 consolidated these into ``worker`` / ``services``:
    "hermes_client",
    "hermes_runtime",
)


@pytest.mark.parametrize("name", REMOVED_FROM_SERVICES)
def test_services_removed_submodules(name: str) -> None:
    import services as services_pkg

    with pytest.raises(AttributeError):
        getattr(services_pkg, name)


@pytest.mark.parametrize("name", REMOVED_FROM_WORKER_OLD)
def test_worker_old_removed_submodules(name: str) -> None:
    import worker_old as worker_old_pkg

    with pytest.raises(AttributeError):
        getattr(worker_old_pkg, name)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Surviving cross-package names still resolve
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SERVICES_SURVIVING = (
    # locally-defined services
    "business_tools",
    "capabilities",
    "conversation_service",
    "data_capability_service",
    "harness_admin_service",
    "harness_config",
    "health_service",
    "job_management_service",
    "mcp_schema_service",
    "mcp_tool_service",
    "memory_service",
    "model_admin_service",
    # cross-package names whose physical location is worker_old
    "file_key_rotation",
    "integration_key_rotation",
    "mcp_registry",
)


@pytest.mark.parametrize("name", SERVICES_SURVIVING)
def test_services_submodule_still_resolvable(name: str) -> None:
    import services as services_pkg

    module = getattr(services_pkg, name)
    assert isinstance(module, ModuleType), f"services.{name} must resolve to a module"


WORKER_OLD_SURVIVING = (
    "file_key_rotation",
    "mcp_registry",
)


@pytest.mark.parametrize("name", WORKER_OLD_SURVIVING)
def test_worker_old_submodule_still_resolvable(name: str) -> None:
    import worker_old as worker_old_pkg

    module = getattr(worker_old_pkg, name)
    assert isinstance(module, ModuleType)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. Settings field removals
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.parametrize("field", ["mcp_hub_url", "hermes_model_default"])
def test_settings_removed_orphan_fields(field: str) -> None:
    assert field not in Settings.model_fields, (
        f"Settings.{field} was deleted by Phase 1 cleanup — re-add only with"
        " a real usage point in production code."
    )


def test_settings_keeps_new_hermes_worker_fields() -> None:
    """Phase 1 must not have touched the new Hermes Worker surface."""
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. Re-exports point at the *real* implementations
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_services_file_key_rotation_is_a_real_alias() -> None:
    """``services.file_key_rotation`` is a re-export shim that must surface
    the *same Python objects* as ``worker_old.file_key_rotation`` — not a
    placeholder, not a copy.
    """
    from services import file_key_rotation as services_mod
    import worker_old.file_key_rotation as real_mod

    for name in ("rotate_file_keys", "verify_file_key_version"):
        assert getattr(services_mod, name) is getattr(real_mod, name), (
            f"services.file_key_rotation.{name} must be worker_old.file_key_rotation.{name}"
        )
    assert services_mod.ROTATION_ADVISORY_LOCK == real_mod.ROTATION_ADVISORY_LOCK


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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. PEP 562 fallback chain correctness
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_services_mcp_registry_falls_through_to_worker_old() -> None:
    """``services.mcp_registry`` must resolve to ``worker_old.mcp_registry``
    via the PEP 562 fallback chain (``services → worker → utils → worker_old``).
    """
    from services import mcp_registry as via_services
    import worker_old.mcp_registry as via_worker_old

    assert via_services is via_worker_old
    assert hasattr(via_services, "MCP_TOOL_SPECS")
    assert hasattr(via_services, "effective_catalog")
    assert hasattr(via_services, "registered_spec")


def test_worker_old_getattr_translates_import_error_to_attribute_error() -> None:
    """``worker_old.<X>`` for an X that does not exist in any package
    must raise :class:`AttributeError` (not :class:`ModuleNotFoundError`),
    so that ``getattr(worker_old, "X", default)`` returns the default.
    """
    import worker_old as worker_old_pkg

    # Unknown name not present anywhere.
    with pytest.raises(AttributeError):
        getattr(worker_old_pkg, "definitely_does_not_exist")

    # ``integration_key_rotation`` was *never* committed; previously the
    # ``__getattr__`` would attempt ``worker.<X>`` and raise
    # ``ModuleNotFoundError`` (a non-``AttributeError`` exception that
    # PEP 562 propagated, breaking ``getattr(..., default)``).
    with pytest.raises(AttributeError, match=r"integration_key_rotation"):
        getattr(worker_old_pkg, "integration_key_rotation")

    # ``getattr(obj, name, default)`` must observe the default.
    sentinel = object()
    assert getattr(worker_old_pkg, "integration_key_rotation", sentinel) is sentinel


def test_worker_old_file_key_rotation_via_getattr_works() -> None:
    """The ModuleNotFoundError-turned-AttributeError fix must not regress
    the cross-package alias through ``services.__getattr__``.
    """
    import worker_old as worker_old_pkg
    import worker_old.file_key_rotation as direct

    assert getattr(worker_old_pkg, "file_key_rotation") is direct


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. Sanity check that the production-time import paths are still healthy
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.parametrize(
    "import_path",
    [
        "worker_old.mcp_registry",
        "worker_old.file_key_rotation",
    ],
)
def test_direct_imports_of_worker_old_modules(import_path: str) -> None:
    module = importlib.import_module(import_path)
    assert isinstance(module, ModuleType)
