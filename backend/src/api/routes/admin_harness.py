from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from services.authz import Principal, require_roles
from api.deps import HarnessAdminServiceDep
from schemas import (
    HarnessConfigOut,
    HarnessConfigUpdate,
    HarnessMetricsOut,
    HarnessSimulationOut,
    HarnessSimulationRequest,
    HarnessTraceOut,
    HarnessVersionOut,
)

router = APIRouter(prefix="/admin/harness", tags=["admin-harness"])
OperationsPrincipal = Annotated[Principal, Depends(require_roles("enterprise_admin", "fde"))]


@router.get("/config", response_model=HarnessConfigOut)
async def get_harness_config(
    principal: OperationsPrincipal,
    service: HarnessAdminServiceDep,
) -> HarnessConfigOut:
    return await service.get_harness_config(principal)


@router.patch("/config", response_model=HarnessConfigOut)
async def update_harness_config(
    payload: HarnessConfigUpdate,
    request: Request,
    principal: OperationsPrincipal,
    service: HarnessAdminServiceDep,
) -> HarnessConfigOut:
    return await service.update_harness_config(payload, principal, request)


@router.get("/versions", response_model=list[HarnessVersionOut])
async def list_harness_versions(
    principal: OperationsPrincipal,
    service: HarnessAdminServiceDep,
    limit: int = Query(default=30, ge=1, le=100),
) -> list[HarnessVersionOut]:
    return await service.list_harness_versions(principal, limit)


@router.post("/versions/{version_id}/restore", response_model=HarnessConfigOut)
async def restore_harness_version(
    version_id: uuid.UUID,
    request: Request,
    principal: OperationsPrincipal,
    service: HarnessAdminServiceDep,
) -> HarnessConfigOut:
    return await service.restore_harness_version(version_id, principal, request)


@router.post("/simulate", response_model=HarnessSimulationOut)
async def simulate_harness(
    payload: HarnessSimulationRequest,
    request: Request,
    principal: OperationsPrincipal,
    service: HarnessAdminServiceDep,
) -> HarnessSimulationOut:
    return await service.simulate_harness(payload, principal, request)


@router.get("/metrics", response_model=HarnessMetricsOut)
async def harness_metrics(
    principal: OperationsPrincipal,
    service: HarnessAdminServiceDep,
    days: int = Query(default=30, ge=1, le=90),
) -> HarnessMetricsOut:
    return await service.harness_metrics(principal, days)


@router.get("/traces", response_model=list[HarnessTraceOut])
async def list_harness_traces(
    principal: OperationsPrincipal,
    service: HarnessAdminServiceDep,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[HarnessTraceOut]:
    return await service.list_harness_traces(principal, limit)


@router.get("/traces/{message_id}", response_model=HarnessTraceOut)
async def get_harness_trace(
    message_id: uuid.UUID,
    principal: OperationsPrincipal,
    service: HarnessAdminServiceDep,
) -> HarnessTraceOut:
    return await service.get_harness_trace(message_id, principal)
