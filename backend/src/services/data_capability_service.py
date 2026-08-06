"""Data capability service.

Follows the anspire service pattern: a class that receives the database
session and settings in the constructor and exposes business methods. The
``/data`` router delegates daily-brief scope resolution and data-capability
assembly to :class:`DataCapabilityService`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import Settings
from services.authz import (
    Principal,
    accessible_organization_unit_ids,
)
from services.daily_brief import DailyBriefService
from services.data_freshness import effective_domain_status
from exceptions.errors import AppError
from models import DataDomainStatus, OrganizationUnit
from schemas import DailyBriefOut, DataCapabilitiesOut, DataDomainStatusOut
from core.security import utc_now

DOMAIN_CAPABILITIES = {
    "opportunity": ["overall", "pipeline", "forecast", "customer", "organization"],
    "delivery": ["overall", "delivery", "customer", "organization", "daily_change"],
    "collection": ["overall", "finance", "collection", "customer", "organization", "daily_change"],
    "target": ["overall", "target", "organization"],
}


class DataCapabilityService:
    """Service for daily brief scope resolution and data capability reporting.

    Mirrors the anspire ``Service`` convention: stateless business logic
    layered on top of a SQLAlchemy ``AsyncSession``.
    """

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def get_daily_brief(
        self,
        principal: Principal,
        organization_unit_ids: list[uuid.UUID] | None,
    ) -> DailyBriefOut:
        """Resolve connected/allowed scopes, validate access, and build the brief."""
        result = await self._session.execute(
            select(OrganizationUnit.id).where(
                OrganizationUnit.enterprise_id == principal.enterprise_id,
                OrganizationUnit.is_active.is_(True),
                OrganizationUnit.enabled_for_analysis.is_(True),
                OrganizationUnit.data_connected.is_(True),
            )
        )
        connected = set(result.scalars().all())
        allowed = await accessible_organization_unit_ids(self._session, principal) & connected
        if not allowed:
            raise AppError(403, "data_scope_forbidden", "当前账号没有有效的事业部查询范围")

        requested = set(organization_unit_ids) if organization_unit_ids else set(allowed)
        if not requested or not requested.issubset(allowed):
            raise AppError(403, "data_scope_forbidden", "请求的事业部不在您的可查询范围内")

        brief_service = DailyBriefService(self._session, self._settings)
        return await brief_service.build(
            enterprise_id=principal.enterprise_id,
            organization_unit_ids=requested,
            connected_organization_unit_ids=connected,
        )

    async def get_data_capabilities(self, principal: Principal) -> DataCapabilitiesOut:
        """Query domain statuses and assemble the data-capability report."""
        result = await self._session.execute(
            select(DataDomainStatus)
            .where(DataDomainStatus.enterprise_id == principal.enterprise_id)
            .order_by(DataDomainStatus.domain)
        )
        rows = result.scalars().all()
        capabilities: dict[str, bool] = {
            name: False for names in DOMAIN_CAPABILITIES.values() for name in names
        }
        effective_statuses = {
            row.id: effective_domain_status(row, self._settings.data_stale_after_hours)
            for row in rows
        }
        for row in rows:
            if effective_statuses[row.id] in {"fresh", "stale", "partial"} and row.active_sync_run_id:
                for name in DOMAIN_CAPABILITIES.get(row.domain, []):
                    capabilities[name] = True
        source_types = {row.source_type for row in rows}
        source_labels = {row.source_display_name for row in rows}
        overall_status = "unavailable"
        if rows:
            statuses = [effective_statuses[row.id] for row in rows]
            if any(value == "failed" for value in statuses):
                overall_status = "partial" if any(capabilities.values()) else "failed"
            elif any(value == "stale" for value in statuses):
                overall_status = "stale"
            elif all(value == "fresh" for value in statuses):
                overall_status = "fresh"
            else:
                overall_status = "partial"
        return DataCapabilitiesOut(
            source_kind=next(iter(source_types), "not_configured"),
            source_label=" / ".join(sorted(source_labels)) or "尚未配置数据源",
            organization_unit_ids=sorted(
                await accessible_organization_unit_ids(self._session, principal), key=str
            ),
            capabilities=capabilities,
            domains=[
                DataDomainStatusOut.model_validate(row).model_copy(
                    update={"status": effective_statuses[row.id]}
                )
                for row in rows
            ],
            overall_status=overall_status,
            generated_at=utc_now(),
        )
