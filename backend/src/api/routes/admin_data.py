from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from api.deps import DataSourceServiceDep
from services.authz import Principal, require_roles
from schemas import (
    DataOperationsV3OverviewOut,
    DataSourceOut,
    DataSourceUpdate,
    DataSourceTestOut,
    ManualRunOut,
    OpportunityExperienceWeightPolicyOut,
    OpportunityExperienceWeightPolicyUpdate,
    Page,
    ScheduledTaskOut,
)

router = APIRouter(prefix="/admin", tags=["admin-data"])
OperationsPrincipal = Annotated[Principal, Depends(require_roles("enterprise_admin", "fde"))]


@router.get("/data-sources", response_model=Page)
async def list_data_sources(
    principal: OperationsPrincipal,
    service: DataSourceServiceDep,
) -> Page:
    return await service.list_data_sources(principal)


@router.get("/data-operations/overview", response_model=DataOperationsV3OverviewOut)
async def get_data_operations_overview(
    principal: OperationsPrincipal,
    service: DataSourceServiceDep,
) -> DataOperationsV3OverviewOut:
    return await service.get_data_operations_overview(principal)


@router.patch("/data-sources/{source_id}", response_model=DataSourceOut)
async def update_data_source(
    source_id: uuid.UUID,
    payload: DataSourceUpdate,
    request: Request,
    principal: OperationsPrincipal,
    service: DataSourceServiceDep,
) -> DataSourceOut:
    return await service.update_data_source(source_id, payload, principal, request)


@router.post("/data-sources/{source_id}/test", response_model=DataSourceTestOut)
async def test_data_source(
    source_id: uuid.UUID,
    request: Request,
    principal: OperationsPrincipal,
    service: DataSourceServiceDep,
) -> DataSourceTestOut:
    return await service.test_data_source(source_id, principal, request)


@router.post("/data-sources/{source_id}/sync", response_model=ManualRunOut, status_code=202)
async def sync_data_source(
    source_id: uuid.UUID,
    request: Request,
    principal: OperationsPrincipal,
    service: DataSourceServiceDep,
) -> ManualRunOut:
    return await service.sync_data_source(source_id, principal, request)


@router.post("/data-sources/{source_id}/validate", response_model=ManualRunOut, status_code=202)
async def validate_data_source_without_activation(
    source_id: uuid.UUID,
    request: Request,
    principal: OperationsPrincipal,
    service: DataSourceServiceDep,
) -> ManualRunOut:
    return await service.validate_data_source_without_activation(source_id, principal, request)


@router.get("/data-sync-runs", response_model=Page)
async def list_data_sync_runs(
    principal: OperationsPrincipal,
    service: DataSourceServiceDep,
) -> Page:
    return await service.list_data_sync_runs(principal)


@router.get(
    "/metric-policies/opportunity-experience-weight",
    response_model=OpportunityExperienceWeightPolicyOut,
)
async def get_opportunity_experience_weight_policy(
    principal: OperationsPrincipal,
    service: DataSourceServiceDep,
) -> OpportunityExperienceWeightPolicyOut:
    return await service.get_opportunity_experience_weight_policy(principal)


@router.patch(
    "/metric-policies/opportunity-experience-weight",
    response_model=OpportunityExperienceWeightPolicyOut,
)
async def update_opportunity_experience_weight_policy(
    payload: OpportunityExperienceWeightPolicyUpdate,
    request: Request,
    principal: OperationsPrincipal,
    service: DataSourceServiceDep,
) -> OpportunityExperienceWeightPolicyOut:
    return await service.update_opportunity_experience_weight_policy(payload, principal, request)


@router.get("/scheduled-tasks", response_model=Page)
async def list_scheduled_tasks(
    principal: OperationsPrincipal,
    service: DataSourceServiceDep,
) -> Page:
    return await service.list_scheduled_tasks(principal)


@router.post("/scheduled-tasks/{task_id}/run", response_model=ManualRunOut, status_code=202)
async def run_scheduled_task(
    task_id: uuid.UUID,
    request: Request,
    principal: OperationsPrincipal,
    service: DataSourceServiceDep,
) -> ManualRunOut:
    return await service.run_scheduled_task(task_id, principal, request)
