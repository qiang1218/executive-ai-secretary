"""配置层：``Settings`` 与环境变量加载。

真实代码位于 ``configs.settings`` 模块；本 ``__init__`` 把
``Settings`` / ``get_settings`` 等顶层符号 re-export 出来。
"""

from __future__ import annotations

from .settings import Settings, get_settings

# 把 settings 模块中所有"非下划线开头"的符号 re-export 出来，方便
# ``from configs import Settings`` 这种顶层访问。
from . import settings as _settings

globals().update({k: getattr(_settings, k) for k in dir(_settings) if not k.startswith("_")})

__all__ = [k for k in dir(_settings) if not k.startswith("_")]
