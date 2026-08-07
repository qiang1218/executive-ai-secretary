"""启动期 audit chain 完整性初始化 (桥接 api.main)。"""
from __future__ import annotations

from sqlalchemy import Engine

from repositories.audit_integrity import initialize_audit_chains

__all__ = ["initialize_runtime_integrity"]


def initialize_runtime_integrity(engine: Engine) -> None:
    with engine.begin() as connection:
        initialize_audit_chains(connection)
