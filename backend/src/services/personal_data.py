"""Compatibility shim: see ``core.personal_data``."""
from __future__ import annotations

from core.personal_data import (  # noqa: F401
    EncryptedPersonalValue,
    decrypt_personal_text,
    decrypt_profile_payload,
    encrypt_personal_text,
    encrypt_profile_payload,
    ensure_memory_encrypted,
    get_memory_content,
    set_memory_content,
)

__all__ = [
    "EncryptedPersonalValue",
    "decrypt_personal_text",
    "decrypt_profile_payload",
    "encrypt_personal_text",
    "encrypt_profile_payload",
    "ensure_memory_encrypted",
    "get_memory_content",
    "set_memory_content",
]
