"""MCP tool service.

Follows the anspire service pattern: a class that receives the database
session in the constructor and exposes business methods. The
``/admin/mcp-tools`` router instantiates ``McpToolService(db)`` and
delegates all DB / business logic here.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import utc_now
from exceptions.errors import AppError
from models import DataDomainStatus, McpToolConfig, McpToolDefinition
from repositories.audit import record_audit
from schemas import (
    McpCompositeToolCreate,
    McpToolCatalogOut,
    McpToolOut,
    McpToolUpdate,
    McpToolValidationOut,
)
from services.authz import Principal
from starlette.concurrency import run_in_threadpool
from worker_old.mcp_registry import (
    MCP_TOOL_SPECS,
    effective_catalog,
    registered_spec,
)


class McpToolService:
    """Service for MCP tool catalog, definition, and config lifecycle.

    Mirrors the anspire ``Service`` convention: stateless business logic
    layered on top of a SQLAlchemy ``AsyncSession``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------ utils

    async def _domain_readiness(self, principal: Principal) -> dict[str, bool]:
        result = await self._session.execute(
            select(DataDomainStatus).where(
                DataDomainStatus.enterprise_id == principal.enterprise_id
            )
        )
        rows = result.scalars().all()
        return {
            row.domain: bool(
                row.status in {"fresh", "stale", "partial"} and row.active_sync_run_id
            )
            for row in rows
        }

    @staticmethod
    def _decorate(
        item: dict[str, Any],
        readiness: dict[str, bool],
        catalog_by_name: dict[str, dict[str, Any]],
    ) -> McpToolOut:
        issues = [domain for domain in item["domains"] if not readiness.get(domain, False)]
        if item["source_type"] == "composite":
            for component in item["component_tools"]:
                dependency = catalog_by_name.get(component)
                if dependency is None:
                    issues.append(f"依赖工具不存在：{component}")
                elif not dependency["is_enabled"]:
                    issues.append(f"依赖工具已停用：{dependency['display_name']}")
        if not item["is_enabled"]:
            state = "disabled"
            messages = ["工具已由企业管理员停用"]
        elif issues:
            state = "data_unavailable"
            messages = [f"数据域尚不可用：{domain}" for domain in issues]
        else:
            state = "ready"
            messages = []
        return McpToolOut(
            **item,
            readiness=state,
            readiness_issues=messages,
        )

    async def _catalog(self, principal: Principal) -> McpToolCatalogOut:
        readiness = await self._domain_readiness(principal)
        raw_catalog = await run_in_threadpool(
            effective_catalog, self._session, principal.enterprise_id
        )
        catalog_by_name = {item["tool_name"]: item for item in raw_catalog}
        tools = [self._decorate(item, readiness, catalog_by_name) for item in raw_catalog]
        return McpToolCatalogOut(
            tools=tools,
            enabled_count=sum(item.is_enabled for item in tools),
            planner_count=sum(item.is_enabled and item.planner_enabled for item in tools),
            generated_at=utc_now(),
        )

    # ---------------------------------------------------------------- queries

    async def list_mcp_tools(self, principal: Principal) -> McpToolCatalogOut:
        return await self._catalog(principal)

    # --------------------------------------------------------------- mutations

    async def create_mcp_tool(
        self,
        payload: McpCompositeToolCreate,
        principal: Principal,
        request: Request,
    ) -> McpToolOut:
        if (
            await run_in_threadpool(
                registered_spec, self._session, principal.enterprise_id, payload.tool_name
            )
            is not None
        ):
            raise AppError(409, "mcp_tool_name_conflict", "工具标识已经存在")
        component_names = list(dict.fromkeys(payload.component_tools))
        if len(component_names) != len(payload.component_tools):
            raise AppError(422, "invalid_mcp_components", "组合工具不能重复选择同一个依赖工具")
        unknown = [name for name in component_names if name not in MCP_TOOL_SPECS]
        if unknown:
            raise AppError(
                422,
                "invalid_mcp_components",
                f"组合工具只能依赖系统内置工具：{', '.join(unknown)}",
            )

        domains: list[str] = []
        parameters: dict[str, dict[str, Any]] = {}
        for name in component_names:
            spec = MCP_TOOL_SPECS[name]
            for domain in spec.domains:
                if domain not in domains:
                    domains.append(domain)
            for parameter, schema in spec.parameters.items():
                existing = parameters.get(parameter)
                if existing is not None and existing != schema:
                    raise AppError(
                        422,
                        "incompatible_mcp_parameters",
                        f"依赖工具的参数定义冲突：{parameter}",
                    )
                parameters[parameter] = schema

        definition = McpToolDefinition(
            enterprise_id=principal.enterprise_id,
            tool_name=payload.tool_name,
            display_name=payload.display_name.strip(),
            description=payload.description.strip(),
            category=payload.category.strip(),
            tool_type="composite",
            component_tools_json=component_names,
            domains_json=domains,
            parameters_json=parameters,
            version=1,
            created_by_user_id=principal.user.id,
            updated_by_user_id=principal.user.id,
        )
        config = McpToolConfig(
            enterprise_id=principal.enterprise_id,
            tool_name=payload.tool_name,
            display_name=payload.display_name.strip(),
            description=payload.description.strip(),
            is_enabled=False,
            planner_enabled=False,
            timeout_seconds=min(
                60,
                max(MCP_TOOL_SPECS[name].default_timeout_seconds for name in component_names) + 5,
            ),
            max_rows=min(MCP_TOOL_SPECS[name].default_limit for name in component_names),
            operator_note=payload.operator_note,
            updated_by_user_id=principal.user.id,
        )
        self._session.add_all([definition, config])
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise AppError(409, "mcp_tool_name_conflict", "工具标识已经存在") from exc
        await record_audit(
            self._session,
            request,
            "admin.mcp_tool_created",
            actor=principal.user,
            session=principal.session,
            target_type="mcp_tool",
            target_id=payload.tool_name,
            metadata={"tool_type": "composite", "component_tools": component_names},
        )
        await self._session.commit()
        catalog = await self._catalog(principal)
        return next(
            item for item in catalog.tools if item.tool_name == payload.tool_name
        )

    async def update_mcp_tool(
        self,
        tool_name: str,
        payload: McpToolUpdate,
        principal: Principal,
        request: Request,
    ) -> McpToolOut:
        spec = await run_in_threadpool(
            registered_spec, self._session, principal.enterprise_id, tool_name
        )
        if spec is None:
            raise AppError(404, "mcp_tool_not_found", "MCP 工具不存在")
        changes = payload.model_dump(exclude_unset=True)
        if changes.get("is_enabled") is False:
            changes["planner_enabled"] = False
        row = await self._session.scalar(
            select(McpToolConfig).where(
                McpToolConfig.enterprise_id == principal.enterprise_id,
                McpToolConfig.tool_name == tool_name,
            )
        )
        if row is None:
            row = McpToolConfig(
                enterprise_id=principal.enterprise_id,
                tool_name=tool_name,
                display_name=spec.display_name,
                description=spec.description,
                is_enabled=True,
                planner_enabled=True,
                timeout_seconds=spec.default_timeout_seconds,
                max_rows=spec.default_limit,
            )
            self._session.add(row)
        for key, value in changes.items():
            setattr(row, key, value)
        row.updated_by_user_id = principal.user.id
        await record_audit(
            self._session,
            request,
            "admin.mcp_tool_updated",
            actor=principal.user,
            session=principal.session,
            target_type="mcp_tool",
            target_id=tool_name,
            metadata={"fields": sorted(changes)},
        )
        await self._session.commit()
        catalog = await self._catalog(principal)
        return next(
            item for item in catalog.tools if item.tool_name == tool_name
        )

    async def validate_mcp_tool(
        self,
        tool_name: str,
        principal: Principal,
        request: Request,
    ) -> McpToolValidationOut:
        if (
            await run_in_threadpool(
                registered_spec, self._session, principal.enterprise_id, tool_name
            )
            is None
        ):
            raise AppError(404, "mcp_tool_not_found", "MCP 工具不存在")
        catalog = await self._catalog(principal)
        tool = next(
            item for item in catalog.tools if item.tool_name == tool_name
        )
        ready = tool.readiness == "ready"
        await record_audit(
            self._session,
            request,
            "admin.mcp_tool_validated",
            actor=principal.user,
            session=principal.session,
            target_type="mcp_tool",
            target_id=tool_name,
            outcome="success" if ready else "failure",
            failure_reason_code=None if ready else "mcp_tool_not_ready",
            metadata={"issues": tool.readiness_issues},
        )
        await self._session.commit()
        return McpToolValidationOut(tool=tool, ready=ready, issues=tool.readiness_issues)
