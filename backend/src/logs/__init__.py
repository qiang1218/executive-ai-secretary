"""日志层：``configure_logging`` 与 ``JsonFormatter``。"""

from __future__ import annotations

from . import config as _config

globals().update({k: getattr(_config, k) for k in dir(_config) if not k.startswith("_")})

__all__ = [k for k in dir(_config) if not k.startswith("_")]
