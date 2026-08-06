from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import AsyncIterator

import httpx

from configs.settings import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class HermesStreamEvent:
    """Worker SSE 事件。"""

    type: str  # "delta" | "tool_start" | "tool_complete" | "done" | "error"
    content: str = ""
    tool: str | None = None
    args: dict | None = None
    result: object | None = None
    error: str | None = None


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
        """
        payload: dict = {
            "base_url": base_url,
            "api_key": api_key,
            "provider": provider,
            "api_mode": api_mode,
            "model": model,
            "messages": messages,
            "conversation_id": conversation_id,
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
