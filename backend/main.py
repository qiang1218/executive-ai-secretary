"""项目根启动入口。

启动方式：

- ``python main.py``  —— 走 ``uvicorn.run``，从 ``configs.settings`` 读 host/port/reload/workers
- ``uvicorn main:app --reload`` —— 走 ASGI，``app`` 由 ``api.create_app`` 装配

``api/main.py`` 不再保留：所有装配逻辑（中间件 / 路由 / 异常 / 生命周期）
都集中在 ``api/registries/register.py`` 的 ``Register`` 类中。
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# 必须在 sys.path 注入之后导入；否则 ``from api import ...`` 会失败。
from api import Register, create_app, middlewares, routes  # noqa: E402
from configs.settings import get_settings  # noqa: E402

# 对外暴露的 ``app`` 实例：uvicorn / gunicorn 都直接 ``main:app`` 引用即可。
app = create_app(routes, middlewares)

__all__ = ["app", "Register", "create_app", "middlewares", "routes"]


def _uvicorn_target() -> str:
    """``uvicorn`` 期望 ``module:attr`` 字符串以启用 ``--reload``。"""

    return f"{Path(__file__).stem}:app"


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        _uvicorn_target(),
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        workers=settings.api_workers,
        log_level=settings.log_level.lower(),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
