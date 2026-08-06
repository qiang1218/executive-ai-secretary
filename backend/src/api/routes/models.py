from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from services.authz import Principal, get_executive_principal
from api.deps import AuthorizedModelServiceDep
from schemas import AuthorizedModelOut

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[AuthorizedModelOut])
async def list_authorized_models(
    principal: Annotated[Principal, Depends(get_executive_principal)],
    service: AuthorizedModelServiceDep,
) -> list[AuthorizedModelOut]:
    return await service.list_authorized_models(principal)
