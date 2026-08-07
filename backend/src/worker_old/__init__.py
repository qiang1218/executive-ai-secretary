"""异步 Worker（旧架构）入口：Hermes 客户端、MCP、密钥轮换。

注意：旧架构 worker 与 services 之间存在双向依赖
（``services.business_tools`` 需要 ``worker_old.mcp_registry`` 的工具元数据）。
新架构已切到 ``worker.app``/``worker.mcp_server``，本包保留作为过渡期间的兼容层。

为避免循环导入，本 ``__init__`` **不主动 import 子模块**，仅在通过
``worker_old.<X>`` 显式访问时通过 ``__getattr__`` 懒加载。

PEP 562 实现要点：

* 当 ``__getattr__`` 抛 ``ModuleNotFoundError`` 时，``getattr(obj, name, default)``
  会把它原样传递给调用方——不像 ``AttributeError`` 那样被捕获并返回 default。
  因此回退路径必须显式捕获 ``ImportError`` 并改抛 ``AttributeError``。
* 旧实现误把 ``worker.<X>`` 当作回退目标，而 ``worker`` 包下根本没有 ``X``，
  这会让任何走 ``getattr(worker_old, "X")`` 的路径爆栈。已修复为回退到
  ``worker_old.<X>``。
"""
from __future__ import annotations

import importlib
from typing import Any

_SUBMODULE_NAMES = (
    "file_key_rotation",
    "mcp_registry",
)


def __getattr__(name: str) -> Any:
    if name in _SUBMODULE_NAMES:
        try:
            return importlib.import_module(f"worker_old.{name}")
        except ImportError as exc:
            raise AttributeError(
                f"module 'worker_old' has no attribute {name!r}"
            ) from exc
    # 在子模块中查找符号
    for sub_name in _SUBMODULE_NAMES:
        try:
            sub = importlib.import_module(f"worker_old.{sub_name}")
        except ImportError:
            continue
        if hasattr(sub, name):
            return getattr(sub, name)
    raise AttributeError(f"module 'worker_old' has no attribute {name!r}")


__all__ = list(_SUBMODULE_NAMES)
