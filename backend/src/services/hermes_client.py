from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import AsyncIterator

import httpx

from configs.settings import Settings, get_settings

logger = logging.getLogger(__name__)


# status_code -> machine-readable code. 5xx 与 4xx 区分，便于审计/call_site 直接
# 落精确 failure_reason_code，不再把"模型名无效 / 限流 / 上游挂"全收口成一个。
_ANSPIRE_STATUS_TO_ERROR_CODE: dict[int, str] = {
    401: "anspire_invalid_api_key",
    403: "anspire_forbidden",
    404: "anspire_model_not_found",
    408: "anspire_request_timeout",
    413: "anspire_request_too_large",
    429: "anspire_rate_limited",
    500: "anspire_internal_error",
    502: "anspire_upstream_bad_gateway",
    503: "anspire_upstream_unavailable",
    504: "anspire_upstream_timeout",
}


def _extract_error_snippet(response: httpx.Response, *, limit: int = 300) -> str:
    """从 Anspire 错误响应里拽出可读片段。优先 JSON 的 ``error.message``。"""
    text = response.text or ""
    if not text:
        return ""
    try:
        body = response.json()
    except ValueError:
        return text[:limit]
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            msg = err.get("message")
            if msg:
                return str(msg)[:limit]
        msg = body.get("message") or body.get("detail")
        if msg:
            return str(msg)[:limit]
    return text[:limit]


