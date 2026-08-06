from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from api.deps import ReportServiceDep
from services.authz import Principal, get_executive_principal
from schemas import Page, ReportOut

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=Page)
async def list_reports(
    principal: Annotated[Principal, Depends(get_executive_principal)],
    report_service: ReportServiceDep,
    kind: str | None = None,
) -> Page:
    return Page(items=await report_service.list_reports(principal, kind=kind))


@router.get("/{report_id}", response_model=ReportOut)
async def get_report(
    report_id: uuid.UUID,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    report_service: ReportServiceDep,
) -> ReportOut:
    return await report_service.get_report(principal, report_id)
