from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from services.authz import Principal, get_executive_principal
from api.deps import AuditServiceDep, JobManagementServiceDep
from schemas import JobCreate, JobOut, Page

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=Page)
async def list_jobs(
    principal: Annotated[Principal, Depends(get_executive_principal)],
    service: JobManagementServiceDep,
) -> Page:
    return await service.list_jobs(principal)


@router.post("", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    payload: JobCreate,
    request: Request,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    service: JobManagementServiceDep,
) -> JobOut:
    return await service.create_job(payload, request, principal)


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: uuid.UUID,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    service: JobManagementServiceDep,
) -> JobOut:
    return await service.get_job(principal, job_id)


@router.post("/{job_id}/cancel", response_model=JobOut)
async def cancel_job(
    job_id: uuid.UUID,
    request: Request,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    service: JobManagementServiceDep,
    audit: AuditServiceDep,
) -> JobOut:
    return await service.cancel_job(job_id, request, principal, audit)


@router.post("/{job_id}/retry", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def retry_job(
    job_id: uuid.UUID,
    request: Request,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    service: JobManagementServiceDep,
) -> JobOut:
    return await service.retry_job(job_id, request, principal)
