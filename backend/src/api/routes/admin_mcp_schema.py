"""MCP v2 Schema 管理路由。

提供表级 schema 注册的 CRUD + 刷新接口。
挂载在 ``/admin/mcp-schemas`` 前缀下。

旧 ``/admin/mcp-tools`` 路由（``admin_mcp.py``）保持不变，后续 Phase 4 清理。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from api.deps import (
    McpSchemaServiceDep,
    PrincipalDep,
)
from schemas.mcp_schema import (
    McpSchemaCatalogOut,
    McpSchemaOut,
    McpSchemaRefreshOut,
    McpSchemaUpdate,
)

router = APIRouter(prefix="/admin/mcp-schemas", tags=["admin-mcp-schemas"])


@router.get("", response_model=McpSchemaCatalogOut)
async def list_schemas(
    principal: PrincipalDep,
    service: McpSchemaServiceDep,
):
    """列出企业所有已注册的数据表 schema。"""
    return await service.list_schemas(principal)


@router.get("/{table_name}", response_model=McpSchemaOut)
async def get_schema(
    table_name: str = Path(description="物理表名"),
    principal: PrincipalDep = ...,
    service: McpSchemaServiceDep = ...,
):
    """获取指定表的 schema 详情。"""
    schema = await service.get_schema(table_name, principal)
    if schema is None:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
    return schema


@router.patch("/{table_name}", response_model=McpSchemaOut)
async def update_schema(
    payload: McpSchemaUpdate,
    table_name: str = Path(description="物理表名"),
    principal: PrincipalDep = ...,
    service: McpSchemaServiceDep = ...,
):
    """更新表配置（显示名称、启用状态、限制参数等）。"""
    schema = await service.update_schema(table_name, payload, principal)
    if schema is None:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
    return schema


@router.post("/{table_name}/refresh", response_model=McpSchemaRefreshOut)
async def refresh_schema(
    table_name: str = Path(description="物理表名"),
    principal: PrincipalDep = ...,
    service: McpSchemaServiceDep = ...,
):
    """刷新指定表的列结构（从数据库自动发现最新 schema）。"""
    return await service.refresh_schema(table_name, principal)


@router.post("/refresh-all", response_model=McpSchemaCatalogOut)
async def refresh_all_schemas(
    principal: PrincipalDep,
    service: McpSchemaServiceDep,
):
    """刷新企业所有注册表的 schema。"""
    return await service.refresh_all(principal)
