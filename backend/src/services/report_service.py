"""Report service.

Follows the anspire service pattern: a class that receives the database
session in the constructor and exposes business methods. The ``/reports``
router delegates DB access and business logic to :class:`ReportService`,
keeping the route layer focused on parameter validation and response shaping.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from exceptions.errors import AppError
from models import Report
from repositories import report as report_repo
from schemas import ReportOut
from services.authz import Principal, assert_org_scope


class ReportService:
    """Service for report listing and retrieval.

    Mirrors the anspire ``Service`` convention: stateless business logic
    layered on top of a SQLAlchemy ``AsyncSession``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Ownership / shaping helpers
    # ------------------------------------------------------------------
    async def owned_report(self, principal: Principal, report_id: uuid.UUID) -> Report:
        """Return the report owned by ``principal`` or raise 404.

        Executive reports remain creator-private in phase one; the query is
        scoped to ``created_by_user_id`` and the organization unit scope is
        asserted via :func:`assert_org_scope`.
        """
        item = await report_repo.find_owned(self._session, principal, report_id)
        if item is None:
            raise AppError(404, "report_not_found", "简报不存在")
        await assert_org_scope(self._session, principal, item.organization_unit_id)
        return item

    async def report_output(
        self, item: Report, include_content: bool = True
    ) -> ReportOut:
        """Build a :class:`ReportOut` payload enriched with the latest version."""
        version = await report_repo.find_latest_version(self._session, item.id)
        output = ReportOut.model_validate(item)
        return output.model_copy(
            update={
                "latest_version": version.version if version else None,
                "content": version.content_json if version and include_content else None,
            }
        )

    # ------------------------------------------------------------------
    # Listing / detail
    # ------------------------------------------------------------------
    async def list_reports(self, principal: Principal, kind: str | None = None) -> list[ReportOut]:
        """List up to 100 most recent reports visible to ``principal``.

        Reports outside the principal's organization scope are silently
        skipped (mirrors the previous route behavior).
        """
        rows = await report_repo.list_by_owner(self._session, principal, kind=kind)
        visible: list[ReportOut] = []
        for item in rows:
            try:
                await assert_org_scope(self._session, principal, item.organization_unit_id)
            except AppError:
                continue
            visible.append(await self.report_output(item, include_content=False))
        return visible

    async def get_report(self, principal: Principal, report_id: uuid.UUID) -> ReportOut:
        """Return the serialized report for ``report_id``."""
        return await self.report_output(await self.owned_report(principal, report_id))
