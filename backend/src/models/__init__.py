"""ORM 模型聚合包。

按领域拆分为多个子模块；本 ``__init__`` 把全部符号 re-export 出来，
保持 ``from models import User`` 的向后兼容。
"""

from __future__ import annotations

from .audit import *  # noqa: F401,F403
from .enterprise import *  # noqa: F401,F403
from .user import *  # noqa: F401,F403
from .project import *  # noqa: F401,F403
from .conversation import *  # noqa: F401,F403
from .file import *  # noqa: F401,F403
from .memory import *  # noqa: F401,F403
from .report import *  # noqa: F401,F403
from .job import *  # noqa: F401,F403
from .config import *  # noqa: F401,F403
from .data_source import *  # noqa: F401,F403
from .data_warehouse import *  # noqa: F401,F403

# 显式列出主要符号，便于 IDE 自动补全
__all__ = [
    "AuditChainHead",
    "AuditEvent",
    "IdempotencyRecord",
    "Enterprise",
    "OrganizationUnit",
    "DataScopeGrant",
    "User",
    "UserCredential",
    "UserSession",
    "ExecutivePersonalProfile",
    "Project",
    "Conversation",
    "ConversationOrganizationScope",
    "ProjectConversation",
    "Message",
    "MessageRun",
    "MessageRoute",
    "HarnessStageRun",
    "HarnessDiagnosticGrant",
    "Clarification",
    "MessageEvidence",
    "FileAsset",
    "ConversationFile",
    "FileEvent",
    "FileExtraction",
    "FileChunk",
    "Memory",
    "MemoryEvent",
    "Report",
    "ReportVersion",
    "Job",
    "JobAttempt",
    "AppConfig",
    "SecretReference",
    "ModelProviderConfig",
    "EnterpriseModelAuthorization",
    "McpToolConfig",
    "McpToolDefinition",
    "HarnessConfigVersion",
    "OpportunityExperienceWeightPolicy",
    "DataSource",
    "ScheduledTask",
    "ScheduleRun",
    "DataSyncRun",
    "DataDomainStatus",
    "SourceCheckpoint",
    "DimPerson",
    "DimCustomer",
    "FactOpportunity",
    "FactOpportunityParticipant",
    "FactOpportunityProduct",
    "FactDelivery",
    "FactFinanceCollection",
    "FactTarget",
    "DailySnapshot",
]