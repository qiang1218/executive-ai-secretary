"""每日邮件摘要服务。

由 ``JobRunner`` 的 ``daily_digest`` handler 调用：
1. 取用户 ``is_notified=False`` 的邮件（自上次摘要后新增）
2. 若无新邮件，跳过
3. 调 LLM 生成一段中文摘要（不超过 300 字），覆盖今日重要邮件要点
4. 创建 ``Notification(type='email_digest', importance='normal')``
5. 将纳入摘要的 EmailMessage ``is_notified`` 置为 True
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from configs.settings import Settings
from core.security import utc_now
from db.session import AsyncSessionLocal
from models import EmailMessage, Job, Notification, User, new_uuid

logger = logging.getLogger(__name__)


async def run_daily_digest(
    ctx: Any, job: Job, settings: Settings
) -> dict[str, Any]:
    """Job handler 入口：为指定用户生成每日邮件摘要通知。

    ``ctx`` 为 ``JobRunnerContext``（未使用但保持 handler 签名一致）。
    ``job.payload_json`` 必须包含 ``user_id``。
    """
    payload = job.payload_json or {}
    user_id_raw = payload.get("user_id")
    if not user_id_raw:
        return {"status": "skipped", "reason": "missing user_id"}
    user_id = uuid.UUID(user_id_raw)

    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if user is None:
            return {"status": "skipped", "reason": "user not found"}

        # 上次摘要通知时间，作为时间窗起点；无则取最近 24h
        last_digest = await session.scalar(
            select(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.type == "email_digest",
            )
            .order_by(Notification.created_at.desc())
            .limit(1)
        )
        since = (
            last_digest.created_at
            if last_digest is not None
            else utc_now() - timedelta(hours=24)
        )

        messages_result = await session.scalars(
            select(EmailMessage).where(
                EmailMessage.user_id == user_id,
                EmailMessage.is_notified.is_(False),
                EmailMessage.received_at >= since,
            ).order_by(EmailMessage.received_at.asc())
        )
        messages = list(messages_result.all())
        if not messages:
            return {"status": "ok", "user_id": str(user_id), "summarized": 0}

        digest_input = _build_digest_input(messages)
        enterprise_id = user.enterprise_id
        message_ids = [m.id for m in messages]

    # 调 LLM 生成摘要文本
    try:
        digest_text = await _generate_digest_text(
            settings, enterprise_id, digest_input
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("daily_digest_llm_failed user=%s err=%s", user_id, exc)
        digest_text = _fallback_digest_text(messages)

    # 落库 Notification + 标记 is_notified
    async with AsyncSessionLocal() as session:
        notification = Notification(
            id=new_uuid(),
            user_id=user_id,
            enterprise_id=enterprise_id,
            type="email_digest",
            title="每日邮件摘要",
            body=digest_text,
            payload_json={
                "message_count": len(messages),
                "message_ids": [str(mid) for mid in message_ids],
                "since": since.isoformat() if since else None,
            },
            importance="normal",
        )
        session.add(notification)
        for msg_id in message_ids:
            db_msg = await session.get(EmailMessage, msg_id)
            if db_msg is not None:
                db_msg.is_notified = True
        await session.commit()

    return {
        "status": "ok",
        "user_id": str(user_id),
        "summarized": len(messages),
    }


def _build_digest_input(messages: list[EmailMessage]) -> str:
    """拼装 LLM 输入：每封邮件一行。"""
    lines = []
    for i, msg in enumerate(messages, 1):
        importance_tag = f"[{msg.importance}]" if msg.importance != "normal" else ""
        lines.append(
            f"{i}. {importance_tag} {msg.subject[:120]}\n"
            f"   From: {msg.sender}\n"
            f"   摘要: {msg.summary or msg.body_excerpt[:120]}"
        )
    return "\n".join(lines)


def _fallback_digest_text(messages: list[EmailMessage]) -> str:
    """LLM 不可用时的降级摘要。"""
    if not messages:
        return "今日无新邮件。"
    high = [m for m in messages if m.importance == "high"]
    parts = [f"今日新增 {len(messages)} 封邮件。"]
    if high:
        parts.append(f"其中 {len(high)} 封标记为重要：")
        for m in high[:5]:
            parts.append(f"  - {m.subject[:80]}（来自 {m.sender}）")
    else:
        parts.append("主题预览：")
        for m in messages[:5]:
            parts.append(f"  - {m.subject[:80]}")
    return "\n".join(parts)


async def _generate_digest_text(
    settings: Settings,
    enterprise_id: uuid.UUID,
    digest_input: str,
) -> str:
    """调 LLM 生成摘要文本；失败时返回空串（由调用方降级）。"""
    from repositories.model_provider_config import find_active as find_active_provider
    from services.anspire import decrypt_anspire_api_key
    from services.hermes_client import HermesClient

    async with AsyncSessionLocal() as async_session:
        provider = await find_active_provider(async_session, enterprise_id)
        if provider is None or not provider.api_key_ciphertext:
            return ""
        api_key = decrypt_anspire_api_key(provider, settings)
        base_url = provider.endpoint_url
        model_id = provider.model_id

    client = HermesClient(settings)
    profile_payload = {
        "instruction": (
            "你是邮件助手。基于下面今日邮件列表，生成一段不超过 300 字的中文摘要，"
            "突出重要事项与待办。不要使用 Markdown，直接输出纯文本。"
        ),
        "input": digest_input,
    }
    result = await client.run_profile(
        profile="daily_digest",
        payload=profile_payload,
        base_url=base_url,
        api_key=api_key,
        model_id=model_id,
    )
    return (result.get("text") or "").strip()[:2000]
