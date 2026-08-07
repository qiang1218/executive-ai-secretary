"""Integration-key rotation is **not yet implemented** in this revision.

History
=======

* 在旧架构中,``worker_old.integration_key_rotation`` 应该是真正实现,
  但该文件从未提交(in git log 里没有任何 commit 添加或删除过它)。
* ``services.integration_key_rotation`` 之前是一个 broken shim,
  ``import worker.integration_key_rotation`` — 而 ``worker/`` 包下也不存在该模块,
  因此任何 ``from services.integration_key_rotation import ...`` 在 collection 阶段
  就会抛 ``ModuleNotFoundError``,让多个测试 + admin CLI ``rotate-integration-keys``
  早就不可用。
* Phase 1 顺手把它清理掉:保留顶层常量 ``INTEGRATION_ROTATION_ADVISORY_LOCK`` 以便
  consumer 可以 ``import`` 但不爆栈,函数入口给出一致的 ``NotImplementedError``,
  在 ``TODO(message)`` 注释里指向未来实现。

Consumer contract
=================

* :data:`INTEGRATION_ROTATION_ADVISORY_LOCK` — 字符串常量,PostgreSQL advisory lock name;
  已经稳定因此保留并可被 :mod:`tests.test_postgres_integration_key_rotation` 使用.
* :func:`rotate_integration_keys` / :func:`verify_integration_key_version`
  — 暂未实现,调用方会收到 :class:`NotImplementedError`.

何时去掉这段说明
================

当 ``services.integration_key_rotation`` 真正实现后(应在 worker 包或 worker_old 包
先落地,再通过 shim 或 import alias 上挂),把此 stub 替换为实现,并移除各个
``tests/test_*integration_key_rotation*.py`` 顶部的 ``pytestmark = pytest.mark.skip``。
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
