"""邮件同步服务。

由 ``JobRunner`` 的 ``email.sync`` handler 调用，负责：
1. 解密邮箱密码，连接 IMAP 服务器
2. 用 UID SEARCH 拉取 ``last_uid`` 之后的新邮件（批量上限由 settings 控制）
3. 去重（account_id + UID），落库 EmailMessage
4. 调用 LLM 生成摘要 / 重要性 / 标签（可选，LLM 未配置时仅截取正文前 500 字）
5. 更新 EmailAccount.last_uid / last_synced_at
6. 若有 importance=high 的邮件 → 立即创建 Notification(type='email_urgent')
"""

from __future__ import annotations

import asyncio
import email
import email.utils
import imaplib
import logging
import re
import uuid
from datetime import UTC, datetime
from email.header import decode_header, make_header
from typing import Any

# 注册 IMAP ID 扩展命令（RFC 2971）
# 163/126 邮箱要求 login 后立即发 ID 命令提供客户端身份，
# 否则 SELECT 会返回 "Unsafe Login. Please contact kefu@188.com"
imaplib.Commands["ID"] = ("AUTH", "SELECTED", "NONAUTH")


def _send_imap_id(conn: imaplib.IMAP4) -> None:
    """向 IMAP 服务器发送 ID 命令提供客户端身份。

    163/126 邮箱在 login 后强制要求此命令，否则拒绝 SELECT。
    其它服务器（Gmail/QQ/Outlook 等）会忽略或返回自身 ID，无副作用。
    """
    id_args = '("name" "ExecSecretary" "version" "1.0" "vendor" "Anchnet" "support-email" "")'
    try:
        # _simple_command 内部已调用 _command_complete 完成完整的请求-响应周期，
        # 不要再调用 _command_complete（会导致 tag 不匹配，消费后续 SELECT 的响应）
        conn._simple_command("ID", id_args)
    except Exception:  # noqa: BLE001
        # ID 失败不影响非 163 服务器，忽略即可
        pass

from sqlalchemy import select

from configs.settings import Settings
from core.security import utc_now
from db.session import AsyncSessionLocal
from models import EmailAccount, EmailMessage, Job, Notification, new_uuid
from repositories import email as email_repo
from services.email_credential import EmailCredentialError, decrypt_email_password

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# IMAP 连接测试
# --------------------------------------------------------------------------

async def test_imap_connection(
    *,
    host: str,
    port: int,
    use_tls: bool,
    address: str,
    password: str,
) -> tuple[bool, str | None, str | None]:
    """测试 IMAP 连接；返回 ``(ok, error_code, error_message)``。"""
    try:
        result = await asyncio.get_running_loop().run_in_executor(
            None, _imap_login_blocking, host, port, use_tls, address, password
        )
        return result
    except Exception as exc:  # noqa: BLE001
        return False, "imap_unexpected_error", f"{type(exc).__name__}: {exc}"


def _imap_login_blocking(
    host: str, port: int, use_tls: bool, address: str, password: str
) -> tuple[bool, str | None, str | None]:
    """阻塞型 IMAP 登录测试，供 ``run_in_executor`` 调用。"""
    conn: imaplib.IMAP4 | None = None
    try:
        if use_tls:
            conn = imaplib.IMAP4_SSL(host, port)
        else:
            conn = imaplib.IMAP4(host, port)
        conn.login(address, password)
        _send_imap_id(conn)
        return True, None, None
    except imaplib.IMAP4.error as exc:
        return False, "imap_auth_failed", str(exc)
    except OSError as exc:
        return False, "imap_connection_failed", str(exc)
    finally:
        if conn is not None:
            try:
                conn.logout()
            except Exception:  # noqa: BLE001
                pass


# --------------------------------------------------------------------------
# 邮件解析
# --------------------------------------------------------------------------

def _decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:  # noqa: BLE001
        return value


