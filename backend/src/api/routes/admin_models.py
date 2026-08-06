from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from services.authz import Principal, require_roles
from configs.settings import Settings, get_settings
from db.session import get_db
from api.deps import ModelAdminServiceDep
from schemas import (
    AdminModelAuthorizationOut,
    AdminModelCatalogOut,
    DefaultModelUpdate,
    ModelAuthorizationUpdate,
    ModelProviderOut,
    ModelProviderTestOut,
    ModelProviderUpdate,
)

router = APIRouter(prefix="/admin/model-provider", tags=["admin-model-provider"])
models_router = APIRouter(prefix="/admin/models", tags=["admin-model-authorization"])
OperationsPrincipal = Annotated[Principal, Depends(require_roles("enterprise_admin", "fde"))]


@router.get("", response_model=ModelProviderOut)
async def get_model_provider(
    principal: OperationsPrincipal,
    service: ModelAdminServiceDep,
) -> ModelProviderOut:
    return await service.get_model_provider(principal)


@router.put("", response_model=ModelProviderOut)
async def update_model_provider(
    payload: ModelProviderUpdate,
    request: Request,
    principal: OperationsPrincipal,
    service: ModelAdminServiceDep,
) -> ModelProviderOut:
    return await service.update_model_provider(payload, principal, request)


@router.post("/test", response_model=ModelProviderTestOut)
async def test_model_provider(
    request: Request,
    principal: OperationsPrincipal,
    service: ModelAdminServiceDep,
) -> ModelProviderTestOut:
    return await service.test_model_provider(principal, request)


@models_router.get("", response_model=AdminModelCatalogOut)
async def get_admin_models(
    principal: OperationsPrincipal,
    service: ModelAdminServiceDep,
) -> AdminModelCatalogOut:
    return await service.get_admin_models(principal)


@models_router.post("/{model_id}/test", response_model=ModelProviderTestOut)
async def test_authorized_model(
    model_id: str,
    request: Request,
    principal: OperationsPrincipal,
    service: ModelAdminServiceDep,
) -> ModelProviderTestOut:
    return await service.test_authorized_model(model_id, principal, request)


@models_router.patch("/{model_id}/authorization", response_model=AdminModelAuthorizationOut)
async def update_model_authorization(
    model_id: str,
    payload: ModelAuthorizationUpdate,
    request: Request,
    principal: OperationsPrincipal,
    service: ModelAdminServiceDep,
) -> AdminModelAuthorizationOut:
    return await service.update_model_authorization(model_id, payload, principal, request)


@models_router.patch("/{model_id}/default", response_model=AdminModelAuthorizationOut)
async def set_default_model(
    model_id: str,
    payload: DefaultModelUpdate,
    request: Request,
    principal: OperationsPrincipal,
    service: ModelAdminServiceDep,
) -> AdminModelAuthorizationOut:
    del payload
    return await service.set_default_model(model_id, principal, request)
