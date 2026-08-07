"""Compatibility shim: see ``core.encrypted_storage``."""
from __future__ import annotations

from core.encrypted_storage import (  # noqa: F401
    CHUNK_SIZE,
    KEY_VERSION_PATTERN,
    LocalEncryptedStorage,
    MAGIC_V1,
    MAGIC_V2,
    NONCE_SIZE,
    PrivateFileStorage,
    ReencryptionResult,
    StoredObject,
    TAG_SIZE,
)

__all__ = [
    "CHUNK_SIZE",
    "KEY_VERSION_PATTERN",
    "LocalEncryptedStorage",
    "MAGIC_V1",
    "MAGIC_V2",
    "NONCE_SIZE",
    "PrivateFileStorage",
    "ReencryptionResult",
    "StoredObject",
    "TAG_SIZE",
]