def _extract_recipients(msg: email.message.Message) -> list[str]:
    recipients: list[str] = []
    for field in ("To", "Cc", "Bcc"):
        raw = msg.get(field)
        if not raw:
            continue
        for _, addr in email.utils.getaddresses([raw]):
            if addr:
                recipients.append(addr)
    return recipients


def _extract_body_excerpt(msg: email.message.Message, *, limit: int = 500) -> str:
    """提取纯文本正文前 ``limit`` 字。优先 text/plain，其次 text/html 简单去标签。"""
    text_part = None
    html_part = None
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain" and text_part is None:
                text_part = part
            elif ctype == "text/html" and html_part is None:
                html_part = part
    else:
        ctype = msg.get_content_type()
        if ctype == "text/plain":
            text_part = msg
        elif ctype == "text/html":
            html_part = msg
    payload: str
    if text_part is not None:
        try:
            payload = text_part.get_payload(decode=True).decode(
                text_part.get_content_charset() or "utf-8",
                errors="replace",
            )
        except Exception:  # noqa: BLE001
            payload = ""
    elif html_part is not None:
        try:
            payload = html_part.get_payload(decode=True).decode(
                html_part.get_content_charset() or "utf-8",
                errors="replace",
            )
        except Exception:  # noqa: BLE001
            payload = ""
        payload = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", payload, flags=re.S | re.I)
        payload = re.sub(r"<[^>]+>", "", payload)
        payload = re.sub(r"\s+", " ", payload).strip()
    else:
        payload = ""
    return payload[:limit]


# --------------------------------------------------------------------------
# 同步主入口（async job handler）
# --------------------------------------------------------------------------

