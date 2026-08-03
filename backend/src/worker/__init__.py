"""异步 Worker 入口：Hermes 客户端、MCP、密钥轮换。

注意：worker 与 services 之间存在双向依赖（``services.business_tools`` 需要
``worker.mcp_registry`` 的工具元数据；``worker.mcp_app`` 需要
``services.business_tools.execute_business_tool`` 执行工具）。

为避免循环导入，本 ``__init__`` **不主动 import 子模块**，仅在通过
``worker.<X>`` 显式访问时通过 ``__getattr__`` 懒加载。
"""

from __future__ import annotations

import importlib
from typing import Any

_SUBMODULE_NAMES = (
    "file_key_rotation",
    "hermes_client",
    "integration_key_rotation",
    "mcp_app",
    "mcp_registry",
)


def __getattr__(name: str) -> Any:
    if name in _SUBMODULE_NAMES:
        return importlib.import_module(f"worker.{name}")
    # 在子模块中查找符号
    for sub_name in _SUBMODULE_NAMES:
        try:
            sub = importlib.import_module(f"worker.{sub_name}")
        except ImportError:
            continue
        if hasattr(sub, name):
            return getattr(sub, name)
    raise AttributeError(f"module 'worker' has no attribute {name!r}")


__all__ = list(_SUBMODULE_NAMES)
