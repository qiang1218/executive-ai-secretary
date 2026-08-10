"""Pydantic schema 聚合包。

按领域拆分为多个子模块；本 ``__init__`` 把全部符号 re-export 出来。
"""

from __future__ import annotations

from .audit import *  # noqa: F401,F403
from .auth import *  # noqa: F401,F403
from .common import *  # noqa: F401,F403
from .conversation import *  # noqa: F401,F403
from .data import *  # noqa: F401,F403
from .data_source import *  # noqa: F401,F403
from .enterprise import *  # noqa: F401,F403
from .file import *  # noqa: F401,F403
from .harness import *  # noqa: F401,F403
from .job import *  # noqa: F401,F403
from .mcp import *  # noqa: F401,F403
from .mcp_schema import *  # noqa: F401,F403
from .model_provider import *  # noqa: F401,F403
from .organization import *  # noqa: F401,F403
from .project import *  # noqa: F401,F403
from .report import *  # noqa: F401,F403
from .runtime import *  # noqa: F401,F403
from .skill import *  # noqa: F401,F403
from .user import *  # noqa: F401,F403

__all__ = [
    "AuditEventOut",
    "AuditVerification",
    "LoginRequest",
    "LoginResponse",
    "ChangePasswordRequest",
    "MeResponse",
    "SessionOut",
    "MessageCreate",
    "MessageOut",
    "MemoryCreate",
    "MemoryUpdate",
    "MemoryOut",
    "MessageEvidenceOut",
    "ConversationCreate",
    "ConversationUpdate",
    "ConversationOut",
    "ConversationProjectUpdate",
    "ClarificationResolve",
    "ClarificationOut",
    "DiagnosticShareOut",
    "DataDomainStatusOut",
    "DataCapabilitiesOut",
    "DailyBriefItemOut",
    "DailyBriefDomainReadinessOut",
    "DailyBriefOut",
    "DataOperationsV3OverviewOut",
    "DataSourceOut",
    "DataSourceUpdate",
    "DataSourceTestOut",
    "DataSyncRunOut",
    "FeishuFieldBindingOut",
    "FeishuTableBindingStatusOut",
    "DataSourceOperationsStatusOut",
    "ExperienceWeightValues",
    "OpportunityExperienceWeightPolicyOut",
    "OpportunityExperienceWeightPolicyUpdate",
    "ScheduledTaskOut",
    "ManualRunOut",
    "EnterpriseOut",
    "FileOut",
    "FileExtractionOut",
    "HarnessConfigOut",
    "HarnessConfigUpdate",
    "HarnessVersionOut",
    "HarnessSimulationRequest",
    "HarnessSimulationOut",
    "HarnessMetricsOut",
    "HarnessTraceOut",
    "JobCreate",
    "JobOut",
    "McpColumnSchema",
    "McpSchemaOut",
    "McpSchemaCatalogOut",
    "McpSchemaUpdate",
    "McpSchemaRefreshOut",
    "McpToolOut",
    "McpToolCatalogOut",
    "McpToolUpdate",
    "McpCompositeToolCreate",
    "McpToolValidationOut",
    "ModelCatalogItem",
    "ModelProviderOut",
    "ModelProviderUpdate",
    "ModelProviderTestOut",
    "AuthorizedModelOut",
    "AdminModelAuthorizationOut",
    "AdminModelCatalogOut",
    "ModelAuthorizationUpdate",
    "DefaultModelUpdate",
    "OrganizationUnitOut",
    "OrganizationUnitCreate",
    "OrganizationUnitUpdate",
    "OrganizationScopeInput",
    "OrganizationScopeOut",
    "DataScopeUpdate",
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectOut",
    "ReportOut",
    "RuntimeStatus",
    "UserOut",
    "UserPreferenceUpdate",
    "ExecutivePersonalProfileOut",
    "ExecutivePersonalProfileUpdate",
    "UserCreate",
    "UserUpdate",
    "TemporaryPasswordRequest",
    "SkillCreate",
    "SkillUpdate",
    "SkillOut",
    "SkillListItem",
    "SkillListOut",
]


# 拆分到子模块后，部分 Pydantic 模型引用了其他子模块的类型（例如
# ``LoginResponse`` 引用 ``UserOut``）。这里在所有子模块加载完毕后统一
# 调用 ``model_rebuild()``，把 forward reference 解析为真实类型。
from pydantic import BaseModel as _BaseModel  # noqa: E402

for _name in list(globals().keys()):
    _obj = globals()[_name]
    if isinstance(_obj, type) and issubclass(_obj, _BaseModel):
        try:
            _obj.model_rebuild()
        except Exception:  # noqa: BLE001
            pass