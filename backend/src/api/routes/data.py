from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from services.authz import Principal, get_executive_principal
from api.deps import DataCapabilityServiceDep
from schemas import DailyBriefOut, DataCapabilitiesOut

router = APIRouter(tags=["data"])


@router.get("/daily-brief", response_model=DailyBriefOut)
async def get_daily_brief(
    principal: Annotated[Principal, Depends(get_executive_principal)],
    service: DataCapabilityServiceDep,
    organization_unit_ids: Annotated[list[uuid.UUID] | None, Query()] = None,
) -> DailyBriefOut:
    return await service.get_daily_brief(principal, organization_unit_ids)


@router.get("/data-capabilities", response_model=DataCapabilitiesOut)
async def get_data_capabilities(
    principal: Annotated[Principal, Depends(get_executive_principal)],
    service: DataCapabilityServiceDep,
) -> DataCapabilitiesOut:
    return await service.get_data_capabilities(principal)
