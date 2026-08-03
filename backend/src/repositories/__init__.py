"""仓储层：纯数据访问对象（Repository）。

实现策略：
    1. ``audit``、``audit_integrity`` 等模块本质上只对数据库做增删改查，
       故整体平移到 ``repositories`` 下；
    2. 通过 ``__getattr__``（PEP 562）兜底，使 ``from repositories import Y``
       能找到 ``repositories.audit_integrity.Y`` 等具体符号；
    3. 保留若干领域级别名 ``AuditRepository``、``SeedRepository`` 等，
       便于后续把领域拆成独立类时不用动调用方。
"""

from __future__ import annotations

from typing import Any

from . import (
    audit as _audit,
    audit_integrity as _audit_integrity,
    migration_compatibility as _migration_compatibility,
    operating_data_reset as _operating_data_reset,
    personal_data_migration as _personal_data_migration,
    rotate_file_keys as _rotate_file_keys,
    rotate_integration_keys as _rotate_integration_keys,
    seed as _seed,
)

# 子模块名称 → 模块对象映射（用于 __getattr__ 兜底）
_SUBMODULES: dict[str, Any] = {
    "audit": _audit,
    "audit_integrity": _audit_integrity,
    "seed": _seed,
    "migration_compatibility": _migration_compatibility,
    "operating_data_reset": _operating_data_reset,
    "personal_data_migration": _personal_data_migration,
    "rotate_file_keys": _rotate_file_keys,
    "rotate_integration_keys": _rotate_integration_keys,
}

# 显式别名（领域级 Service / Repository 命名）
AuditRepository = _audit
AuditIntegrityRepository = _audit_integrity
SeedRepository = _seed
MigrationCompatibilityRepository = _migration_compatibility
OperatingDataResetRepository = _operating_data_reset
PersonalDataMigrationRepository = _personal_data_migration
FileKeyRotationRepository = _rotate_file_keys
IntegrationKeyRotationRepository = _rotate_integration_keys


def __getattr__(name: str) -> Any:
    """PEP 562：未在 ``__init__`` 中显式导出的符号，从子模块中查找。"""
    if name in _SUBMODULES:
        return _SUBMODULES[name]
    for module in _SUBMODULES.values():
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(f"module 'repositories' has no attribute {name!r}")


__all__ = [
    "AuditRepository",
    "AuditIntegrityRepository",
    "SeedRepository",
    "MigrationCompatibilityRepository",
    "OperatingDataResetRepository",
    "PersonalDataMigrationRepository",
    "FileKeyRotationRepository",
    "IntegrationKeyRotationRepository",
] + list(_SUBMODULES.keys())
