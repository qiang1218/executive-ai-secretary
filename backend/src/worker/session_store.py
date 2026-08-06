"""会话映射存储：API conversation_id -> hermes session_id。

AIAgent 通过 ``session_id`` 标识 hermes 侧的会话上下文；上层 API 用
``conversation_id`` 标识业务会话。本模块在两者之间做翻译，且线程安全，
可被同步线程池与异步事件循环同时访问。
"""
from __future__ import annotations

import threading
import uuid


class SessionStore:
    """线程安全的会话映射存储。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._map: dict[str, str] = {}  # api_conversation_id -> hermes_session_id

    def get_or_create(self, conversation_id: str) -> str:
        """返回 ``conversation_id`` 对应的 hermes session_id，不存在则新建。"""
        with self._lock:
            if conversation_id not in self._map:
                self._map[conversation_id] = str(uuid.uuid4())
            return self._map[conversation_id]

    def get(self, conversation_id: str) -> str | None:
        """查询已存在的映射，不存在返回 None。"""
        with self._lock:
            return self._map.get(conversation_id)

    def remove(self, conversation_id: str) -> None:
        """删除指定会话映射（幂等）。"""
        with self._lock:
            self._map.pop(conversation_id, None)


session_store = SessionStore()
