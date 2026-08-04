"""项目根启动入口。

启动方式：

- ``python main.py``                     默认，启动 API（走 uvicorn）
- ``python main.py --worker``            只启动 worker（占用当前进程，不启动 API）
- ``python main.py --worker --api``      同时启动 worker 线程 + API（开发用）
- ``uvicorn main:app --reload``          走 ASGI，``app`` 由 ``api.create_app`` 装配

``api/main.py`` 不再保留：所有装配逻辑（中间件 / 路由 / 异常 / 生命周期）
都集中在 ``api/registries/register.py`` 的 ``Register`` 类中。
"""

from __future__ import annotations

import argparse
import sys
import threading
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executive AI Secretary — API + Worker 启动入口",
    )
    parser.add_argument(
        "--worker",
        action="store_true",
        help="启动后台 worker（轮询 jobs 表并执行任务）。默认仅启动 API。",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="与 --worker 配合使用，同时启动 API（开发模式）。",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # ── Worker 模式 ──────────────────────────────────────────────
    if args.worker:
        # 延迟 import，避免无 worker 依赖时污染 API 启动
        from worker.runner import run_worker, run_worker_in_thread

        if args.api:
            # 开发模式: worker 跑在后台 daemon thread, 前台跑 API
            worker_thread = run_worker_in_thread()
            print(
                f"[main] worker started in background thread "
                f"(daemon={worker_thread.daemon})"
            )
            _start_api()
        else:
            # 纯 worker 模式: 占用当前进程
            print("[main] starting worker (foreground, no API)")
            import traceback

            try:
                run_worker()
            except Exception:
                traceback.print_exc()
                raise
        return

    # ── 默认 API 模式 ─────────────────────────────────────────────
    _start_api()


def _start_api() -> None:
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
