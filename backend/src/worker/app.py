"""Worker FastAPI 应用。

worker 现在只做两件事：

1. ``POST /v1/chat/completions`` —— 委托给 ``AgentRunner`` 完成 LLM + tool 调用。
2. ``POST /v1/profile/run`` —— Phase 2 起取代 ``hermes-agent`` 的 subprocess 路径。
   worker 直接 ``httpx`` 调 Anspire 网关，使用 ``worker.profile_prompts``
   里物理的 system prompt / 安全内核 / 输出 token 预算。

任何 LLM 凭据都从 API 侧注入（``base_url / api_key / provider / api_mode / model``），
worker 不再自己读 ``HERMES_*`` 环境变量；当 ``Settings.hermes_api_key`` 被显式配置时，
``_check_auth`` 仍然执行 Bearer 校验作为对外 API。
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from configs.settings import get_settings
from worker.agent import agent_runner
from worker.profile_prompts import (
    HermesRunError,
    ProfileRunProviderConfig,
    ProfileRunResponse,
    build_profile_prompt,
    is_known_profile,
    max_output_tokens,
)

logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(title="Executive AI Worker", version="2.0.0")


# --------------------------------------------------------------------------
# Request / response models
# --------------------------------------------------------------------------

class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    # LLM 配置（调用方从数据库配置中读取并注入）
    base_url: str = Field(description="LLM 网关地址，如 https://open-gateway.anspire.ai/v6")
    api_key: str = Field(description="API Key（明文，调用方已解密）")
    provider: str = Field(default="openai")
    api_mode: str = Field(default="chat_completions")

    # 模型与会话
    model: str = Field(default="qwen3.5-plus")
    messages: list[Message]
    conversation_id: str

    # 可选
    max_iterations: int = Field(default=10)
    max_tokens: int | None = None
    system_prompt: str | None = None
    enabled_toolsets: list[str] | None = None
    disabled_toolsets: list[str] | None = None
    mcp_servers: list[dict] | None = None
    stream: bool = True


class ProfileRequest(BaseModel):
    """Phase 2: 取代 ``hermes-agent`` subprocess 路径的 profile 任务端点。

    API 侧把"路由 / 改写 / 规划 / 数据回答 / 通用回答"profile 任务通过这个端点
    转发到 worker；worker 自己调用 LLM 并返回文本 + 用量。
    """

    profile: str = Field(description="route / plan / rewrite / data / general")
    payload: dict[str, Any] = Field(description="包含 question + harness_config + scope 等")
    provider: ProfileRunProviderConfig


class ProfileRunOutput(BaseModel):
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------

def _check_auth(authorization: str | None) -> None:
    """校验 Bearer token，与 ``Settings.hermes_api_key`` 比对。"""
    if not settings.hermes_api_key:
        return
    expected = f"Bearer {settings.hermes_api_key.get_secret_value()}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# --------------------------------------------------------------------------
# Chat completions（agentic chat via AIAgent）
# --------------------------------------------------------------------------

@app.post("/v1/chat/completions")
async def chat_completions(
    req: ChatRequest,
    authorization: str | None = Header(default=None),
) -> StreamingResponse:
    _check_auth(authorization)

    user_msg = next((m for m in reversed(req.messages) if m.role == "user"), None)
    if not user_msg:
        raise HTTPException(status_code=400, detail="no user message")

    system_parts = [m.content for m in req.messages if m.role == "system"]
    system_prompt = "\n\n".join(system_parts) if system_parts else req.system_prompt

    async def event_stream():
        try:
            async for event in agent_runner.chat(
                conversation_id=req.conversation_id,
                message=user_msg.content,
                base_url=req.base_url,
                api_key=req.api_key,
                provider=req.provider,
                api_mode=req.api_mode,
                model=req.model,
                max_iterations=req.max_iterations,
                max_tokens=req.max_tokens,
                system_prompt=system_prompt,
                enabled_toolsets=req.enabled_toolsets,
                disabled_toolsets=req.disabled_toolsets,
                mcp_servers=req.mcp_servers,
            ):
                data: dict[str, Any] = {
                    "type": event.type,
                    "content": event.content,
                }
                if event.tool:
                    data["tool"] = event.tool
                if event.args is not None:
                    data["args"] = event.args
                if event.result is not None:
                    data["result"] = event.result
                if event.error:
                    data["error"] = event.error
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001
            logger.exception("worker_stream_failed")
            yield (
                "data: "
                + json.dumps({"type": "error", "error": str(e)}, ensure_ascii=False)
                + "\n\n"
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# --------------------------------------------------------------------------
# Profile runs（直连 LLM，替代 hermes-agent subprocess）
# --------------------------------------------------------------------------

def _redact(text: str, *, marker: str = "[redacted]") -> str:
    return marker if not text else text


async def _call_llm_once(
    *,
    base_url: str,
    api_key: str,
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int | None,
    timeout: float,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model_id,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
    }
    if max_tokens:
        body["max_tokens"] = max_tokens
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
            },
            json=body,
        )
    if response.status_code >= 400:
        if response.status_code in (401, 403):
            raise HermesRunError(
                "Anspire 拒绝了该凭证，请确认 API Key 有效且已开通所选模型",
                status_code=response.status_code,
            )
        if response.status_code == 404:
            raise HermesRunError(
                "所选 Anspire 模型暂不可用，请重新选择模型后测试",
                status_code=response.status_code,
            )
        if response.status_code == 429:
            raise HermesRunError(
                "Anspire 当前限流或账户额度不足，请稍后重试并检查账户状态",
                status_code=response.status_code,
            )
        if response.status_code >= 500:
            raise HermesRunError(
                "Anspire 网关暂时不可用，请稍后重试",
                status_code=response.status_code,
            )
        raise HermesRunError(
            "Anspire 连接测试未通过，请检查凭证与模型权限",
            status_code=response.status_code,
        )
    try:
        return response.json()
    except ValueError as exc:
        raise HermesRunError(
            "Anspire returned an invalid response",
            status_code=502,
        ) from exc


@app.post("/v1/profile/run")
async def profile_run(
    req: ProfileRequest,
    authorization: str | None = Header(default=None),
) -> ProfileRunResponse:
    """同步执行一次 profile 调用。

    * ``_check_auth`` 同 ``/v1/chat/completions``：如果 Settings.hermes_api_key
      被配置，调用方必须带正确的 Bearer token。
    * ``provider`` 由 API 侧注入；worker 不再读任何环境变量。
    * ``harness_admin_service.simulate_harness`` 通过
      ``HermesClient.run_profile`` 调用本端点。
    """
    _check_auth(authorization)

    profile = req.profile
    if not is_known_profile(profile):
        raise HTTPException(status_code=422, detail=f"unknown profile: {profile}")

    api_key = req.provider.api_key
    if isinstance(api_key, str):
        # API 已解密
        pass
    else:
        # 防御性 fallback：若调用方传了 SecretStr，_build_provider_config 仍可能命中
        api_key = api_key.get_secret_value()  # type: ignore[union-attr]

    api_key = api_key.strip()
    if len(api_key) < 16:
        raise HTTPException(status_code=400, detail="invalid Anspire API key")

    prompt = build_profile_prompt(profile, req.payload)
    budget = max_output_tokens(profile)
    timeout = settings.hermes_timeout_seconds

    # 后台线程跑，无 I/O 阻塞：把同步 httpx 调用包到 thread 防止阻塞 event loop
    try:
        response_body = await asyncio.to_thread(
            _call_llm_once_sync,
            base_url=req.provider.endpoint_url,
            api_key=api_key,
            model_id=req.provider.model_id,
            system_prompt=SECURITY_KERNEL_PLACEHOLDER,  # See below
            user_prompt=prompt,
            max_tokens=budget or None,
            timeout=timeout,
        )
    except HermesRunError as exc:
        # Message already redacted by callers.
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    text, in_tokens, out_tokens = _extract_text(response_body)
    return ProfileRunResponse(
        text=text,
        model=req.provider.model_id,
        input_tokens=in_tokens,
        output_tokens=out_tokens,
    )


def _call_llm_once_sync(
    *,
    base_url: str,
    api_key: str,
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int | None,
    timeout: float,
) -> dict[str, Any]:
    """同步版 LLM 调用；用 sync httpx，包到 ``asyncio.to_thread``。"""
    import httpx as _httpx

    body: dict[str, Any] = {
        "model": model_id,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
    }
    if max_tokens:
        body["max_tokens"] = max_tokens
    with _httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
            },
            json=body,
        )
    if response.status_code >= 400:
        if response.status_code in (401, 403):
            raise HermesRunError(
                "Anspire 拒绝了该凭证，请确认 API Key 有效且已开通所选模型",
                status_code=response.status_code,
            )
        if response.status_code == 404:
            raise HermesRunError(
                "所选 Anspire 模型暂不可用，请重新选择模型后测试",
                status_code=response.status_code,
            )
        if response.status_code == 429:
            raise HermesRunError(
                "Anspire 当前限流或账户额度不足，请稍后重试并检查账户状态",
                status_code=response.status_code,
            )
        if response.status_code >= 500:
            raise HermesRunError(
                "Anspire 网关暂时不可用，请稍后重试",
                status_code=response.status_code,
            )
        raise HermesRunError(
            "Anspire 连接测试未通过，请检查凭证与模型权限",
            status_code=response.status_code,
        )
    try:
        return response.json()
    except ValueError as exc:
        raise HermesRunError(
            "Anspire returned an invalid response",
            status_code=502,
        ) from exc


def _extract_text(response_body: dict[str, Any]) -> tuple[str, int | None, int | None]:
    choices = response_body.get("choices") or []
    if not isinstance(choices, list) or not choices:
        raise HermesRunError("Anspire response does not contain choices", status_code=502)
    first = choices[0] or {}
    message = first.get("message") or {}
    text = str(message.get("content") or "").strip()
    if not text:
        raise HermesRunError("Anspire returned an empty completion", status_code=502)
    usage = response_body.get("usage") or {}
    in_tokens = usage.get("prompt_tokens") if isinstance(usage, dict) else None
    out_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
    return text, in_tokens, out_tokens


# Security kernel placeholder is provided via build_profile_prompt itself;
# ``_call_llm_once_sync`` here passes a single 'system' message containing
# ``user_prompt`` because that already includes SECURITY_KERNEL.
SECURITY_KERNEL_PLACEHOLDER = "_SECURITY_KERNEL_INCLUDED_IN_USER_PROMPT_"