async def run_email_sync(
    ctx: Any, job: Job, settings: Settings
) -> dict[str, Any]:
    """Job handler 入口：同步指定 EmailAccount 的新邮件。

    ``ctx`` 为 ``JobRunnerContext``（未使用但保持 handler 签名一致）。
    ``job.payload_json`` 必须包含 ``email_account_id``。
    """
    payload = job.payload_json or {}
    account_id_raw = payload.get("email_account_id")
    if not account_id_raw:
        return {"status": "skipped", "reason": "missing email_account_id"}
    account_id = uuid.UUID(account_id_raw)

    async with AsyncSessionLocal() as session:
        account = await session.scalar(
            select(EmailAccount).where(EmailAccount.id == account_id)
        )
        if account is None:
            return {"status": "skipped", "reason": "account not found"}
        if not account.is_enabled:
            return {"status": "skipped", "reason": "account disabled"}

        try:
            password = decrypt_email_password(
                ciphertext=account.password_ciphertext,
                nonce=account.password_nonce,
                enterprise_id=account.enterprise_id,
                key_version=account.encryption_key_version,
                settings=settings,
            )
        except EmailCredentialError as exc:
            await _record_error(session, account, exc.code, str(exc))
            return {"status": "error", "error_code": exc.code, "error_message": str(exc)}

        # IMAP 拉取（阻塞 → run_in_executor）
        try:
            new_messages = await asyncio.get_running_loop().run_in_executor(
                None,
                _fetch_new_messages,
                account.server_host,
                account.server_port,
                account.use_tls,
                account.address,
                password,
                account.last_uid or 0,
                settings.email_sync_batch_size,
            )
        except Exception as exc:  # noqa: BLE001
            await _record_error(session, account, "imap_sync_failed", str(exc))
            logger.exception("email_sync_failed account=%s", account.id)
            return {"status": "error", "error_code": "imap_sync_failed", "error_message": str(exc)}

        # 去重 + 落库
        existing_uids = await email_repo.find_existing_uids(
            session, account.id, [m["uid"] for m in new_messages]
        )
        inserted_ids: list[uuid.UUID] = []
        inserted_summaries: list[dict[str, Any]] = []
        for raw in new_messages:
            if raw["uid"] in existing_uids:
                continue
            msg_obj = EmailMessage(
                id=new_uuid(),
                email_account_id=account.id,
                user_id=account.user_id,
                enterprise_id=account.enterprise_id,
                message_uid=raw["uid"],
                message_id_header=raw["message_id"],
                subject=raw["subject"],
                sender=raw["sender"],
                recipients_json=raw["recipients"],
                received_at=raw["received_at"],
                summary="",
                body_excerpt=raw["body_excerpt"],
                importance="normal",
                is_read=False,
                is_notified=False,
                labels_json=[],
            )
            session.add(msg_obj)
            inserted_ids.append(msg_obj.id)
            inserted_summaries.append({
                "id": msg_obj.id,
                "subject": raw["subject"],
                "sender": raw["sender"],
                "body_excerpt": raw["body_excerpt"],
            })

        # 更新账户游标
        if new_messages:
            max_uid = max(m["uid"] for m in new_messages)
            if account.last_uid is None or max_uid > account.last_uid:
                account.last_uid = max_uid
        account.last_synced_at = utc_now()
        account.last_error_code = None
        account.last_error_message = None
        await session.commit()

        result = {
            "status": "ok",
            "account_id": str(account.id),
            "new_messages": len(inserted_ids),
            "skipped_duplicates": len(new_messages) - len(inserted_ids),
        }

    # LLM 摘要（异步，失败不影响同步成功）
    if inserted_ids:
        try:
            await _summarize_messages(
                settings, account, inserted_ids, inserted_summaries
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("email_summarize_failed account=%s err=%s", account.id, exc)
            await _fallback_summarize(inserted_ids)

    return result


async def _record_error(
    session, account: EmailAccount, code: str, message: str
) -> None:
    account.last_error_code = code[:100]
    account.last_error_message = message[:4000]
    await session.commit()


def _fetch_new_messages(
    host: str,
    port: int,
    use_tls: bool,
    address: str,
    password: str,
    last_uid: int,
    batch_size: int,
) -> list[dict[str, Any]]:
    """连接 IMAP 拉取 ``last_uid`` 之后的新邮件；返回字典列表。

    纯同步阻塞函数，由 ``run_in_executor`` 调用。
    """
    conn: imaplib.IMAP4 | None = None
    try:
        if use_tls:
            conn = imaplib.IMAP4_SSL(host, port)
        else:
            conn = imaplib.IMAP4(host, port)
        conn.login(address, password)
        _send_imap_id(conn)
        conn.select("INBOX")

        typ, data = conn.uid("search", None, f"UID {last_uid + 1}:*")
        if typ != "OK":
            return []
        uids: list[int] = []
        for chunk in data:
            for token in chunk.split():
                try:
                    uid = int(token)
                except ValueError:
                    continue
                if uid > last_uid:
                    uids.append(uid)
        uids.sort()
        uids = uids[:batch_size]
        if not uids:
            return []

        results: list[dict[str, Any]] = []
        for uid in uids:
            typ, msg_data = conn.uid("fetch", str(uid), "(UID BODY.PEEK[])")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            raw_bytes = msg_data[0][1] if isinstance(msg_data[0], tuple) else None
            if raw_bytes is None:
                continue
            try:
                msg = email.message_from_bytes(raw_bytes)
            except Exception:  # noqa: BLE001
                continue
            subject = _decode_mime_header(msg.get("Subject"))
            sender = _decode_mime_header(msg.get("From"))
            recipients = _extract_recipients(msg)
            date_tuple = email.utils.parsedate_tz(msg.get("Date"))
            if date_tuple:
                received_at = datetime.fromtimestamp(
                    email.utils.mktime_tz(date_tuple), tz=UTC
                )
            else:
                received_at = utc_now()
            message_id = msg.get("Message-ID")
            body_excerpt = _extract_body_excerpt(msg)
            results.append({
                "uid": uid,
                "message_id": message_id or "",
                "subject": subject[:1000],
                "sender": sender[:320],
                "recipients": recipients,
                "received_at": received_at,
                "body_excerpt": body_excerpt,
            })
        return results
    finally:
        if conn is not None:
            try:
                conn.logout()
            except Exception:  # noqa: BLE001
                pass


async def _fallback_summarize(message_ids: list[uuid.UUID]) -> None:
    """LLM 不可用时的降级摘要：截取 subject + body 前 80 字。"""
    async with AsyncSessionLocal() as session:
        for msg_id in message_ids:
            msg = await session.get(EmailMessage, msg_id)
            if msg is None:
                continue
            summary = (msg.subject or "")[:40]
            if msg.body_excerpt:
                summary = f"{summary} — {msg.body_excerpt[:80]}"
            msg.summary = summary
        await session.commit()


async def _summarize_messages(
    settings: Settings,
    account: EmailAccount,
    message_ids: list[uuid.UUID],
    summaries_meta: list[dict[str, Any]],
) -> None:
    """调 LLM 批量生成摘要、重要性、标签；高重要性邮件立即创建 Notification。"""
    from repositories.model_provider_config import find_active as find_active_provider
    from services.anspire import decrypt_anspire_api_key
    from services.hermes_client import HermesClient

    async with AsyncSessionLocal() as async_session:
        provider = await find_active_provider(async_session, account.enterprise_id)
        if provider is None or not provider.api_key_ciphertext:
            await _fallback_summarize(message_ids)
            return
        api_key = decrypt_anspire_api_key(provider, settings)
        base_url = provider.endpoint_url
        model_id = provider.model_id

    client = HermesClient(settings)
    lines = []
    for i, meta in enumerate(summaries_meta, 1):
        lines.append(
            f"[{i}] Subject: {meta['subject']}\n"
            f"From: {meta['sender']}\n"
            f"Excerpt: {meta['body_excerpt'][:300]}"
        )
    payload_text = "\n\n".join(lines)
    profile_payload = {
        "instruction": (
            "你是邮件助手。为下面每封邮件生成 1 句中文摘要、重要性（low/normal/high）"
            "和 0-3 个标签。严格输出 JSON 数组，元素形如 "
            '{"summary":"...","importance":"normal","labels":["..."]}'
        ),
        "input": payload_text,
    }
    result = await client.run_profile(
        profile="email_summarize",
        payload=profile_payload,
        base_url=base_url,
        api_key=api_key,
        model_id=model_id,
    )
    text = result.get("text", "").strip()
    import json as _json
    try:
        items = _json.loads(text)
        if not isinstance(items, list):
            raise ValueError("not a list")
    except (ValueError, _json.JSONDecodeError):
        await _fallback_summarize(message_ids)
        return

    async with AsyncSessionLocal() as session:
        for msg_id, item in zip(message_ids, items, strict=False):
            if not isinstance(item, dict):
                continue
            summary = str(item.get("summary", ""))[:500]
            importance = str(item.get("importance", "normal")).lower()
            if importance not in {"low", "normal", "high"}:
                importance = "normal"
            labels_raw = item.get("labels", [])
            labels = [str(x) for x in labels_raw if isinstance(x, (str, int))][:3]
            db_msg = await session.get(EmailMessage, msg_id)
            if db_msg is None:
                continue
            db_msg.summary = summary
            db_msg.importance = importance
            db_msg.labels_json = labels
            if importance == "high":
                session.add(
                    Notification(
                        id=new_uuid(),
                        user_id=account.user_id,
                        enterprise_id=account.enterprise_id,
                        type="email_urgent",
                        title=f"重要邮件：{db_msg.subject[:80]}",
                        body=summary,
                        payload_json={
                            "email_message_id": str(db_msg.id),
                            "sender": db_msg.sender,
                            "received_at": db_msg.received_at.isoformat()
                            if db_msg.received_at
                            else None,
                        },
                        importance="high",
                    )
                )
        await session.commit()
