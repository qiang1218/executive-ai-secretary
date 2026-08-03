"""API 顶层包：暴露 ``Register``、``create_app``、``middlewares``、``routes``。

装配顺序：:func:`create_app` 会自动调用 ``configure_logging``、注入
``RequestContextMiddleware``、注册全局异常处理，并按 :mod:`api.routes`
中 ``public_routers`` / ``protected_routers`` 的分组把业务 router 挂载到
``/api/v1`` 之下（公共路由除外）。
"""

from __future__ import annotations

from . import middlewares, routes
from .main import create_app
from .registries import Register

__all__ = ["Register", "create_app", "middlewares", "routes"]
