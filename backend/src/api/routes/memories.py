from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from services.authz import Principal, get_executive_principal
from api.deps import MemoryServiceDep
from schemas import MemoryCreate, MemoryOut, MemoryUpdate, Page

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("", response_model=Page)
async def list_memories(
    principal: Annotated[Principal, Depends(get_executive_principal)],
    memory_service: MemoryServiceDep,
    include_disabled: bool = False,
) -> Page:
    return await memory_service.list_memories(principal, include_disabled=include_disabled)


@router.post("", response_model=MemoryOut, status_code=status.HTTP_201_CREATED)
async def create_memory(
    payload: MemoryCreate,
    request: Request,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    memory_service: MemoryServiceDep,
) -> MemoryOut:
    return await memory_service.create_memory(payload, request, principal)


@router.get("/{memory_id}", response_model=MemoryOut)
async def get_memory(
    memory_id: uuid.UUID,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    memory_service: MemoryServiceDep,
) -> MemoryOut:
    return await memory_service.get_memory(principal, memory_id)


@router.patch("/{memory_id}", response_model=MemoryOut)
async def update_memory(
    memory_id: uuid.UUID,
    payload: MemoryUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    memory_service: MemoryServiceDep,
) -> MemoryOut:
    return await memory_service.update_memory(memory_id, payload, request, principal)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: uuid.UUID,
    request: Request,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    memory_service: MemoryServiceDep,
):
    await memory_service.delete_memory(memory_id, request, principal)
