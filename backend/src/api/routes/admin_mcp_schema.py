"""MCP v2 Schema 管理路由。

挂载在 ``/admin/mcp-schemas`` 前缀下；v2 用 :class:`mcp_schema_registry` +
``discover_schema`` / ``query_schema`` / ``execute_query`` 三个通用 MCP 工具
代替旧版逐 case hardcode handler。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from api.deps import (
    McpSchemaServiceDep,
    PrincipalDep,
)
from schemas.mcp_schema import (
    McpSchemaCandidateListOut,
    McpSchemaCatalogOut,
    McpSchemaDeleteOut,
    McpSchemaOut,
    McpSchemaRefreshOut,
    McpSchemaRegisterIn,
    McpSchemaUpdate,
)

router = APIRouter(prefix="/admin/mcp-schemas", tags=["admin-mcp-schemas"])


@router.get("/candidates", response_model=McpSchemaCandidateListOut)
async def list_candidates(
    principal: PrincipalDep,
    service: McpSchemaServiceDep,
):
    """候选物理表列表(BUILTIN_TABLES - 已注册表),用于"勾选注册"工作流。"""

    return await service.list_candidates(principal)


@router.post("/register/{table_name}", response_model=McpSchemaOut, status_code=201)
async def register_schema(
    payload: McpSchemaRegisterIn | None = None,
    table_name: str = Path(description="物理表名"),
    principal: PrincipalDep = ...,
    service: McpSchemaServiceDep = ...,
):
    """注册一张新的物理表(从 BUILTIN_TABLES 模板创建 McpSchemaRegistry 行)。"""

    return await service.register_table(table_name, payload, principal)


@router.post("/unregister/{table_name}", response_model=McpSchemaDeleteOut)
async def unregister_schema(
    table_name: str = Path(description="物理表名"),
    principal: PrincipalDep = ...,
    service: McpSchemaServiceDep = ...,
):
    """注销某张表(只删 mcp_schema_registry 行,不删除物理表)。"""

    return await service.unregister_table(table_name, principal)


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
