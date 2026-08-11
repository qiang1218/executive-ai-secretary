"""邮件账户、邮件消息与站内通知模型.

设计要点：
- ``EmailAccount`` per-user 邮件账户，凭据通过 AES-GCM 内联加密存储
  （与 ``ModelProviderConfig.api_key_ciphertext`` 同一体系），
  由 services/email_credential.py 处理加解密。
- ``EmailMessage`` 拉取到的邮件原始信息 + LLM 生成的摘要/重要性/标签。
- ``Notification`` 通用站内通知（不只邮件），可关联邮件/每日简报/系统事件。
"""

from __future__ import annotations

from .base import *  # noqa: F401,F403  Base / JSONType / new_uuid / mixins / sqlalchemy symbols


class EmailAccount(UUIDMixin, TimestampMixin, Base):
    """用户邮箱账户配置（IMAP/POP3）。"""

    __tablename__ = "email_accounts"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "address", name="uq_email_account_user_address"
        ),
        Index("ix_email_account_user_enabled", "user_id", "is_enabled"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    address: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    protocol: Mapped[str] = mapped_column(
        String(16), default="imap", nullable=False
    )  # imap / pop3
    server_host: Mapped[str] = mapped_column(String(200), nullable=False)
    server_port: Mapped[int] = mapped_column(Integer, default=993, nullable=False)
    use_tls: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 密码以 AES-GCM 加密内联存储（与 ModelProviderConfig.api_key_ciphertext 同一体系），
    # 由 services/email_credential.py 的 encrypt/decrypt 函数处理。
    password_ciphertext: Mapped[str | None] = mapped_column(Text)
    password_nonce: Mapped[str | None] = mapped_column(String(64))
    password_hint: Mapped[str | None] = mapped_column(String(16))
    encryption_key_version: Mapped[str] = mapped_column(
        String(64), default="v1", nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 同步游标
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_uid: Mapped[int | None] = mapped_column(BigInteger)
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    last_error_message: Mapped[str | None] = mapped_column(Text)


class EmailMessage(UUIDMixin, TimestampMixin, Base):
    """拉取到的邮件（已落库的快照）。"""

    __tablename__ = "email_messages"
    __table_args__ = (
        UniqueConstraint(
            "email_account_id", "message_uid", name="uq_email_message_account_uid"
        ),
        Index("ix_email_message_user_date", "user_id", "received_at"),
        Index("ix_email_message_unread", "user_id", "is_read"),
    )

    email_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("email_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_uid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id_header: Mapped[str | None] = mapped_column(String(500))
    subject: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    sender: Mapped[str] = mapped_column(String(320), default="", nullable=False)
    recipients_json: Mapped[list[str]] = mapped_column(
        JSONType, default=list, nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_excerpt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    importance: Mapped[str] = mapped_column(
        String(16), default="normal", nullable=False
    )  # low / normal / high
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    labels_json: Mapped[list[str]] = mapped_column(
        JSONType, default=list, nullable=False
    )


class Notification(UUIDMixin, TimestampMixin, Base):
    """站内通知（通用载体，可承载邮件摘要/每日简报/系统事件等）。"""

    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "ix_notification_user_unread",
            "user_id",
            "is_read",
            "created_at",
        ),
        Index("ix_notification_user_type", "user_id", "type"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    # email_digest / email_urgent / daily_brief / system
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSONType, default=dict, nullable=False
    )
    importance: Mapped[str] = mapped_column(
        String(16), default="normal", nullable=False
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
