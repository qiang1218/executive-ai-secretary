"""项目根启动入口。

启动方式：

- ``python main.py``                     默认，启动 API（走 uvicorn）
- ``python main.py --worker``            只启动 worker（uvicorn worker.app:app）
- ``python main.py --api``               显式指定启动 API（与无参数相同）
- ``python main.py --api --worker``      同时启动两个进程（开发模式，multiprocessing）
- ``uvicorn main:app --reload``          走 ASGI，``app`` 由 ``api.create_app`` 装配

``api/main.py`` 不再保留：所有装配逻辑（中间件 / 路由 / 异常 / 生命周期）
都集中在 ``api/registries/register.py`` 的 ``Register`` 类中。
"""

from __future__ import annotations

import argparse
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


def _worker_target() -> str:
    """worker 的 uvicorn import 字符串。``worker.app`` 必须暴露 ``app``。"""

    return "worker.app:app"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executive AI Secretary — API + Worker 启动入口",
    )
    parser.add_argument(
        "--worker",
        action="store_true",
        help="启动 Hermes Worker（uvicorn worker.app:app）。默认仅启动 API。",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="显式指定启动 API。与 --worker 配合可同时启动两个进程（开发模式）。",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settings = get_settings()

    start_worker = args.worker
    # 无参数或 --api 都启动 API；只有 --worker 时不启动 API。
    start_api = args.api or not args.worker

    # ── 同时启动 API + Worker（开发模式，multiprocessing） ─────────
    if start_api and start_worker:
        import multiprocessing

        ctx = multiprocessing.get_context("spawn")
        api_proc = ctx.Process(
            target=_run_api,
            name="api",
            daemon=False,
        )
        worker_proc = ctx.Process(
            target=_run_worker,
            name="worker",
            daemon=False,
        )
        api_proc.start()
        worker_proc.start()
        print(f"[main] API pid={api_proc.pid} | Worker pid={worker_proc.pid}")
        try:
            api_proc.join()
        finally:
            if worker_proc.is_alive():
                worker_proc.terminate()
            worker_proc.join()
        return

    # ── 只启动 Worker ──────────────────────────────────────────────
    if start_worker:
        _run_worker()
        return

    # ── 默认 API 模式 ─────────────────────────────────────────────
    _run_api()


def _run_api() -> None:
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


def _run_worker() -> None:
    import os

    import uvicorn

    # 将 hermes 项目的 site-packages 加入 sys.path，使 run_agent / hermes_constants 等私有模块可用。
    _HERMES_VENV_SITE = Path("D:/anchnet/hermes/.venv/Lib/site-packages")
    if _HERMES_VENV_SITE.exists() and str(_HERMES_VENV_SITE) not in sys.path:
        sys.path.insert(0, str(_HERMES_VENV_SITE))

    # Hermes AIAgent 需要的环境变量
    os.environ.setdefault("HERMES_BASE_URL", "https://open-gateway.anspire.ai/v6")
    os.environ.setdefault("HERMES_API_KEY", "sk-bLOrWpvFjVGeNq2o9n1JyW1tVowTSzDs")
    os.environ.setdefault("HERMES_MODEL", "qwen3.5-plus")
    os.environ.setdefault("OPENAI_API_KEY", os.environ["HERMES_API_KEY"])

    settings = get_settings()
    uvicorn.run(
        _worker_target(),
        host=settings.worker_host,
        port=settings.worker_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower(),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
