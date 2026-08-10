"""工具与运维脚本包，CLI 通过 ``__getattr__`` 转发子模块符号。

注意：本包名 ``utils`` 与 hermes-agent 的 site-packages/utils.py 同名。
hermes 内部 ``from utils import base_url_hostname`` 会命中本包，因此
``__getattr__`` 在本包子模块未命中时，回退到 hermes 的单文件 utils.py
加载符号，保证 hermes 调用链正常。
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

_LOCAL = (
    "cli",
    "personal_data_migration",
    "rotate_file_keys",
    "rotate_integration_keys",
)
_SERVICES = ("job_state",)


def _load_hermes_utils() -> Any:
    """加载 site-packages/utils.py（hermes 的单文件 utils）。

    用 importlib.util 显式加载，避免触发 ``import utils``（会回到本包形成循环）。
    加载后缓存到 sys.modules["utils._hermes"] 以便复用。
    """
    cache_key = "utils._hermes"
    if cache_key in sys.modules:
        return sys.modules[cache_key]
    # 通过 spec 从文件加载，module 名用别名避免与本包冲突
    for p in sys.path:
        candidate = Path(p) / "utils.py"
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location(cache_key, candidate)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[cache_key] = mod
                spec.loader.exec_module(mod)
                return mod
    raise ImportError("hermes site-packages/utils.py not found on sys.path")


def __getattr__(name: str) -> Any:
    # 子模块名直接转发（避免触发其他子模块的 import 链）
    if name in _LOCAL:
        return importlib.import_module(f"utils.{name}")
    if name in _SERVICES:
        return importlib.import_module(f"services.{name}")
    # 优先从 hermes 的 site-packages/utils.py 加载（避免遍历子模块触发
    # cli.py 等重 import 链）
    try:
        hermes_utils = _load_hermes_utils()
    except ImportError:
        hermes_utils = None
    if hermes_utils is not None and hasattr(hermes_utils, name):
        return getattr(hermes_utils, name)
    # 最后兜底：遍历本包子模块
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
