"""邮件账户密码加解密。

复用 ``Settings.integration_encryption_keys()`` 与 AES-256-GCM，
AAD 形如 ``executive-ai\\x00<enterprise_id>\\x00email-account\\x00<key_version>``，
与 ``services/anspire.py`` 的 anspire api_key 加解密同构。
"""

from __future__ import annotations

import base64
import os
import uuid
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from configs.settings import Settings
from exceptions.errors import AppError


_PROVIDER_TAG = "email-account"


class EmailCredentialError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class EncryptedEmailPassword:
    ciphertext: str
    nonce: str
    hint: str
    key_version: str


def _aad(enterprise_id: uuid.UUID, key_version: str) -> bytes:
    return f"executive-ai\x00{enterprise_id}\x00{_PROVIDER_TAG}\x00{key_version}".encode()


def _normalize_password(password: str) -> str:
    normalized = password.strip()
    if not normalized:
        raise EmailCredentialError("email_password_empty", "邮箱密码不能为空")
    if len(normalized) > 512:
        raise EmailCredentialError("email_password_too_long", "邮箱密码过长")
    return normalized


def encrypt_email_password(
    password: str,
    *,
    enterprise_id: uuid.UUID,
    settings: Settings,
) -> EncryptedEmailPassword:
    """加密邮箱密码，返回可入库的字段元组。"""
    normalized = _normalize_password(password)
    version = settings.integration_encryption_key_version
    key = settings.integration_encryption_keys().get(version)
    if key is None:
        raise EmailCredentialError(
            "email_encryption_key_unavailable",
            "邮箱凭证加密所需的密钥未配置",
        )
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, normalized.encode("utf-8"), _aad(enterprise_id, version))
    return EncryptedEmailPassword(
        ciphertext=base64.urlsafe_b64encode(ciphertext).decode("ascii"),
        nonce=base64.urlsafe_b64encode(nonce).decode("ascii"),
        hint=normalized[-4:],
        key_version=version,
    )


def decrypt_email_password(
    *,
    ciphertext: str | None,
    nonce: str | None,
    enterprise_id: uuid.UUID,
    key_version: str,
    settings: Settings,
) -> str:
    """解密邮箱密码；失败时抛 :class:`EmailCredentialError`。"""
    if not ciphertext or not nonce:
        raise EmailCredentialError(
            "email_credential_not_configured",
            "该邮件账户尚未配置密码",
        )
    key = settings.integration_encryption_keys().get(key_version)
    if key is None:
        raise EmailCredentialError(
            "email_encryption_key_unavailable",
            "邮箱凭证所需的历史加密密钥未加载",
        )
    try:
        plaintext = AESGCM(key).decrypt(
            base64.urlsafe_b64decode(nonce.encode("ascii")),
            base64.urlsafe_b64decode(ciphertext.encode("ascii")),
            _aad(enterprise_id, key_version),
        )
    except (InvalidTag, ValueError, UnicodeError) as exc:
        raise EmailCredentialError(
            "email_credential_integrity_error",
            "邮箱凭证完整性校验失败",
        ) from exc
    try:
        return plaintext.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EmailCredentialError(
            "email_credential_integrity_error",
            "邮箱凭证无法解密",
        ) from exc
