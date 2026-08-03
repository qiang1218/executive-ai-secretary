"""Register：按 anspire 风格集中装配 FastAPI 路由、中间件与生命周期。

``Register`` 仅是 ``create_app`` 背后的"组织者"——它记录 ``app`` 实例与
``routes``、``middlewares`` 列表，便于在测试或替代入口处复用装配步骤。
真正的装配逻辑仍位于 :func:`api.main.create_app`，这与 ``backend/main.py``
中 ``app = create_app(routes, middlewares)`` 的调用顺序一致。
"""

from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware

from configs.settings import get_settings


class Register:
    """集中持有 ``FastAPI`` 实例、路由集合与中间件集合的注册器。"""

    def __init__(
        self,
        app: FastAPI,
        routes_module: object | None = None,
        middlewares_module: object | None = None,
    ) -> None:
        self._app = app
        self._routes_module = routes_module
        self._middlewares_module = middlewares_module
        self._settings = get_settings()

    # ---- 路由 ---------------------------------------------------------------
    def set_public_routers(self) -> None:
        """注册无需鉴权/CSRF 的公共路由。"""
        for router in self._collect_routers("public_routers"):
            self._app.include_router(router)

    def set_protected_routers(self) -> None:
        """注册需 CSRF 保护的路由。"""
        from fastapi import Depends

        from services.authz import csrf_protect

        dependencies = [Depends(csrf_protect)]
        for router in self._collect_routers("protected_routers"):
            self._app.include_router(
                router,
                prefix=self._settings.api_prefix,
                dependencies=dependencies,
            )

    def set_router(self) -> None:
        """一次性注册所有路由。"""
        self.set_public_routers()
        self.set_protected_routers()

    def _collect_routers(self, attr: str) -> list:
        if self._routes_module is None:
            return []
        routers = getattr(self._routes_module, attr, None)
        if routers is None:
            return list(getattr(self._routes_module, "all_routers", []))
        return list(routers)

    # ---- 中间件 -------------------------------------------------------------
    def set_extra_middlewares(self) -> None:
        """注册 routes/middlewares 中显式声明的额外中间件类（BaseHTTPMiddleware 子类）。"""
        if self._middlewares_module is None:
            return
        for name in dir(self._middlewares_module):
            obj = getattr(self._middlewares_module, name, None)
            if isinstance(obj, type) and issubclass(obj, BaseHTTPMiddleware) and obj is not BaseHTTPMiddleware:
                self._app.add_middleware(obj)

    # ---- 后台任务占位 -------------------------------------------------------
    def start_background_tasks(self) -> None:
        """后台任务入口占位：当前版本不启用线程型后台任务，统一交给外部 worker。"""
        return None

    def stop_background_tasks(self) -> None:
        """后台任务停止占位。"""
        return None
