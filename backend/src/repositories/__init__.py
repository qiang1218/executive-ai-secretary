"""仓储层（纯数据访问），PEP 562 ``__getattr__`` 兜底子模块符号。"""
from __future__ import annotations

from typing import Any

from . import (
    audit as _audit,
    audit_integrity as _audit_integrity,
    conversation as _conversation,
    email as _email,
    file_asset as _file_asset,
    job as _job,
    message as _message,
    migration_compatibility as _migration_compatibility,
    model_provider_config as _model_provider_config,
    notification as _notification,
    operating_data_reset as _operating_data_reset,
    organization_unit as _organization_unit,
    project as _project,
    report as _report,
    seed as _seed,
    user as _user,
)

_SUBMODULES: dict[str, Any] = {
    "audit": _audit,
    "audit_integrity": _audit_integrity,
    "conversation": _conversation,
    "email": _email,
    "file_asset": _file_asset,
    "job": _job,
    "message": _message,
    "model_provider_config": _model_provider_config,
    "notification": _notification,
    "project": _project,
    "report": _report,
    "seed": _seed,
    "migration_compatibility": _migration_compatibility,
    "operating_data_reset": _operating_data_reset,
    "organization_unit": _organization_unit,
    "user": _user,
}

AuditRepository = _audit
AuditIntegrityRepository = _audit_integrity
ConversationRepository = _conversation
EmailRepository = _email
FileAssetRepository = _file_asset
JobRepository = _job
MessageRepository = _message
ModelProviderConfigRepository = _model_provider_config
NotificationRepository = _notification
ProjectRepository = _project
ReportRepository = _report
SeedRepository = _seed
MigrationCompatibilityRepository = _migration_compatibility
OperatingDataResetRepository = _operating_data_reset
OrganizationUnitRepository = _organization_unit
UserRepository = _user


def __getattr__(name: str) -> Any:
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
    "EmailRepository",
    "FileAssetRepository",
    "JobRepository",
    "MessageRepository",
    "ModelProviderConfigRepository",
    "NotificationRepository",
    "ProjectRepository",
    "ReportRepository",
    "SeedRepository",
    "MigrationCompatibilityRepository",
    "OperatingDataResetRepository",
    "OrganizationUnitRepository",
    "UserRepository",
] + list(_SUBMODULES.keys())
