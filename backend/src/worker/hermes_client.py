from __future__ import annotations

import json
from typing import Any

from configs.settings import Settings
from worker.hermes_runtime import (
    HermesRunError,
    ProviderConfig,
    RunResponse,
    execute_provider_test,
    execute_run,
)


class HermesRuntimeError(RuntimeError):
    def __init__(self, code: str, message: str, *, permanent: bool = False) -> None:
        self.code = code
        self.permanent = permanent
        super().__init__(message)


def _build_provider_config(provider_config: dict[str, str]) -> ProviderConfig:
    """把 worker 侧的 dict 参数转换成 ProviderConfig 对象。"""
    try:
        return ProviderConfig(
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
    """进程内直接调用 execute_run（原 hermes-runtime 逻辑）。"""
    config = _build_provider_config(provider_config)

    try:
        result: RunResponse = execute_run(
            profile=profile,
            payload=payload,
            request_id=request_id,
            provider_config=config,
            timeout=settings.hermes_timeout_seconds,
        )
    except HermesRunError as exc:
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
    """进程内直接调用 execute_provider_test。"""
    config = _build_provider_config(provider_config)

    try:
        return execute_provider_test(config)
    except HermesRunError as exc:
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
