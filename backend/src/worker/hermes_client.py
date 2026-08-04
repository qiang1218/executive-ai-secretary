from __future__ import annotations

import json
from typing import Any

from configs.settings import Settings


class HermesRuntimeError(RuntimeError):
    def __init__(self, code: str, message: str, *, permanent: bool = False) -> None:
        self.code = code
        self.permanent = permanent
        super().__init__(message)


def _import_hermes_runtime():
    """从 hermes-runtime 目录加载 embedded 模块，避免与 backend 的 main.py 冲突。

    返回 hermes-runtime 的 embedded 模块，包含 execute_run, execute_provider_test,
    ProviderConfig, HermesRunError 等符号。
    """
    import importlib.util
    import sys
    from pathlib import Path

    _runtime_root = Path(__file__).resolve().parents[3] / "hermes-runtime"
    _embedded_path = _runtime_root / "embedded.py"
    if not _embedded_path.exists():
        raise HermesRuntimeError(
            "hermes_unavailable",
            f"hermes-runtime/embedded.py not found at {_runtime_root}",
            permanent=True,
        )
    # 先把 hermes-runtime 目录加入 sys.path，使 embedded.py 内部的 import 能工作
    if str(_runtime_root) not in sys.path:
        sys.path.insert(0, str(_runtime_root))
    spec = importlib.util.spec_from_file_location(
        "hermes_runtime_embedded", _embedded_path
    )
    if spec is None or spec.loader is None:
        raise HermesRuntimeError(
            "hermes_unavailable", "无法加载 hermes-runtime embedded 模块"
        )
    mod = importlib.util.module_from_spec(spec)
    # 注册到 sys.modules，使 pydantic 的类型解析器能正确找到模块级符号
    sys.modules["hermes_runtime_embedded"] = mod
    spec.loader.exec_module(mod)
    return mod


def _build_provider_config(mod, provider_config: dict[str, str]):
    """把 worker 侧的 dict 参数转换成 hermes-runtime 的 ProviderConfig 对象。"""
    try:
        return mod.ProviderConfig(
            provider="anspire",
            endpoint_url=provider_config.get(
                "endpoint_url", "https://open-gateway.anspire.ai/v6"
            ),
            model_id=provider_config["model_id"],
            api_key=provider_config["api_key"],
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise HermesRuntimeError(
            "hermes_invalid_provider_config",
            f"Provider 配置无效：{exc}",
            permanent=True,
        ) from exc


def run_hermes(
    settings: Settings,
    *,
    profile: str,
    payload: dict[str, Any],
    request_id: str,
    provider_config: dict[str, str],
) -> dict[str, Any]:
    """进程内直接调用 hermes-runtime 的 execute_run。

    hermes-runtime 与 worker 在同一 Python 环境中，通过 importlib 加载。
    """
    mod = _import_hermes_runtime()
    config = _build_provider_config(mod, provider_config)

    try:
        result = mod.execute_run(
            profile=profile,
            payload=payload,
            request_id=request_id,
            provider_config=config,
            timeout=settings.hermes_timeout_seconds,
        )
    except mod.HermesRunError as exc:
        permanent = exc.status_code in {400, 401, 403, 404, 422}
        raise HermesRuntimeError(
            "hermes_failed",
            f"Hermes 执行失败：{str(exc)[:1600]}",
            permanent=permanent,
        ) from exc
    except Exception as exc:
        raise HermesRuntimeError("hermes_unavailable", str(exc)) from exc

    return result.model_dump()


def test_anspire_provider(
    settings: Settings,
    provider_config: dict[str, str],
) -> dict[str, Any]:
    """进程内直接调用 hermes-runtime 的 execute_provider_test。"""
    mod = _import_hermes_runtime()
    config = _build_provider_config(mod, provider_config)

    try:
        return mod.execute_provider_test(config)
    except mod.HermesRunError as exc:
        permanent = exc.status_code in {400, 401, 403, 404, 422}
        raise HermesRuntimeError(
            "anspire_connection_failed",
            str(exc)[:1200],
            permanent=permanent,
        ) from exc
    except Exception as exc:
        raise HermesRuntimeError("hermes_unavailable", str(exc)) from exc


def parse_json_response(text: str) -> dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[-1]
        value = value.rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HermesRuntimeError(
            "hermes_invalid_route",
            "Hermes 路由返回了无效结构",
        ) from exc
    if not isinstance(parsed, dict):
        raise HermesRuntimeError("hermes_invalid_route", "Hermes 路由结构无效")
    return parsed
