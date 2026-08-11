"""FastAPI 依赖注入层。

将 ``db.session.get_db_async``、``services.authz.get_current_principal``
等作为 :class:`typing.Annotated` 别名导出，便于 router 层以 ``db: AsyncSessionDep``
风格注入异步数据库会话与当前主体。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from services.admin_service import AdminService
from services.auth_service import AuthService
from services.authorized_model_service import AuthorizedModelService
from services.audit_service import AuditService
from services.authz import (
    Principal,
    get_current_principal,
    get_executive_principal,
)
from services.conversation_service import ConversationService
from services.data_capability_service import DataCapabilityService
from services.data_source_service import DataSourceService
from services.daily_brief import DailyBriefService
from services.email_account_service import EmailAccountService
from services.file_service import FileService
from services.harness_admin_service import HarnessAdminService
from services.health_service import HealthService
from services.job_management_service import JobManagementService
from services.mcp_schema_service import McpSchemaService
from services.memory_service import MemoryService
from services.model_admin_service import ModelAdminService
from services.entity_indexer_service import EntityIndexerService
from services.notification_service import NotificationService
from services.hermes_client import HermesClient
from services.organization_service import OrganizationService
from services.project_service import ProjectService
from services.report_service import ReportService
from services.skill_service import SkillService
from configs.settings import Settings, get_settings
from db.session import get_db_async

AsyncSessionDep = Annotated[AsyncSession, Depends(get_db_async)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]
ExecutivePrincipalDep = Annotated[Principal, Depends(get_executive_principal)]


async def get_audit_service(session: AsyncSessionDep) -> AuditService:
    """FastAPI dependency: instantiate ``AuditService`` with the request session."""
    return AuditService(session)


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


async def get_auth_service(session: AsyncSessionDep, settings: SettingsDep) -> AuthService:
    """FastAPI dependency: instantiate ``AuthService``."""
    return AuthService(session, settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def get_daily_brief_service(
    session: AsyncSessionDep, settings: SettingsDep
) -> DailyBriefService:
    """FastAPI dependency: instantiate ``DailyBriefService``."""
    return DailyBriefService(session, settings)


DailyBriefServiceDep = Annotated[DailyBriefService, Depends(get_daily_brief_service)]


async def get_authorized_model_service(
    session: AsyncSessionDep,
) -> AuthorizedModelService:
    """FastAPI dependency: instantiate ``AuthorizedModelService``."""
    return AuthorizedModelService(session)


AuthorizedModelServiceDep = Annotated[
    AuthorizedModelService, Depends(get_authorized_model_service)
]


async def get_conversation_service(session: AsyncSessionDep) -> ConversationService:
    """FastAPI dependency: instantiate ``ConversationService`` with the request session."""
    return ConversationService(session)


ConversationServiceDep = Annotated[
    ConversationService, Depends(get_conversation_service)
]


async def get_data_capability_service(
    session: AsyncSessionDep, settings: SettingsDep
) -> DataCapabilityService:
    """FastAPI dependency: instantiate ``DataCapabilityService``."""
    return DataCapabilityService(session, settings)


DataCapabilityServiceDep = Annotated[
    DataCapabilityService, Depends(get_data_capability_service)
]


async def get_data_source_service(session: AsyncSessionDep) -> DataSourceService:
    """FastAPI dependency: instantiate ``DataSourceService`` with the request session."""
    return DataSourceService(session)


DataSourceServiceDep = Annotated[DataSourceService, Depends(get_data_source_service)]


async def get_job_management_service(
    session: AsyncSessionDep, settings: SettingsDep
) -> JobManagementService:
    """FastAPI dependency: instantiate ``JobManagementService``."""
    return JobManagementService(session, settings)


JobManagementServiceDep = Annotated[
    JobManagementService, Depends(get_job_management_service)
]


async def get_memory_service(
    session: AsyncSessionDep, settings: SettingsDep
) -> MemoryService:
    """FastAPI dependency: instantiate ``MemoryService``."""
    return MemoryService(session, settings)


MemoryServiceDep = Annotated[MemoryService, Depends(get_memory_service)]


async def get_email_account_service(
    session: AsyncSessionDep, settings: SettingsDep
) -> EmailAccountService:
    """FastAPI dependency: instantiate ``EmailAccountService``."""
    return EmailAccountService(session, settings)


EmailAccountServiceDep = Annotated[
    EmailAccountService, Depends(get_email_account_service)
]


async def get_notification_service(
    session: AsyncSessionDep, settings: SettingsDep
) -> NotificationService:
    """FastAPI dependency: instantiate ``NotificationService``."""
    return NotificationService(session, settings)


NotificationServiceDep = Annotated[
    NotificationService, Depends(get_notification_service)
]


async def get_project_service(session: AsyncSessionDep) -> ProjectService:
    """FastAPI dependency: instantiate ``ProjectService``."""
    return ProjectService(session)


ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]


async def get_mcp_schema_service(session: AsyncSessionDep) -> McpSchemaService:
    """FastAPI dependency: instantiate ``McpSchemaService``."""
    return McpSchemaService(session)


McpSchemaServiceDep = Annotated[McpSchemaService, Depends(get_mcp_schema_service)]


async def get_entity_indexer_service(
    session: AsyncSessionDep, settings: SettingsDep
) -> EntityIndexerService:
    """FastAPI dependency: instantiate ``EntityIndexerService``."""
    return EntityIndexerService(session, settings)


EntityIndexerServiceDep = Annotated[
    EntityIndexerService, Depends(get_entity_indexer_service)
]


async def get_admin_service(
    session: AsyncSessionDep, settings: SettingsDep
) -> AdminService:
    """FastAPI dependency: instantiate ``AdminService``.

    Settings is required for the password validation and runtime status
    endpoints. Routes that only need DB access can still construct
    ``AdminService(db)`` directly without settings.
    """
    return AdminService(session, settings)


AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]


async def get_file_service(session: AsyncSessionDep) -> FileService:
    """FastAPI dependency: instantiate ``FileService`` with the request session."""
    return FileService(session)


FileServiceDep = Annotated[FileService, Depends(get_file_service)]


async def get_report_service(session: AsyncSessionDep) -> ReportService:
    """FastAPI dependency: instantiate ``ReportService`` with the request session."""
    return ReportService(session)


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]


async def get_organization_service(session: AsyncSessionDep) -> OrganizationService:
    """FastAPI dependency: instantiate ``OrganizationService`` with the request session."""
    return OrganizationService(session)


OrganizationServiceDep = Annotated[OrganizationService, Depends(get_organization_service)]


async def get_model_admin_service(
    session: AsyncSessionDep, settings: SettingsDep
) -> ModelAdminService:
    """FastAPI dependency: instantiate ``ModelAdminService`` with the request session."""
    return ModelAdminService(session, settings)


ModelAdminServiceDep = Annotated[ModelAdminService, Depends(get_model_admin_service)]


async def get_harness_admin_service(
    session: AsyncSessionDep, settings: SettingsDep
) -> HarnessAdminService:
    """FastAPI dependency: instantiate ``HarnessAdminService``.

    Settings is required for the simulation endpoints that invoke the
    hermes runtime. Routes that only need DB access can still construct
    ``HarnessAdminService(db, settings)`` directly.
    """
    return HarnessAdminService(session, settings)


HarnessAdminServiceDep = Annotated[
    HarnessAdminService, Depends(get_harness_admin_service)
]


async def get_health_service(
    session: AsyncSessionDep, settings: SettingsDep
) -> HealthService:
    """FastAPI dependency: instantiate ``HealthService``."""
    return HealthService(session, settings)


HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]


async def get_hermes_client(settings: SettingsDep) -> HermesClient:
    """FastAPI dependency: instantiate ``HermesClient`` with the request settings."""
    return HermesClient(settings)


HermesClientDep = Annotated[HermesClient, Depends(get_hermes_client)]


async def get_skill_service(
    session: AsyncSessionDep, settings: SettingsDep
) -> SkillService:
    """FastAPI dependency: instantiate ``SkillService``."""
    return SkillService(session, settings)


SkillServiceDep = Annotated[SkillService, Depends(get_skill_service)]


__all__ = [
    "AsyncSessionDep",
    "SettingsDep",
    "PrincipalDep",
    "ExecutivePrincipalDep",
    "AuditServiceDep",
    "DailyBriefServiceDep",
    "AuthorizedModelServiceDep",
    "DataCapabilityServiceDep",
    "EmailAccountServiceDep",
    "JobManagementServiceDep",
    "MemoryServiceDep",
    "NotificationServiceDep",
    "ProjectServiceDep",
    "FileServiceDep",
    "ReportServiceDep",
    "OrganizationServiceDep",
    "DataSourceServiceDep",
    "McpSchemaServiceDep",
    "EntityIndexerServiceDep",
    "EntityIndexerService",
    "AuthServiceDep",
    "AdminServiceDep",
    "ConversationServiceDep",
    "ModelAdminServiceDep",
    "HarnessAdminServiceDep",
    "HealthServiceDep",
    "HermesClientDep",
    "SkillServiceDep",
    "AuditService",
    "AuthService",
    "DailyBriefService",
    "AuthorizedModelService",
    "DataCapabilityService",
    "JobManagementService",
    "MemoryService",
    "ProjectService",
    "FileService",
    "ReportService",
    "OrganizationService",
    "DataSourceService",
    "McpSchemaService",
    "ConversationService",
    "ModelAdminService",
    "HarnessAdminService",
    "HealthService",
    "HermesClient",
    "SkillService",
    "Principal",
    "get_current_principal",
    "get_executive_principal",
    "get_audit_service",
    "get_auth_service",
    "get_daily_brief_service",
    "get_authorized_model_service",
    "get_data_capability_service",
    "get_job_management_service",
    "get_memory_service",
    "get_project_service",
    "get_admin_service",
    "get_file_service",
    "get_report_service",
    "get_organization_service",
    "get_data_source_service",
    "get_mcp_schema_service",
    "get_conversation_service",
    "get_model_admin_service",
    "get_harness_admin_service",
    "get_health_service",
    "get_hermes_client",
    "get_skill_service",
    "get_db_async",
    "get_settings",
    "Settings",
]
