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
import os
import subprocess
import sys
from pathlib import Path

# 强制 UTF-8 编码，避免 Windows 中文系统下 subprocess 用 gbk 解码子进程输出
# 失败（UnicodeDecodeError: 'gbk' codec can't decode byte ...）。
# PYTHONUTF8/PYTHONIOENCODING 会对所有子进程生效（MCP server 等）；
# reconfigure 则让当前进程的标准流也用 utf-8。
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Monkey-patch subprocess.Popen：当调用方用 text=True/universal_newlines=True
# 但未显式指定 encoding 时，自动注入 encoding="utf-8", errors="replace"。
# 这从根源上消除 Windows 中文系统下 gbk 解码子进程输出导致的崩溃
# （Python UTF-8 模式需在解释器启动前设置，对当前已运行进程无效，
#  因此用 monkey-patch 兜底）。
_OrigPopenInit = subprocess.Popen.__init__


def _utf8_popen_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
    if (
        kwargs.get("text") or kwargs.get("universal_newlines")
    ) and "encoding" not in kwargs:
        kwargs["encoding"] = "utf-8"
        kwargs.setdefault("errors", "replace")
    return _OrigPopenInit(self, *args, **kwargs)


subprocess.Popen.__init__ = _utf8_popen_init  # type: ignore[method-assign]

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
    import uvicorn

    from worker.app import app as worker_app

    settings = get_settings()
    uvicorn.run(
        worker_app,
        host=settings.worker_host,
        port=settings.worker_port,
        reload=False,
        log_level=settings.log_level.lower(),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
