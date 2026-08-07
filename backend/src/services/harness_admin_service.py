"""Harness admin service.

``HarnessAdminService(db, settings)`` 暴露所有 harness 相关业务方法；
``/admin/harness`` 路由只做参数解析与响应包装。
"""
from __future__ import annotations

import math
import uuid
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import Settings
from core.security import utc_now
from exceptions.errors import AppError
from models import (
    HarnessConfigVersion,
    HarnessDiagnosticGrant,
    HarnessStageRun,
    Message,
    MessageRoute,
    OrganizationUnit,
)
from repositories import conversation as conversation_repo
from repositories import model_provider_config as model_config_repo
from repositories.audit import record_audit
from schemas import (
    HarnessConfigOut,
    HarnessConfigUpdate,
    HarnessMetricsOut,
    HarnessSimulationOut,
    HarnessSimulationRequest,
    HarnessTraceOut,
    HarnessVersionOut,
    OrganizationScopeInput,
)
from services.anspire import AnspireConfigurationError, runtime_provider_config
from services.authz import Principal
from services.hermes_client import HermesClient, HermesStreamEvent
from services.harness_config import (
    HARNESS_SCHEMA_VERSION,
    MCP_V2_TOOLS,
    SAFETY_KERNEL_SUMMARY,
    active_harness_config,
    apply_glossary,
    config_hash,
    match_fast_rule,
    next_harness_version,
    validate_harness_config,
)
from services.query_spec import normalize_query_spec


def _parse_json_response(text: str) -> dict:
    """Strip Markdown code fences / surrounding prose and parse JSON."""
    import json
    import re

    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned, re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    cleaned = cleaned.strip("`")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # 最后一道 fallback：尝试抽取 "{...}" 第一段
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            return json.loads(match.group(0))
        raise


def _p95(values: list[int]) -> int:
    """Compute the 95th percentile latency (ms) for a list of values."""
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


def _query_spec_summary(route: MessageRoute | None) -> dict[str, Any]:
    """Summarize the query spec attached to a route for trace output."""
    spec = route.query_spec_json if route else {}
    return {
        "metric_count": len(spec.get("metrics", [])),
        "analysis_goal_count": len(spec.get("analysis_goals", [])),
        "entity_types": sorted(spec.get("entities", {}).keys())[:12],
        "has_time_range": bool(spec.get("time_range")),
        "filter_count": len(spec.get("filters", [])),
        "ambiguity_count": len(spec.get("unresolved_ambiguities", [])),
    }


