"""工具层：CLI、密钥轮换脚本、Job 状态、个人数据迁移工具。

注意：``cli`` / ``job_state`` 在本包内；``personal_data_migration`` /
``rotate_file_keys`` / ``rotate_integration_keys`` 物理位于 ``repositories``
包（它们是纯数据访问）。本 ``__init__`` 通过懒加载暴露所有这些子模块。
"""

from __future__ import annotations

import importlib
from typing import Any

# 本地子模块
_LOCAL = ("cli", "job_state")
# 物理位于 repositories 包的子模块
_REPOSITORIES = (
    "personal_data_migration",
    "rotate_file_keys",
    "rotate_integration_keys",
)


def __getattr__(name: str) -> Any:
    if name in _LOCAL:
        return importlib.import_module(f"utils.{name}")
    if name in _REPOSITORIES:
        return importlib.import_module(f"repositories.{name}")
    # 在子模块中查找符号
    for sub_name in _LOCAL + _REPOSITORIES:
        pkg = "utils" if sub_name in _LOCAL else "repositories"
        try:
            sub = importlib.import_module(f"{pkg}.{sub_name}")
        except ImportError:
            continue
        if hasattr(sub, name):
            return getattr(sub, name)
    raise AttributeError(f"module 'utils' has no attribute {name!r}")


__all__ = list(_LOCAL + _REPOSITORIES)
