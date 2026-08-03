"""FastAPI 应用工厂：负责装配中间件、异常处理、路由与生命周期。

``backend/main.py`` 中的 ``app = create_app(routes, middlewares)`` 是入口；
此函数被 :mod:`api.__init__` 重新暴露，便于在测试与文档生成脚本中复用。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import ORJSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from repositories.audit_integrity import initialize_audit_chains
from services.authz import csrf_protect
from db.session import engine
from exceptions.errors import (
    AppError,
    app_error_handler,
    http_error_handler,
    validation_error_handler,
)
from logs.config import configure_logging
from middleware import RequestContextMiddleware

from configs.settings import get_settings


def _build_lifespan() -> object:
    """构造 lifespan 上下文管理器：在启动时初始化审计链、校验关键密钥。"""

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        settings = get_settings()
        # 启动期校验：unsafe production 值会在这里 fail closed。
        settings.decoded_file_encryption_key()
        settings.integration_encryption_keys()
        if len(settings.hermes_runtime_hmac_key.get_secret_value()) < 32:
            raise RuntimeError("HERMES_RUNTIME_HMAC_KEY must contain at least 32 characters")
        with engine.begin() as connection:
            initialize_audit_chains(connection)
        yield

    return lifespan


def _build_openapi(app: FastAPI) -> Callable[[], dict]:
    """构造自定义 ``openapi()``：追加 sessionCookie 安全方案与 ``X-CSRF-Token`` 必填约束。"""

    settings = get_settings()

    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        components = schema.setdefault("components", {})
        schemes = components.setdefault("securitySchemes", {})
        schemes["sessionCookie"] = {
            "type": "apiKey",
            "in": "cookie",
            "name": settings.session_cookie_name,
            "description": (
                "HttpOnly opaque session token. Unsafe requests also require X-CSRF-Token."
            ),
        }
        for path, methods in schema.get("paths", {}).items():
            if path.startswith(settings.api_prefix) and path != f"{settings.api_prefix}/auth/login":
                for operation in methods.values():
                    if isinstance(operation, dict):
                        operation.setdefault("security", [{"sessionCookie": []}])
        app.openapi_schema = schema
        return schema

    return custom_openapi


def create_app(routes: object | None = None, middlewares: object | None = None) -> FastAPI:
    """装配并返回 ``FastAPI`` 实例。

    参数:
        routes: 路由模块对象（应提供 ``public_routers`` / ``protected_routers``
                两个列表，或 ``all_routers`` 一个列表）。
        middlewares: 中间件模块对象（提供 ``BaseHTTPMiddleware`` 子类即可被自动注册）。
    """
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="董事长人工智能研究员 API",
        description=(
            "企业经营决策工作台正式 API。所有业务接口均使用服务端 Session、CSRF 与数据范围校验。"
        ),
        version=settings.app_version,
        default_response_class=ORJSONResponse,
        lifespan=_build_lifespan(),
        docs_url="/api/docs" if settings.app_mode != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.app_mode != "production" else None,
    )

    # 1) 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID", "Idempotency-Key"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    app.add_middleware(RequestContextMiddleware)

    # 2) 额外中间件（来自 ``middlewares`` 模块，BaseHTTPMiddleware 子类）
    if middlewares is not None:
        from starlette.middleware.base import BaseHTTPMiddleware

        for name in dir(middlewares):
            obj = getattr(middlewares, name, None)
            if (
                isinstance(obj, type)
                and issubclass(obj, BaseHTTPMiddleware)
                and obj is not BaseHTTPMiddleware
            ):
                app.add_middleware(obj)

    # 3) 异常处理
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    # 4) 路由
    protected_dependencies = [Depends(csrf_protect)]
    if routes is not None:
        # 公共路由（无 CSRF）
        for router in getattr(routes, "public_routers", []):
            app.include_router(router)
        # 受保护路由（带 prefix + CSRF）
        protected = getattr(routes, "protected_routers", None)
        if protected is None:
            protected = getattr(routes, "all_routers", [])
        for router in protected:
            app.include_router(
                router,
                prefix=settings.api_prefix,
                dependencies=protected_dependencies,
            )

    # 5) OpenAPI 自定义
    app.openapi = _build_openapi(app)  # type: ignore[assignment]

    return app


# 兼容：直接 ``from api.main import app`` 仍然可用，但默认实例不带任何路由
# —— 真正启用的实例由 :func:`api.create_app` 在 ``backend/main.py`` 中生成。
app: FastAPI | None = None


__all__ = ["app", "create_app"]
