"""API 路由模块。

注意：``admin_models`` 模块下有两个 ``APIRouter``，分别挂在
``/admin/model-provider``（``admin_models.router``）与
``/admin/models``（``admin_models.models_router``），必须都注册。
"""

from __future__ import annotations

import importlib
from typing import Any

_ROUTE_MODULES = (
    "admin",
    "admin_data",
    "admin_harness",
    "admin_mcp_schema",
    "admin_models",
    "auth",
    "conversations",
    "data",
    "files",
    "health",
    "jobs",
    "memories",
    "models",
    "organizations",
    "projects",
    "reports",
)


def __getattr__(name: str) -> Any:
    """按需懒加载子模块或子模块中的符号。"""
    if name in _ROUTE_MODULES:
        return importlib.import_module(f"api.routes.{name}")
    # 在子模块中查找符号
    for sub_name in _ROUTE_MODULES:
        try:
            sub = importlib.import_module(f"api.routes.{sub_name}")
        except ImportError:
            continue
        if hasattr(sub, name):
            return getattr(sub, name)
    raise AttributeError(f"module 'api.routes' has no attribute {name!r}")


def _all_routers() -> list:
    """加载所有 router 模块并返回 (public, protected) 分组。"""
    health = importlib.import_module("api.routes.health")
    public = [health.router]

    protected_names = [n for n in _ROUTE_MODULES if n != "health"]
    protected = []
    for n in protected_names:
        mod = importlib.import_module(f"api.routes.{n}")
        protected.append(mod.router)
        # admin_models 有第二个 router
        if n == "admin_models" and hasattr(mod, "models_router"):
            protected.append(mod.models_router)
    return public + protected


# 公共路由（无需 CSRF 保护）
public_routers: list = []
# 业务路由（启用 CSRF 保护 + API 前缀）
protected_routers: list = []
# 全部 router
all_routers: list = []


def _ensure_loaded() -> None:
    global public_routers, protected_routers, all_routers
    if not all_routers:
        health = importlib.import_module("api.routes.health")
        public_routers = [health.router]
        protected_names = [n for n in _ROUTE_MODULES if n != "health"]
        protected_routers = []
        for n in protected_names:
            mod = importlib.import_module(f"api.routes.{n}")
            protected_routers.append(mod.router)
            if n == "admin_models" and hasattr(mod, "models_router"):
                protected_routers.append(mod.models_router)
        all_routers = public_routers + protected_routers


_ensure_loaded()


__all__ = list(_ROUTE_MODULES) + ["public_routers", "protected_routers", "all_routers"]
