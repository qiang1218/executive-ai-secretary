"""AIAgent 封装层：同步 -> 异步桥接 + 流式回调 + MCP 注入。

AIAgent 的 ``chat()`` 是同步阻塞方法，``stream_callback`` 是 ``chat()`` 的方法参数
（不是构造参数）。``tool_start_callback`` / ``tool_complete_callback`` 才是构造参数。
本模块通过 ``asyncio.Queue`` + ``run_in_executor`` 把它桥接到异步流式接口。

MCP 工具通过 ``tools.mcp_tool.register_mcp_servers`` 全局注册到 AIAgent 的
工具注册表。``ENTERPRISE_ID`` 写进子进程 env，由 ``worker.mcp_server`` 读取后做
SQL 过滤，实现多企业隔离。企业切换时先 ``shutdown_mcp_servers`` 再重新注册。
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator

from run_agent import AIAgent
from tools.mcp_tool import register_mcp_servers, shutdown_mcp_servers

from configs.settings import get_settings
from worker.session_store import session_store

logger = logging.getLogger(__name__)

# 固定 MCP server 名：单实例 worker 同一时刻只承载一个企业的 MCP 连接，
# 企业切换时先 shutdown 再 register，保证隔离。
_MCP_SERVER_NAME = "executive-data"

# 当前已注册的企业 ID，避免同企业重复 register（register 是幂等的，
# 但同企业重复调用仍会触发不必要的连接检查）。
_registered_enterprise_id: str | None = None
_register_lock = asyncio.Lock()


async def _ensure_mcp_registered(enterprise_id: str) -> None:
    """确保 MCP server 已为指定企业注册。

    - 同企业：跳过（register_mcp_servers 内部对已存在 server 名幂等）
    - 企业切换：先 shutdown 再 register，断开旧企业的 stdio 子进程
    """
    global _registered_enterprise_id
    async with _register_lock:
        if _registered_enterprise_id == enterprise_id:
            return
        if _registered_enterprise_id is not None:
            logger.info(
                "MCP enterprise switch: %s -> %s, shutting down old connection",
                _registered_enterprise_id, enterprise_id,
            )
            # shutdown_mcp_servers 是同步阻塞调用，放到线程池避免阻塞事件循环
            await asyncio.to_thread(shutdown_mcp_servers)

        servers = {
            _MCP_SERVER_NAME: {
                "command": sys.executable,
                "args": ["-m", "worker.mcp_server"],
                "env": {
                    "DATABASE_URL": get_settings().database_url,
                    "ENTERPRISE_ID": enterprise_id,
                    # 子进程是新 spawn 的 python，不执行 main.py，需要显式
                    # 注入 PYTHONPATH 让它能 import worker.mcp_server
                    "PYTHONPATH": str(__import__("pathlib").Path(__file__).resolve().parents[1]),
                    # 强制子进程用 UTF-8 标准流，避免 Windows 中文系统下
                    # 父进程 subprocess 读取时 gbk 解码失败
                    "PYTHONUTF8": "1",
                    "PYTHONIOENCODING": "utf-8",
                },
                "timeout": 30,
                "connect_timeout": 10,
            }
        }
        # register_mcp_servers 内部用专用 event loop，可安全从 async 上下文调用
        await asyncio.to_thread(register_mcp_servers, servers)
        _registered_enterprise_id = enterprise_id
        logger.info("MCP server registered for enterprise=%s", enterprise_id)


def _build_mcp_servers(_enterprise_id: str) -> list[dict]:
    """已废弃：保留仅为向后兼容，新代码用 ``_ensure_mcp_registered``。

    早期版本通过 AIAgent(mcp_servers=...) 注入，但 AIAgent 构造函数不支持
    该参数；现在改用 ``register_mcp_servers`` 全局注册。
    """
    return []


@dataclass
class StreamEvent:
    """流式事件。

    基础事件（向后兼容）：
    - ``delta``: 增量文本片段
    - ``tool_start``: 工具调用开始
    - ``tool_complete``: 工具调用完成
    - ``done``: 整个 chat 结束，``content`` 为最终完整文本
    - ``error``: 发生错误，``error`` 为错误信息

    阶段事件（供前端渲染进度时间线）：
    - ``turn_start``: 一轮对话开始，``data`` 含 model/session_id/message_preview
    - ``turn_end``: 一轮对话结束，``data`` 含 duration_seconds
    - ``step``: 新的 API 调用迭代开始，``data`` 含 api_call_count/prev_tools
    - ``thinking``: 模型思考/等待状态文本，``content`` 为状态文本
    - ``interim_assistant``: 中间助理评论（工具调用前的解说），``content`` 为文本
    - ``status``: 生命周期/警告消息，``data`` 含 kind/message
    """

    type: str
    content: str = ""
    tool: str | None = None
    args: dict | None = None
    result: Any | None = None
    error: str | None = None
    data: dict | None = None


class AgentRunner:
    """封装 AIAgent，提供异步流式接口。"""

    async def chat(
        self,
        *,
        conversation_id: str,
        message: str,
        base_url: str,
        api_key: str,
        enterprise_id: str,
        provider: str = "openai",
        api_mode: str = "chat_completions",
        model: str = "qwen3.5-plus",
        max_iterations: int = 10,
        max_tokens: int | None = None,
        system_prompt: str | None = None,
        enabled_toolsets: list[str] | None = None,
        disabled_toolsets: list[str] | None = None,
        mcp_servers: list[dict] | None = None,
        skills: list[str] | None = None,
        conversation_history: list[dict] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """异步流式聊天。

        每次 ``chat`` 都会基于 ``conversation_id`` 复用或新建 hermes
        session_id，从而保持 hermes 侧上下文连续。

        ``enterprise_id`` 用于注入 MCP server 子进程 env，做多企业数据隔离。
        MCP server 通过 ``register_mcp_servers`` 全局注册（见
        ``_ensure_mcp_registered``），不再通过 AIAgent 构造参数传入。

        ``conversation_history`` 为本会话历史消息（不含本轮 user message），
        按 role/content 顺序传入。hermes ``run_conversation`` 会把它作为
        ``messages`` 起点，再 append 本轮 user message，从而让 LLM 看到完整
        上下文。``skip_memory=True`` 仅关闭 MemoryManager 长期记忆插件，
        不会自动加载磁盘历史 —— 必须显式传 ``conversation_history``。
        """
        # 按企业注册 MCP server（企业切换时自动 shutdown 旧连接）
        if enterprise_id:
            await _ensure_mcp_registered(enterprise_id)

        # HERMES_HOME 优先从 .env 环境变量读取（进程启动时已加载）；
        # 若未配置则回退到 settings.skills_active_dir 并动态设置。
        # hermes-agent 从 <HERMES_HOME>/skills/<slug>/ 加载 skill 文件。
        if not os.environ.get("HERMES_HOME"):
            hermes_home = get_settings().skills_active_dir
            if hermes_home:
                os.environ["HERMES_HOME"] = str(hermes_home)

        # skills 参数仅用于日志记录；实际加载由 hermes-agent 扫描
        # <HERMES_HOME>/skills/ 目录完成（API 侧只释放已启用的 skill）
        if skills:
            logger.info("chat_with_skills conversation=%s skills=%s", conversation_id, skills)

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

        def step_callback(api_call_count: int, prev_tools: list) -> None:
            """每个 API 调用迭代开始时触发（工具批次完成后、下一次调 LLM 前）。"""
            event = StreamEvent(
                type="step",
                data={
                    "api_call_count": api_call_count,
                    "prev_tools": prev_tools or [],
                },
            )
            asyncio.run_coroutine_threadsafe(queue.put(event), loop)

        def thinking_callback(text: str) -> None:
            """模型思考/等待状态文本（如 "Waiting for response..."）。"""
            if not text:
                return
            event = StreamEvent(type="thinking", content=text)
            asyncio.run_coroutine_threadsafe(queue.put(event), loop)

        def interim_assistant_callback(text: str) -> None:
            """中间助理评论（工具调用前的解说文本）。"""
            if not text:
                return
            event = StreamEvent(type="interim_assistant", content=text)
            asyncio.run_coroutine_threadsafe(queue.put(event), loop)

        def status_callback(kind: str, message: str) -> None:
            """生命周期/警告消息（如压缩通知、限流警告）。"""
            if not message:
                return
            event = StreamEvent(
                type="status",
                content=message,
                data={"kind": kind},
            )
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
            "step_callback": step_callback,
            "thinking_callback": thinking_callback,
            "interim_assistant_callback": interim_assistant_callback,
            "status_callback": status_callback,
        }
        if max_tokens is not None:
            agent_kwargs["max_tokens"] = max_tokens
        if system_prompt:
            agent_kwargs["ephemeral_system_prompt"] = system_prompt
        if enabled_toolsets:
            agent_kwargs["enabled_toolsets"] = enabled_toolsets
        if disabled_toolsets:
            agent_kwargs["disabled_toolsets"] = disabled_toolsets

        # 截取用户消息前 80 字符作为预览（去掉换行），供前端展示
        _msg_preview = (message[:80] + "...") if len(message) > 80 else message
        _msg_preview = _msg_preview.replace("\n", " ")

        # 发射 turn_start 事件（在启动 agent 线程之前，让前端尽早看到"开始处理"）
        yield StreamEvent(
            type="turn_start",
            data={
                "model": model,
                "session_id": hermes_session_id,
                "message_preview": _msg_preview,
            },
        )

        _turn_started = time.monotonic()

        def run_agent_sync() -> None:
            """在线程池中同步执行 AIAgent.run_conversation。

            使用 ``run_conversation`` 而非 ``chat`` 的原因：``chat`` 不接受
            ``conversation_history`` 参数，无法把 API 侧传入的历史消息透传
            给 hermes，会导致同一会话内后续提问丢失上下文。
            """
            try:
                agent = AIAgent(**agent_kwargs)
                # stream_callback 是 run_conversation() 的方法参数，不是构造参数
                result = agent.run_conversation(
                    message,
                    conversation_history=conversation_history,
                    stream_callback=stream_callback,
                )
                final_response = ""
                if isinstance(result, dict):
                    final_response = result.get("final_response") or ""
                elif isinstance(result, str):
                    final_response = result
                asyncio.run_coroutine_threadsafe(
                    queue.put(StreamEvent(type="done", content=final_response)), loop
                )
            except Exception as e:  # noqa: BLE001
                logger.exception("agent_chat_failed")
                asyncio.run_coroutine_threadsafe(
                    queue.put(StreamEvent(type="error", error=str(e))), loop
                )
            finally:
                _duration = round(time.monotonic() - _turn_started, 2)
                asyncio.run_coroutine_threadsafe(
                    queue.put(
                        StreamEvent(type="turn_end", data={"duration_seconds": _duration})
                    ),
                    loop,
                )
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
