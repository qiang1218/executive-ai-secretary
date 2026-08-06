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
    conversation as _conversation,
    file_asset as _file_asset,
    job as _job,
    message as _message,
    migration_compatibility as _migration_compatibility,
    model_provider_config as _model_provider_config,
    operating_data_reset as _operating_data_reset,
    organization_unit as _organization_unit,
    personal_data_migration as _personal_data_migration,
    project as _project,
    report as _report,
    rotate_file_keys as _rotate_file_keys,
    rotate_integration_keys as _rotate_integration_keys,
    seed as _seed,
    user as _user,
)

# 子模块名称 → 模块对象映射（用于 __getattr__ 兜底）
_SUBMODULES: dict[str, Any] = {
    "audit": _audit,
    "audit_integrity": _audit_integrity,
    "conversation": _conversation,
    "file_asset": _file_asset,
    "job": _job,
    "message": _message,
    "model_provider_config": _model_provider_config,
    "project": _project,
    "report": _report,
    "seed": _seed,
    "migration_compatibility": _migration_compatibility,
    "operating_data_reset": _operating_data_reset,
    "organization_unit": _organization_unit,
    "personal_data_migration": _personal_data_migration,
    "rotate_file_keys": _rotate_file_keys,
    "rotate_integration_keys": _rotate_integration_keys,
    "user": _user,
}

# 显式别名（领域级 Service / Repository 命名）
AuditRepository = _audit
AuditIntegrityRepository = _audit_integrity
ConversationRepository = _conversation
FileAssetRepository = _file_asset
JobRepository = _job
MessageRepository = _message
ModelProviderConfigRepository = _model_provider_config
ProjectRepository = _project
ReportRepository = _report
SeedRepository = _seed
MigrationCompatibilityRepository = _migration_compatibility
OperatingDataResetRepository = _operating_data_reset
OrganizationUnitRepository = _organization_unit
PersonalDataMigrationRepository = _personal_data_migration
FileKeyRotationRepository = _rotate_file_keys
IntegrationKeyRotationRepository = _rotate_integration_keys
UserRepository = _user


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
    "ConversationRepository",
    "FileAssetRepository",
    "JobRepository",
    "MessageRepository",
    "ModelProviderConfigRepository",
    "ProjectRepository",
    "ReportRepository",
    "SeedRepository",
    "MigrationCompatibilityRepository",
    "OperatingDataResetRepository",
    "OrganizationUnitRepository",
    "PersonalDataMigrationRepository",
    "FileKeyRotationRepository",
    "IntegrationKeyRotationRepository",
    "UserRepository",
] + list(_SUBMODULES.keys())
