"""Compatibility shim: see ``core.backup_integrity``."""
from __future__ import annotations

from core.backup_integrity import (  # noqa: F401
    VerifiedBackupEvidence,
    verify_backup_evidence,
)

__all__ = [
    "VerifiedBackupEvidence",
    "verify_backup_evidence",
]
