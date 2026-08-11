"""email_and_notifications

Revision ID: e2b3c4d5f6a7
Revises: 27e9d8d36948
Create Date: 2026-08-10

新增邮件拉取 + 站内通知三张表：
- ``email_accounts``   per-user 邮箱账户配置（凭据通过 AES-GCM 内联加密存储，
  对齐 ModelProviderConfig.api_key_ciphertext 体系）
- ``email_messages``   拉取的邮件快照（含 LLM 摘要 / 重要性 / 标签）
- ``notifications``    通用站内通知（email_digest / email_urgent / daily_brief / system）

并扩展 ``scheduled_tasks.task_type`` 的取值范围（不改列定义，仅业务层识别），
新增 ``email.sync`` 与 ``daily_digest`` 两类任务，由 JobRunner 注册的 handler 处理。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e2b3c4d5f6a7"
down_revision: Union[str, None] = "27e9d8d36948"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enterprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("address", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False, server_default=sa.text("''")),
        sa.Column("protocol", sa.String(16), nullable=False, server_default=sa.text("'imap'")),
        sa.Column("server_host", sa.String(200), nullable=False),
        sa.Column("server_port", sa.Integer, nullable=False, server_default=sa.text("993")),
        sa.Column("use_tls", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("password_ciphertext", sa.Text, nullable=True),
        sa.Column("password_nonce", sa.String(64), nullable=True),
        sa.Column("password_hint", sa.String(16), nullable=True),
        sa.Column("encryption_key_version", sa.String(64), nullable=False, server_default=sa.text("'v1'")),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_uid", sa.BigInteger, nullable=True),
        sa.Column("last_error_code", sa.String(100), nullable=True),
        sa.Column("last_error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["enterprise_id"], ["enterprises.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "address", name="uq_email_account_user_address"),
    )
    op.create_index(
        "ix_email_account_user_enabled", "email_accounts", ["user_id", "is_enabled"]
    )
    op.create_index("ix_email_account_user_id", "email_accounts", ["user_id"])

    op.create_table(
        "email_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enterprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_uid", sa.BigInteger, nullable=False),
        sa.Column("message_id_header", sa.String(500), nullable=True),
        sa.Column("subject", sa.String(1000), nullable=False, server_default=sa.text("''")),
        sa.Column("sender", sa.String(320), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "recipients_json",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("body_excerpt", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("importance", sa.String(16), nullable=False, server_default=sa.text("'normal'")),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_notified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column(
            "labels_json",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["email_account_id"], ["email_accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["enterprise_id"], ["enterprises.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "email_account_id", "message_uid", name="uq_email_message_account_uid"
        ),
    )
    op.create_index(
        "ix_email_message_user_date", "email_messages", ["user_id", "received_at"]
    )
    op.create_index(
        "ix_email_message_unread", "email_messages", ["user_id", "is_read"]
    )
    op.create_index("ix_email_message_email_account_id", "email_messages", ["email_account_id"])

    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enterprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column(
            "payload_json",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("importance", sa.String(16), nullable=False, server_default=sa.text("'normal'")),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["enterprise_id"], ["enterprises.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_notification_user_unread",
        "notifications",
        ["user_id", "is_read", "created_at"],
    )
    op.create_index(
        "ix_notification_user_type", "notifications", ["user_id", "type"]
    )
    op.create_index("ix_notification_user_id", "notifications", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_notification_user_id", table_name="notifications")
    op.drop_index("ix_notification_user_type", table_name="notifications")
    op.drop_index("ix_notification_user_unread", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_email_message_email_account_id", table_name="email_messages")
    op.drop_index("ix_email_message_unread", table_name="email_messages")
    op.drop_index("ix_email_message_user_date", table_name="email_messages")
    op.drop_table("email_messages")
    op.drop_index("ix_email_account_user_id", table_name="email_accounts")
    op.drop_index("ix_email_account_user_enabled", table_name="email_accounts")
    op.drop_table("email_accounts")