class HermesClientError(RuntimeError):
    """worker ``/v1/profile/run`` 失败。携带 status_code 与 machine-readable code
    让上层(``simulate_harness`` 等)能按类别分发最终 HTTP code,不再把所有错误
    收口到一个 422。

    透传约定：worker 端 ``profile_run`` 把 ``HermesRunError.code`` 放进
    ``HTTPException.detail["code"]``;run_profile 把 ``code`` 落到这里。
    """

    def __init__(self, code: str, status_code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass
class HermesStreamEvent:
    """Worker SSE 事件。

    基础事件：delta / tool_start / tool_complete / done / error
    阶段事件：turn_start / turn_end / step / thinking / interim_assistant / status
    阶段事件的附加数据放在 ``data`` 字段中。
    """

    type: str
    content: str = ""
    tool: str | None = None
    args: dict | None = None
    result: object | None = None
    error: str | None = None
    data: dict | None = None


class HermesClient:
    """异步 HTTP 客户端，调 worker SSE。"""

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or get_settings()
        self._base_url = self._settings.worker_base_url
        self._timeout = httpx.Timeout(
            connect=10.0,
            read=self._settings.hermes_timeout_seconds,
            write=10.0,
            pool=10.0,
        )

    async def stream_chat(
        self,
        *,
        conversation_id: str,
        messages: list[dict],
        base_url: str,
        api_key: str,
        model: str,
        enterprise_id: str,
        provider: str = "openai",
        api_mode: str = "chat_completions",
        system_prompt: str | None = None,
        max_iterations: int | None = None,
        max_tokens: int | None = None,
        enabled_toolsets: list[str] | None = None,
        disabled_toolsets: list[str] | None = None,
        mcp_servers: list[dict] | None = None,
    ) -> AsyncIterator[HermesStreamEvent]:
        """流式调用 worker /v1/chat/completions。

        所有 LLM 配置（base_url / api_key / provider / api_mode / model）均由
        调用方从数据库配置中读取并传入，worker 不做全局配置。

        ``enterprise_id`` 会透传给 worker，用于注入 MCP server 子进程 env，
        实现多企业数据隔离。
        """
        payload: dict = {
            "base_url": base_url,
            "api_key": api_key,
            "provider": provider,
            "api_mode": api_mode,
            "model": model,
            "messages": messages,
            "conversation_id": conversation_id,
            "enterprise_id": enterprise_id,
            "max_iterations": max_iterations or self._settings.hermes_max_iterations,
            "stream": True,
        }
        if system_prompt:
            payload["system_prompt"] = system_prompt
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if enabled_toolsets:
            payload["enabled_toolsets"] = enabled_toolsets
        if disabled_toolsets:
            payload["disabled_toolsets"] = disabled_toolsets
        if mcp_servers:
            payload["mcp_servers"] = mcp_servers

        headers = {}
        if self._settings.hermes_api_key:
            headers["Authorization"] = (
                f"Bearer {self._settings.hermes_api_key.get_secret_value()}"
            )

        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
        ) as client:
            async with client.stream(
                "POST",
                "/v1/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = json.loads(line[6:])
                    yield HermesStreamEvent(
                        type=data.get("type", "delta"),
                        content=data.get("content", ""),
                        tool=data.get("tool"),
                        args=data.get("args"),
                        result=data.get("result"),
                        error=data.get("error"),
                        data=data.get("data"),
                    )

    async def health_check(self) -> bool:
        """检查 worker 是否在线。"""
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(5.0),
            ) as client:
                resp = await client.get("/health")
                return resp.status_code == 200
        except Exception:
            return False

    async def run_profile(
        self,
        *,
        profile: str,
        payload: dict,
        base_url: str,
        api_key: str,
        model_id: str,
        endpoint_url: str | None = None,
    ) -> dict:
        """Phase 2: 调用 worker ``/v1/profile/run`` 取代 ``run_hermes`` subprocess。

        返回 dict ``{"text", "model", "input_tokens?", "output_tokens?"}``；
        与旧 ``RunResponse`` 兼容，业务侧用 ``text`` / ``model`` / ``usage``。
        """
        provider_dict: dict = {
            "endpoint_url": endpoint_url or base_url,
            "model_id": model_id,
            "api_key": api_key,
            "provider": "anspire",
        }
        body = {"profile": profile, "payload": payload, "provider": provider_dict}

        headers = {}
        if self._settings.hermes_api_key:
            headers["Authorization"] = (
                f"Bearer {self._settings.hermes_api_key.get_secret_value()}"
            )

        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
        ) as client:
            response = await client.post(
                "/v1/profile/run",
                json=body,
                headers=headers,
            )
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                raise HermesClientError(
                    "harness_worker_invalid_response",
                    response.status_code,
                    f"worker /v1/profile/run invalid JSON: {response.text[:200]}",
                )
            detail = payload.get("detail") if isinstance(payload, dict) else None
            if isinstance(detail, dict):
                code = str(detail.get("code") or "harness_simulation_failed")
                message = str(detail.get("message") or detail)
            else:
                code = (
                    "harness_unauthorized" if response.status_code == 401
                    else "harness_simulation_failed"
                )
                message = str(detail) if detail is not None else response.text
            logger.error(
                "hermes.profile_run.failed status=%s code=%s message=%s",
                response.status_code, code, message,
            )
            raise HermesClientError(code, response.status_code, message)
        data = response.json()
        usage = {
            "prompt_tokens": data.get("input_tokens"),
            "completion_tokens": data.get("output_tokens"),
        }
        return {
            "text": data.get("text") or "",
            "model": data.get("model") or model_id,
            "usage": usage,
        }

    async def test_anspire_provider(  # noqa: D401 — third-party gateway ping
        self,
        *,
        endpoint_url: str,
        api_key: str,
        model_id: str,
    ) -> dict:
        """同步测试 Anspire provider 连通性（直连网关 ``/chat/completions``）。

        直连网关，不再依赖 ``hermes-agent`` 子进程。
        """
        import time

        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{endpoint_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model_id,
                        "stream": False,
                        "messages": [
                            {"role": "system", "content": "Reply with only: OK"},
                            {"role": "user", "content": "connection test"},
                        ],
                        # max_tokens + temperature 都故意不传：
                        # - Anspire 的 gpt-5.5 / gpt-5.6-sol 上游只要收到
                        #   max_tokens 字段就 503 GW_SERVICE_UNAVAILABLE；
                        # - 显式 temperature=0 会被 400 GW_REQUEST_INVALID 拒绝
                        #   ("Only the default (1) value is supported")。
                        # 让 provider 用自己默认即可。
                    },
                )
        except httpx.HTTPError as exc:
            latency_ms = round((time.monotonic() - started) * 1000)
            logger.error(
                "anspire_test_unreachable model=%s latency_ms=%s error=%s",
                model_id,
                latency_ms,
                exc,
            )
            raise HermesClientError(
                code="anspire_connection_failed",
                status_code=502,
                message=f"Anspire gateway unavailable: {exc}",
            ) from exc

        latency_ms = round((time.monotonic() - started) * 1000)

        if response.status_code >= 400:
            snippet = _extract_error_snippet(response)
            code = _ANSPIRE_STATUS_TO_ERROR_CODE.get(
                response.status_code, "anspire_connection_failed"
            )
            request_id = response.headers.get("x-request-id") or response.headers.get(
                "x-anspire-request-id"
            )
            logger.error(
                "anspire_test_failed model=%s status=%s code=%s "
                "latency_ms=%s request_id=%s body=%s",
                model_id,
                response.status_code,
                code,
                latency_ms,
                request_id or "-",
                snippet or "-",
            )
            suffix = f": {snippet}" if snippet else ""
            raise HermesClientError(
                code=code,
                status_code=response.status_code,
                message=f"Anspire provider test failed: HTTP {response.status_code} "
                f"({code}){suffix}",
            )
        try:
            result = response.json()
        except ValueError as exc:
            raise RuntimeError("Anspire returned an invalid response") from exc
        if not isinstance(result.get("choices"), list):
            raise RuntimeError("Anspire response does not contain choices")
        return {"status": "success", "latency_ms": latency_ms, "model": model_id}
