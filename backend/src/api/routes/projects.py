from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from services.authz import Principal, get_executive_principal
from api.deps import ProjectServiceDep
from schemas import Page, ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=Page)
async def list_projects(
    principal: Annotated[Principal, Depends(get_executive_principal)],
    project_service: ProjectServiceDep,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    include_archived: bool = False,
) -> Page:
    return await project_service.list_projects(
        principal,
        cursor=cursor,
        limit=limit,
        include_archived=include_archived,
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    request: Request,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    project_service: ProjectServiceDep,
):
    return await project_service.create_project(payload, request, principal)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    project_service: ProjectServiceDep,
) -> ProjectOut:
    return await project_service.get_project(principal, project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    project_service: ProjectServiceDep,
) -> ProjectOut:
    return await project_service.update_project(project_id, payload, request, principal)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_project(
    project_id: uuid.UUID,
    request: Request,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    project_service: ProjectServiceDep,
):
    await project_service.archive_project(project_id, request, principal)


@router.post("/{project_id}/pin", response_model=ProjectOut)
async def pin_project(
    project_id: uuid.UUID,
    request: Request,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    project_service: ProjectServiceDep,
) -> ProjectOut:
    return await project_service.pin_project(project_id, request, principal)


@router.delete("/{project_id}/pin", response_model=ProjectOut)
async def unpin_project(
    project_id: uuid.UUID,
    request: Request,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    project_service: ProjectServiceDep,
) -> ProjectOut:
    return await project_service.unpin_project(project_id, request, principal)
