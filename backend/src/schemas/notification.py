"""站内通知 Pydantic 模型。"""

from __future__ import annotations

import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import ORMModel


NotificationType = Literal["email_digest", "email_urgent", "daily_brief", "system"]
NotificationImportance = Literal["low", "normal", "high"]


class NotificationOut(ORMModel):
    """站内通知输出。"""

    id: str
    user_id: str
    type: NotificationType
    title: str
    body: str
    payload_json: dict[str, Any] = Field(default_factory=dict)
    importance: NotificationImportance
    is_read: bool
    read_at: datetime.datetime | None = None
    created_at: datetime.datetime


class UnreadCountOut(BaseModel):
    """未读通知数。"""

    unread: int


class MarkReadRequest(BaseModel):
    """批量标记已读。``ids`` 与 ``all`` 互斥；二者皆空时返回 0。"""

    model_config = ConfigDict(extra="forbid")

    ids: list[str] | None = Field(default=None, description="指定 id 列表")
    all: bool = Field(default=False, description="标记当前用户全部未读为已读")


class MarkReadResult(BaseModel):
    """标记已读结果。"""

    updated: int


class DigestGenerateOut(BaseModel):
    """手动触发每日摘要入队结果。"""

    job_id: str
    status: str
