"""邮件账户与邮件消息 Pydantic 模型。"""

from __future__ import annotations

import datetime
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


_PROTOCOLS = frozenset({"imap", "pop3"})


class EmailAccountCreate(BaseModel):
    """新建邮件账户请求体。``password`` 通过 AES-GCM 内联加密后存储
    （与 ``ModelProviderConfig.api_key_ciphertext`` 同一体系）。"""

    model_config = ConfigDict(extra="forbid")

    address: str = Field(min_length=3, max_length=320, description="邮箱地址")
    display_name: str = Field(default="", max_length=200)
    protocol: str = Field(default="imap")
    server_host: str = Field(min_length=1, max_length=200)
    server_port: int = Field(default=993, ge=1, le=65535)
    use_tls: bool = Field(default=True)
    password: SecretStr = Field(..., description="邮箱密码（明文传入，服务端加密存储）")
    is_enabled: bool = Field(default=True)

    @field_validator("protocol")
    @classmethod
    def _check_protocol(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if v not in _PROTOCOLS:
            raise ValueError(f"protocol 仅支持 {sorted(_PROTOCOLS)}")
        return v


class EmailAccountUpdate(BaseModel):
    """编辑邮件账户请求体。``password`` 为空表示不修改。"""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=200)
    protocol: str | None = None
    server_host: str | None = Field(default=None, max_length=200)
    server_port: int | None = Field(default=None, ge=1, le=65535)
    use_tls: bool | None = None
    password: SecretStr | None = Field(
        default=None, description="为空表示不修改密码"
    )
    is_enabled: bool | None = None

    @field_validator("protocol")
    @classmethod
    def _check_protocol(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lower()
        if v not in _PROTOCOLS:
            raise ValueError(f"protocol 仅支持 {sorted(_PROTOCOLS)}")
        return v


class EmailAccountOut(BaseModel):
    """邮件账户输出（不含密码）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    address: str
    display_name: str
    protocol: str
    server_host: str
    server_port: int
    use_tls: bool
    is_enabled: bool
    last_synced_at: datetime.datetime | None = None
    last_uid: int | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class EmailAccountTestOut(BaseModel):
    """测试连接结果。"""

    ok: bool
    error_code: str | None = None
    error_message: str | None = None


class EmailMessageOut(BaseModel):
    """邮件消息输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email_account_id: str
    subject: str
    sender: str
    recipients_json: list[str] = Field(default_factory=list)
    received_at: datetime.datetime
    summary: str
    body_excerpt: str
    importance: str
    is_read: bool
    is_notified: bool
    labels_json: list[str] = Field(default_factory=list)
    created_at: datetime.datetime


class EmailSyncEnqueueOut(BaseModel):
    """手动触发邮件同步入队结果。"""

    job_id: str
    status: str
