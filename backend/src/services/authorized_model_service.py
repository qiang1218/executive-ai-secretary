"""Authorized model service.

Follows the anspire service pattern: a class that receives the database
session in the constructor and exposes business methods. The ``/models`` router
delegates all catalog assembly to :class:`AuthorizedModelService`.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from services.authz import Principal
from services.model_authorization import authorized_model_rows, catalog_by_id
from schemas import AuthorizedModelOut


class AuthorizedModelService:
    """Service for listing the models an enterprise is authorized to use.

    Mirrors the anspire ``Service`` convention: stateless business logic
    layered on top of a SQLAlchemy ``AsyncSession``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_authorized_models(self, principal: Principal) -> list[AuthorizedModelOut]:
        """Assemble the list of authorized models for the principal's enterprise."""
        catalog = catalog_by_id()
        output: list[AuthorizedModelOut] = []
        for row in await authorized_model_rows(self._session, principal.enterprise_id):
            item = catalog.get(row.model_id)
            if item is None:
                continue
            output.append(
                AuthorizedModelOut(
                    model_id=row.model_id,
                    name=str(item["name"]),
                    family=str(item["family"]),
                    profile=str(item["profile"]),
                    display_name=(
                        str(item["name"])
                        if not row.display_name or row.display_name == row.model_id
                        else row.display_name
                    ),
                    is_default=row.is_default,
                )
            )
        return output
