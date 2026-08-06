"""AIAgent 封装层：同步 -> 异步桥接 + 流式回调。

AIAgent 的 ``chat()`` 是同步阻塞方法，``stream_callback`` 是 ``chat()`` 的方法参数
（不是构造参数）。``tool_start_callback`` / ``tool_complete_callback`` 才是构造参数。
本模块通过 ``asyncio.Queue`` + ``run_in_executor`` 把它桥接到异步流式接口。
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator

from run_agent import AIAgent

from worker.session_store import session_store

logger = logging.getLogger(__name__)


@dataclass
class StreamEvent:
    """流式事件。

    - ``delta``: 增量文本片段
    - ``tool_start``: 工具调用开始
    - ``tool_complete``: 工具调用完成
    - ``done``: 整个 chat 结束，``content`` 为最终完整文本
    - ``error``: 发生错误，``error`` 为错误信息
    """

    type: str  # "delta" | "tool_start" | "tool_complete" | "done" | "error"
    content: str = ""
    tool: str | None = None
    args: dict | None = None
    result: Any | None = None
    error: str | None = None


class AgentRunner:
    """封装 AIAgent，提供异步流式接口。"""

    async def chat(
        self,
        *,
        conversation_id: str,
        message: str,
        base_url: str,
        api_key: str,
        provider: str = "openai",
        api_mode: str = "chat_completions",
        model: str = "qwen3.5-plus",
        max_iterations: int = 10,
        max_tokens: int | None = None,
        system_prompt: str | None = None,
        enabled_toolsets: list[str] | None = None,
        disabled_toolsets: list[str] | None = None,
        mcp_servers: list[dict] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """异步流式聊天。

        每次 ``chat`` 都会基于 ``conversation_id`` 复用或新建 hermes
        session_id，从而保持 hermes 侧上下文连续。
        """
        hermes_session_id = session_store.get_or_create(conversation_id)

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue()

        def stream_callback(text: str | None) -> None:
            """AIAgent.chat() 的同步流式回调（方法参数，非构造参数）。"""
            if not text:
                return
            event = StreamEvent(type="delta", content=text)
            asyncio.run_coroutine_threadsafe(queue.put(event), loop)

        def tool_start_callback(name: str, args: dict) -> None:
            event = StreamEvent(type="tool_start", tool=name, args=args)
            asyncio.run_coroutine_threadsafe(queue.put(event), loop)

        def tool_complete_callback(name: str, result: Any) -> None:
            event = StreamEvent(type="tool_complete", tool=name, result=result)
            asyncio.run_coroutine_threadsafe(queue.put(event), loop)

        # 构造 AIAgent 参数（stream_callback 不在这里，它是 chat() 的参数）
        agent_kwargs: dict[str, Any] = {
            "base_url": base_url,
            "api_key": api_key,
            "provider": provider,
            "api_mode": api_mode,
            "model": model,
            "max_iterations": max_iterations,
            "skip_memory": True,  # 由 API 侧管理上下文
            "quiet_mode": True,
            "verbose_logging": False,
            "save_trajectories": False,
            "session_id": hermes_session_id,
            "chat_id": conversation_id,
            "tool_start_callback": tool_start_callback,
            "tool_complete_callback": tool_complete_callback,
        }
        if max_tokens is not None:
            agent_kwargs["max_tokens"] = max_tokens
        if system_prompt:
            agent_kwargs["ephemeral_system_prompt"] = system_prompt
        if enabled_toolsets:
            agent_kwargs["enabled_toolsets"] = enabled_toolsets
        if disabled_toolsets:
            agent_kwargs["disabled_toolsets"] = disabled_toolsets
        if mcp_servers:
            agent_kwargs["mcp_servers"] = mcp_servers

        def run_agent_sync() -> None:
            """在线程池中同步执行 AIAgent.chat。"""
            try:
                agent = AIAgent(**agent_kwargs)
                # stream_callback 是 chat() 的方法参数，不是构造参数
                result = agent.chat(message, stream_callback=stream_callback)
                asyncio.run_coroutine_threadsafe(
                    queue.put(StreamEvent(type="done", content=result or "")), loop
                )
            except Exception as e:  # noqa: BLE001
                logger.exception("agent_chat_failed")
                asyncio.run_coroutine_threadsafe(
                    queue.put(StreamEvent(type="error", error=str(e))), loop
                )
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)

        # 在线程池中运行同步 agent，不 await 以便立即开始消费队列
        loop.run_in_executor(None, run_agent_sync)

        # 异步消费队列
        while True:
            event = await queue.get()
            if event is None:
                break
            yield event


agent_runner = AgentRunner()
