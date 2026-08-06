from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.deps import OrganizationServiceDep
from services.authz import Principal, get_executive_principal
from schemas import Page

router = APIRouter(prefix="/organization-units", tags=["organization-units"])


@router.get("", response_model=Page)
async def list_organization_units(
    principal: Annotated[Principal, Depends(get_executive_principal)],
    organization_service: OrganizationServiceDep,
    enabled_for_analysis: bool | None = Query(default=None),
) -> Page:
    return Page(
        items=await organization_service.list_organization_units(
            principal, enabled_for_analysis=enabled_for_analysis
        )
    )
