from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from api.deps import McpToolServiceDep
from schemas import (
    McpCompositeToolCreate,
    McpToolCatalogOut,
    McpToolOut,
    McpToolUpdate,
    McpToolValidationOut,
)
from services.authz import Principal, require_roles

router = APIRouter(prefix="/admin/mcp-tools", tags=["admin-mcp-tools"])
OperationsPrincipal = Annotated[Principal, Depends(require_roles("enterprise_admin", "fde"))]


@router.get("", response_model=McpToolCatalogOut)
async def list_mcp_tools(
    principal: OperationsPrincipal,
    service: McpToolServiceDep,
) -> McpToolCatalogOut:
    return await service.list_mcp_tools(principal)


@router.post("", response_model=McpToolOut, status_code=201)
async def create_mcp_tool(
    payload: McpCompositeToolCreate,
    request: Request,
    principal: OperationsPrincipal,
    service: McpToolServiceDep,
) -> McpToolOut:
    return await service.create_mcp_tool(payload, principal, request)


@router.patch("/{tool_name}", response_model=McpToolOut)
async def update_mcp_tool(
    tool_name: str,
    payload: McpToolUpdate,
    request: Request,
    principal: OperationsPrincipal,
    service: McpToolServiceDep,
) -> McpToolOut:
    return await service.update_mcp_tool(tool_name, payload, principal, request)


@router.post("/{tool_name}/validate", response_model=McpToolValidationOut)
async def validate_mcp_tool(
    tool_name: str,
    request: Request,
    principal: OperationsPrincipal,
    service: McpToolServiceDep,
) -> McpToolValidationOut:
    return await service.validate_mcp_tool(tool_name, principal, request)