class HarnessAdminService:
    """Service for the admin harness endpoints.

    Mirrors the anspire ``Service`` convention: stateless business logic
    layered on top of a SQLAlchemy ``AsyncSession``. ``Settings`` is required
    for simulation endpoints that invoke the hermes runtime.
    """

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _config_out(row: HarnessConfigVersion) -> HarnessConfigOut:
        return HarnessConfigOut(
            id=row.id,
            version=row.version,
            schema_version=row.schema_version,
            config_hash=row.config_hash,
            config=row.config_json,
            safety_kernel=SAFETY_KERNEL_SUMMARY,
            activated_at=row.activated_at,
            updated_at=row.updated_at,
        )

    async def _simulation_scope(
        self,
        enterprise_id: uuid.UUID,
        raw_scope: dict[str, Any] | None,
    ) -> tuple[OrganizationScopeInput, list[uuid.UUID]]:
        available = set(
            (
                await self._session.scalars(
                    select(OrganizationUnit.id).where(
                        OrganizationUnit.enterprise_id == enterprise_id,
                        OrganizationUnit.is_active.is_(True),
                        OrganizationUnit.enabled_for_analysis.is_(True),
                    )
                )
            ).all()
        )
        scope = (
            OrganizationScopeInput.model_validate(raw_scope)
            if raw_scope
            else OrganizationScopeInput(mode="all_authorized", organization_unit_ids=[])
        )
        if scope.mode == "selected":
            selected = set(scope.organization_unit_ids)
            if not selected.issubset(available):
                raise AppError(422, "invalid_organization_scope", "模拟范围包含不可分析的事业部")
            return scope, sorted(selected, key=str)
        return scope, sorted(available, key=str)

    async def _trace_out(
        self,
        principal: Principal,
        route: MessageRoute,
    ) -> HarnessTraceOut:
        db = self._session
        stages = (
            await db.scalars(
                select(HarnessStageRun)
                .where(HarnessStageRun.message_id == route.message_id)
                .order_by(HarnessStageRun.created_at, HarnessStageRun.id)
            )
        ).all()
        version = (
            await db.get(HarnessConfigVersion, route.harness_version_id)
            if route.harness_version_id
            else None
        )
        question = await db.get(Message, route.message_id)
        answer = await db.scalar(
            select(Message)
            .where(
                Message.conversation_id == route.conversation_id,
                Message.role == "assistant",
                Message.sequence > (question.sequence if question else -1),
            )
            .order_by(Message.sequence)
            .limit(1)
        )
        grant = await db.scalar(
            select(HarnessDiagnosticGrant).where(
                HarnessDiagnosticGrant.message_id == (answer.id if answer else route.message_id),
                HarnessDiagnosticGrant.enterprise_id == principal.enterprise_id,
                HarnessDiagnosticGrant.revoked_at.is_(None),
                HarnessDiagnosticGrant.expires_at > utc_now(),
            )
        )
        shared_content = None
        if grant:
            shared_content = {
                "question": question.content if question else None,
                "rewritten_query": route.rewritten_query,
                "query_spec": route.query_spec_json,
                "plan": (answer.content_json or {}).get("execution_plan") if answer else None,
                "answer": answer.content if answer else None,
            }
        tools = sorted({name for stage in stages for name in stage.tool_names_json})
        organization_count = max(
            [int(stage.summary_json.get("organization_unit_count", 0)) for stage in stages] or [0]
        )
        return HarnessTraceOut(
            message_id=answer.id if answer else route.message_id,
            conversation_id=route.conversation_id,
            route=route.route,
            route_source=route.route_source,
            query_spec_summary=_query_spec_summary(route),
            harness_version=version.version if version else None,
            organization_unit_count=organization_count,
            tools=tools,
            stages=[
                {
                    "stage": row.stage,
                    "status": row.status,
                    "model_name": row.model_name,
                    "latency_ms": row.latency_ms,
                    "input_tokens": row.input_tokens,
                    "output_tokens": row.output_tokens,
                    "tool_names": row.tool_names_json,
                    "summary": row.summary_json,
                    "error_code": row.error_code,
                    "created_at": row.created_at,
                }
                for row in stages
            ],
            diagnostic_shared_until=grant.expires_at if grant else None,
            shared_content=shared_content,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def get_harness_config(self, principal: Principal) -> HarnessConfigOut:
        row = await active_harness_config(self._session, principal.enterprise_id)
        await self._session.commit()
        return self._config_out(row)

    async def update_harness_config(
        self,
        payload: HarnessConfigUpdate,
        principal: Principal,
        request: Request,
    ) -> HarnessConfigOut:
        db = self._session
        # MCP v2 后，``candidate_tools`` 只接受 {discover_schema, query_schema,
        # execute_query} 这套通用工具名；validate_harness_config 的默认
        # ``allowed_tools`` 已经覆盖。
        clean = validate_harness_config(payload.config)
        current = await db.scalar(
            select(HarnessConfigVersion)
            .where(
                HarnessConfigVersion.enterprise_id == principal.enterprise_id,
                HarnessConfigVersion.is_active.is_(True),
            )
            .with_for_update()
        )
        if current is None:
            current = await active_harness_config(db, principal.enterprise_id)
        if current.version != payload.base_version:
            raise AppError(
                409,
                "harness_version_conflict",
                "编排策略已被其他管理员更新，请刷新后重试",
                {"current_version": current.version},
            )
        current.is_active = False
        row = HarnessConfigVersion(
            enterprise_id=principal.enterprise_id,
            version=await next_harness_version(db, principal.enterprise_id),
            schema_version=HARNESS_SCHEMA_VERSION,
            config_json=clean,
            config_hash=config_hash(clean),
            is_active=True,
            source_version_id=current.id,
            created_by_user_id=principal.user.id,
            activated_at=utc_now(),
        )
        db.add(row)
        await db.flush()
        await record_audit(
            db,
            request,
            "admin.harness_config_updated",
            actor=principal.user,
            session=principal.session,
            target_type="harness_config_version",
            target_id=row.id,
            metadata={
                "previous_version": current.version,
                "version": row.version,
                "config_hash": row.config_hash,
            },
        )
        await db.commit()
        await db.refresh(row)
        return self._config_out(row)

    async def list_harness_versions(
        self,
        principal: Principal,
        limit: int,
    ) -> list[HarnessVersionOut]:
        rows = (
            await self._session.scalars(
                select(HarnessConfigVersion)
                .where(HarnessConfigVersion.enterprise_id == principal.enterprise_id)
                .order_by(HarnessConfigVersion.version.desc())
                .limit(limit)
            )
        ).all()
        return [HarnessVersionOut.model_validate(row, from_attributes=True) for row in rows]

    async def restore_harness_version(
        self,
        version_id: uuid.UUID,
        principal: Principal,
        request: Request,
    ) -> HarnessConfigOut:
        db = self._session
        source = await db.scalar(
            select(HarnessConfigVersion).where(
                HarnessConfigVersion.id == version_id,
                HarnessConfigVersion.enterprise_id == principal.enterprise_id,
            )
        )
        if source is None:
            raise AppError(404, "harness_version_not_found", "编排版本不存在")
        current = await db.scalar(
            select(HarnessConfigVersion)
            .where(
                HarnessConfigVersion.enterprise_id == principal.enterprise_id,
                HarnessConfigVersion.is_active.is_(True),
            )
            .with_for_update()
        )
        if current:
            current.is_active = False
        clean = validate_harness_config(source.config_json)
        row = HarnessConfigVersion(
            enterprise_id=principal.enterprise_id,
            version=await next_harness_version(db, principal.enterprise_id),
            schema_version=HARNESS_SCHEMA_VERSION,
            config_json=clean,
            config_hash=config_hash(clean),
            is_active=True,
            source_version_id=source.id,
            created_by_user_id=principal.user.id,
            activated_at=utc_now(),
        )
        db.add(row)
        await db.flush()
        await record_audit(
            db,
            request,
            "admin.harness_version_restored",
            actor=principal.user,
            session=principal.session,
            target_type="harness_config_version",
            target_id=row.id,
            metadata={"restored_from": source.version, "new_version": row.version},
        )
        await db.commit()
        await db.refresh(row)
        return self._config_out(row)

    async def simulate_harness(
        self,
        payload: HarnessSimulationRequest,
        principal: Principal,
        request: Request,
    ) -> HarnessSimulationOut:
        db = self._session
        settings = self._settings
        current = await active_harness_config(db, principal.enterprise_id)
        config = validate_harness_config(payload.config or current.config_json)
        scope, resolved_ids = await self._simulation_scope(
            principal.enterprise_id, payload.organization_scope
        )
        rule = match_fast_rule(payload.question, config)
        route = str(rule["route"]) if rule else ""
        route_source = "fast_rule" if rule else "hermes"
        model_config = await model_config_repo.find_active(db, principal.enterprise_id)
        if model_config is None:
            raise AppError(409, "anspire_not_configured", "请先配置并启用 Anspire 模型")
        hermes_client = HermesClient(settings)
        try:
            provider = runtime_provider_config(model_config, settings)
            if not route:
                response = await hermes_client.run_profile(
                    profile="route",
                    payload={
                        "question": payload.question,
                        "harness_config": config,
                        "organization_count": len(resolved_ids),
                    },
                    base_url=provider["endpoint_url"],
                    api_key=provider["api_key"],
                    model_id=provider["model_id"],
                )
                route_data = _parse_json_response(response["text"])
                route = str(route_data.get("route") or "clarification")
            if route not in {"data", "general", "clarification"}:
                route = "clarification"
                route_source = "validation"
            query_spec: dict[str, Any] = {}
            if route == "data":
                rewritten_question = apply_glossary(payload.question, config)
                response = await hermes_client.run_profile(
                    profile="rewrite",
                    payload={
                        "question": rewritten_question,
                        "harness_config": config,
                        "organization_scope": {
                            "mode": scope.mode,
                            "organization_unit_ids": [str(item) for item in resolved_ids],
                        },
                    },
                    base_url=provider["endpoint_url"],
                    api_key=provider["api_key"],
                    model_id=provider["model_id"],
                )
                rewrite_data = _parse_json_response(response["text"])
                query_spec = normalize_query_spec(
                    rewrite_data,
                    question=rewritten_question,
                    organization_scope={
                        "mode": scope.mode,
                        "organization_unit_ids": [str(item) for item in resolved_ids],
                    },
                )
        except AnspireConfigurationError as exc:
            raise AppError(422, exc.code, str(exc)) from exc
        except RuntimeError as exc:
            raise AppError(422, "harness_simulation_failed", str(exc)) from exc

        # MCP v2 的 3 个通用工具始终启用；先前通过 ``effective_catalog`` 过滤
        # ``is_enabled`` / ``planner_enabled`` 标志的逻辑不再适用。
        planner_tools = set(MCP_V2_TOOLS)
        candidate_tools = [
            name for name in (rule or {}).get("candidate_tools", []) if name in planner_tools
        ]
        issues = list(query_spec.get("unresolved_ambiguities", []))
        await record_audit(
            db,
            request,
            "admin.harness_simulated",
            actor=principal.user,
            session=principal.session,
            target_type="harness_config_version",
            target_id=current.id,
            metadata={
                "route": route,
                "route_source": route_source,
                "scope_count": len(resolved_ids),
                "config_hash": config_hash(config),
            },
        )
        await db.commit()
        return HarnessSimulationOut(
            route=route,
            route_source=route_source,
            matched_rule_id=str(rule["id"]) if rule else None,
            candidate_tools=candidate_tools,
            query_spec=query_spec,
            validation_issues=issues,
            config_hash=config_hash(config),
        )

    async def harness_metrics(
        self,
        principal: Principal,
        days: int,
    ) -> HarnessMetricsOut:
        db = self._session
        cutoff = utc_now() - timedelta(days=days)
        # ``conversation_repo.list_ids_by_enterprise`` returns a select object
        # (no DB round-trip); it can be called synchronously even on an
        # AsyncSession. We feed it as a subquery to ``in_()`` below.
        routes = (
            await db.scalars(
                select(MessageRoute).where(
                    MessageRoute.created_at >= cutoff,
                    MessageRoute.conversation_id.in_(
                        conversation_repo.list_ids_by_enterprise(
                            db, principal.enterprise_id
                        )
                    ),
                )
            )
        ).all()
        stages = (
            await db.scalars(
                select(HarnessStageRun).where(
                    HarnessStageRun.enterprise_id == principal.enterprise_id,
                    HarnessStageRun.created_at >= cutoff,
                )
            )
        ).all()
        stage_latencies: dict[str, list[int]] = defaultdict(list)
        for row in stages:
            if row.latency_ms is not None:
                stage_latencies[row.stage].append(row.latency_ms)
        execution = [row for row in stages if row.stage == "mcp_execution"]
        return HarnessMetricsOut(
            window_days=days,
            message_count=len(routes),
            intent_accuracy_sample_size=0,
            structured_output_rate=(
                sum(bool(row.query_spec_json) or row.route == "general" for row in routes)
                / len(routes)
                if routes
                else 0.0
            ),
            tool_success_rate=(
                sum(row.status == "completed" for row in execution) / len(execution)
                if execution
                else 0.0
            ),
            route_counts=dict(Counter(row.route for row in routes)),
            stage_latency_p95_ms={
                stage: _p95(values) for stage, values in stage_latencies.items()
            },
        )

    async def list_harness_traces(
        self,
        principal: Principal,
        limit: int,
    ) -> list[HarnessTraceOut]:
        db = self._session
        rows = (
            await db.scalars(
                select(MessageRoute)
                .where(
                    MessageRoute.conversation_id.in_(
                        conversation_repo.list_ids_by_enterprise(
                            db, principal.enterprise_id
                        )
                    )
                )
                .order_by(MessageRoute.created_at.desc())
                .limit(limit)
            )
        ).all()
        return [await self._trace_out(principal, row) for row in rows]

    async def get_harness_trace(
        self,
        message_id: uuid.UUID,
        principal: Principal,
    ) -> HarnessTraceOut:
        db = self._session
        message = await db.scalar(
            select(Message).where(
                Message.id == message_id,
                Message.conversation_id.in_(
                    conversation_repo.list_ids_by_enterprise(
                        db, principal.enterprise_id
                    )
                ),
            )
        )
        route_message_id = message_id
        if message and message.role == "assistant":
            route_message_id = await db.scalar(
                select(Message.id)
                .where(
                    Message.conversation_id == message.conversation_id,
                    Message.role == "user",
                    Message.sequence < message.sequence,
                )
                .order_by(Message.sequence.desc())
                .limit(1)
            ) or message_id
        route = await db.scalar(
            select(MessageRoute).where(
                MessageRoute.message_id == route_message_id,
                MessageRoute.conversation_id.in_(
                    conversation_repo.list_ids_by_enterprise(
                        db, principal.enterprise_id
                    )
                ),
            )
        )
        if route is None:
            raise AppError(404, "harness_trace_not_found", "编排追踪不存在")
        return await self._trace_out(principal, route)
