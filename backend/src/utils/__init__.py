"""工具与运维脚本包，CLI 通过 ``__getattr__`` 转发子模块符号。"""
from __future__ import annotations

import importlib
from typing import Any

_LOCAL = (
    "cli",
    "personal_data_migration",
    "rotate_file_keys",
    "rotate_integration_keys",
)
_SERVICES = ("job_state",)


def __getattr__(name: str) -> Any:
    if name in _LOCAL:
        return importlib.import_module(f"utils.{name}")
    if name in _SERVICES:
        return importlib.import_module(f"services.{name}")
    for sub_name in _LOCAL:
        try:
            sub = importlib.import_module(f"utils.{sub_name}")
        except ImportError:
            continue
        if hasattr(sub, name):
            return getattr(sub, name)
    for sub_name in _SERVICES:
        try:
            sub = importlib.import_module(f"services.{sub_name}")
        except ImportError:
            continue
        if hasattr(sub, name):
            return getattr(sub, name)
    raise AttributeError(f"module 'utils' has no attribute {name!r}")


__all__ = list(_LOCAL + _SERVICES)
