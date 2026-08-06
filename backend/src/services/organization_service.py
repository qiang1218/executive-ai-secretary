"""Organization service.

Follows the anspire service pattern: a class that receives the database
session in the constructor and exposes business methods. The
``/organization-units`` router delegates DB access and filtering logic to
:class:`OrganizationService`.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import OrganizationUnit
from schemas import OrganizationUnitOut
from services.authz import Principal, accessible_organization_unit_ids


class OrganizationService:
    """Service for organization unit listing.

    Mirrors the anspire ``Service`` convention: stateless business logic
    layered on top of a SQLAlchemy ``AsyncSession``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_organization_units(
        self, principal: Principal, enabled_for_analysis: bool | None = None
    ) -> list[OrganizationUnitOut]:
        """List active organization units accessible to ``principal``.

        When ``enabled_for_analysis`` is provided, results are additionally
        filtered by that flag (and, when enabled, by ``data_connected``).
        """
        ids = await accessible_organization_unit_ids(self._session, principal)
        statement = select(OrganizationUnit).where(
            OrganizationUnit.enterprise_id == principal.enterprise_id,
            OrganizationUnit.id.in_(ids),
            OrganizationUnit.is_active.is_(True),
        )
        if enabled_for_analysis is not None:
            statement = statement.where(
                OrganizationUnit.enabled_for_analysis.is_(enabled_for_analysis)
            )
            if enabled_for_analysis:
                statement = statement.where(OrganizationUnit.data_connected.is_(True))
        result = await self._session.execute(
            statement.order_by(OrganizationUnit.sort_order, OrganizationUnit.name)
        )
        items = result.scalars().all()
        return [OrganizationUnitOut.model_validate(item) for item in items]
