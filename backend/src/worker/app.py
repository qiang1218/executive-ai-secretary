"""Worker FastAPI 应用。

提供 OpenAI 风格的 ``/v1/chat/completions`` SSE 接口，内部委托给
``AgentRunner`` -> AIAgent 完成实际的 LLM + tool 调用。
"""
from __future__ import annotations

import json
import logging
import sys
from typing import Any

# Windows GBK patch：hermes-agent 内部 subprocess 用 text=True 时会 GBK 解码失败
if sys.platform == "win32":
    import subprocess

    _orig_popen_init = subprocess.Popen.__init__

    def _patched_popen_init(self, *args, **kwargs):
        if kwargs.get("text") or kwargs.get("universal_newlines"):
            kwargs.setdefault("encoding", "utf-8")
            kwargs.setdefault("errors", "replace")
        _orig_popen_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _patched_popen_init

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from configs.settings import get_settings
from worker.agent import agent_runner

logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(title="Executive AI Worker", version="1.0.0")


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    # ── LLM 配置（由调用方从数据库配置中读取并传入）──
    base_url: str = Field(description="LLM 网关地址，如 https://open-gateway.anspire.ai/v6")
    api_key: str = Field(description="API Key（明文，调用方已解密）")
    provider: str = Field(default="openai", description="Provider 类型")
    api_mode: str = Field(default="chat_completions", description="API 模式")

    # ── 模型与会话 ──
    model: str = Field(default="qwen3.5-plus")
    messages: list[Message]
    conversation_id: str

    # ── 可选参数 ──
    max_iterations: int = Field(default=10)
    max_tokens: int | None = None
    system_prompt: str | None = None
    enabled_toolsets: list[str] | None = None
    disabled_toolsets: list[str] | None = None
    mcp_servers: list[dict] | None = None
    stream: bool = True


def _check_auth(authorization: str | None) -> None:
    """校验 Bearer token，与 ``HERMES_API_KEY`` 比对。"""
    if not settings.hermes_api_key:
        return
    expected = f"Bearer {settings.hermes_api_key.get_secret_value()}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(
    req: ChatRequest,
    authorization: str | None = Header(default=None),
) -> StreamingResponse:
    _check_auth(authorization)

    # 取最后一条 user message 作为本次输入
    user_msg = next((m for m in reversed(req.messages) if m.role == "user"), None)
    if not user_msg:
        raise HTTPException(status_code=400, detail="no user message")

    # 合并多条 system message；若没有则回退到请求体的 system_prompt
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
                f"{json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}"
                "\n\n"
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
