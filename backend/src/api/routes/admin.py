from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from api.deps import AdminServiceDep
from schemas import (
    AuditVerification,
    DataScopeUpdate,
    OrganizationUnitCreate,
    OrganizationUnitOut,
    OrganizationUnitUpdate,
    Page,
    RuntimeStatus,
    TemporaryPasswordRequest,
    UserCreate,
    UserOut,
    UserUpdate,
)
from services.authz import Principal, require_roles

router = APIRouter(prefix="/admin", tags=["admin"])
AdminPrincipal = Annotated[Principal, Depends(require_roles("enterprise_admin"))]
OperationsPrincipal = Annotated[
    Principal, Depends(require_roles("enterprise_admin", "fde"))
]


@router.get("/users", response_model=Page)
async def list_users(
    principal: AdminPrincipal,
    service: AdminServiceDep,
) -> Page:
    return await service.list_users(principal)


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    request: Request,
    principal: AdminPrincipal,
    service: AdminServiceDep,
) -> UserOut:
    return await service.create_user(payload, principal, request)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    request: Request,
    principal: AdminPrincipal,
    service: AdminServiceDep,
) -> UserOut:
    return await service.update_user(user_id, payload, principal, request)


@router.post("/users/{user_id}/reset-password", response_model=UserOut)
async def reset_password(
    user_id: uuid.UUID,
    payload: TemporaryPasswordRequest,
    request: Request,
    principal: AdminPrincipal,
    service: AdminServiceDep,
) -> UserOut:
    return await service.reset_password(user_id, payload, principal, request)


@router.put(
    "/users/{user_id}/data-scopes", response_model=list[OrganizationUnitOut]
)
async def replace_data_scopes(
    user_id: uuid.UUID,
    payload: DataScopeUpdate,
    request: Request,
    principal: AdminPrincipal,
    service: AdminServiceDep,
) -> list[OrganizationUnitOut]:
    return await service.replace_data_scopes(user_id, payload, principal, request)


@router.delete(
    "/users/{user_id}/sessions", status_code=status.HTTP_204_NO_CONTENT
)
async def revoke_user_sessions(
    user_id: uuid.UUID,
    request: Request,
    principal: AdminPrincipal,
    service: AdminServiceDep,
):
    await service.revoke_user_sessions(user_id, principal, request)


@router.get("/organization-units", response_model=Page)
async def admin_list_organization_units(
    principal: AdminPrincipal,
    service: AdminServiceDep,
) -> Page:
    return await service.list_organization_units(principal)


@router.post(
    "/organization-units",
    response_model=OrganizationUnitOut,
    status_code=201,
)
async def create_organization_unit(
    payload: OrganizationUnitCreate,
    request: Request,
    principal: AdminPrincipal,
    service: AdminServiceDep,
) -> OrganizationUnitOut:
    return await service.create_organization_unit(payload, principal, request)


@router.patch(
    "/organization-units/{unit_id}", response_model=OrganizationUnitOut
)
async def update_organization_unit(
    unit_id: uuid.UUID,
    payload: OrganizationUnitUpdate,
    request: Request,
    principal: AdminPrincipal,
    service: AdminServiceDep,
) -> OrganizationUnitOut:
    return await service.update_organization_unit(unit_id, payload, principal, request)


@router.get("/audit-events", response_model=Page)
async def list_audit_events(
    principal: OperationsPrincipal,
    service: AdminServiceDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> Page:
    return await service.list_audit_events(principal, limit)


@router.get("/runtime", response_model=RuntimeStatus)
async def runtime_status(
    principal: OperationsPrincipal,
    service: AdminServiceDep,
) -> RuntimeStatus:
    return await service.runtime_status(principal)


@router.post("/audit-events/verify", response_model=AuditVerification)
async def verify_audit_events(
    request: Request,
    principal: AdminPrincipal,
    service: AdminServiceDep,
) -> AuditVerification:
    return await service.verify_audit_events(principal, request)
