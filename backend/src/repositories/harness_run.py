"""MessageRoute / HarnessStageRun 写入封装。

供 ``conversation_service._run_pipeline`` 在 route / rewrite / chat 各阶段
落库追踪数据。失败时仅记录日志，不阻断对话流程——调用方负责 try/except。
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.security import utc_now
from models import HarnessStageRun, MessageRoute

logger = logging.getLogger(__name__)


async def record_message_route(
    db: AsyncSession,
    *,
    message_id: uuid.UUID,
    conversation_id: uuid.UUID,
    enterprise_id: uuid.UUID,
    route: str,
    route_source: str,
    matched_rule_id: str | None,
    confidence: float,
    rewritten_query: str,
    query_spec_json: dict[str, Any],
    harness_version_id: uuid.UUID | None,
    scope_status: str,
    model_name: str | None,
    profile: str = "chat_pipeline_b",
    rationale: str | None = None,
) -> MessageRoute | None:
    """写一条 ``MessageRoute``。失败返回 None，不抛异常。"""
    try:
        row = MessageRoute(
            message_id=message_id,
            conversation_id=conversation_id,
            enterprise_id=enterprise_id,
            route=route,
            profile=profile,
            confidence=confidence,
            rewritten_query=rewritten_query,
            query_spec_json=query_spec_json or {},
            harness_version_id=harness_version_id,
            route_source=route_source,
            matched_rule_id=matched_rule_id,
            scope_status=scope_status,
            rationale=rationale,
            model_name=model_name,
            completed_at=utc_now(),
        )
        db.add(row)
        await db.flush()
        return row
    except Exception:  # noqa: BLE001
        logger.exception(
            "record_message_route_failed message_id=%s route=%s",
            message_id,
            route,
        )
        return None


async def record_stage_run(
    db: AsyncSession,
    *,
    enterprise_id: uuid.UUID,
    message_id: uuid.UUID,
    harness_version_id: uuid.UUID | None,
    stage: str,
    status: str,
    route_source: str | None = None,
    model_name: str | None = None,
    latency_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    tool_names: list[str] | None = None,
    summary: dict[str, Any] | None = None,
    error_code: str | None = None,
) -> HarnessStageRun | None:
    """写一条 ``HarnessStageRun``。失败返回 None，不抛异常。"""
    try:
        row = HarnessStageRun(
            enterprise_id=enterprise_id,
            message_id=message_id,
            harness_version_id=harness_version_id,
            stage=stage,
            status=status,
            route_source=route_source,
            model_name=model_name,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            tool_names_json=tool_names or [],
            summary_json=summary or {},
            error_code=error_code,
        )
        db.add(row)
        await db.flush()
        return row
    except Exception:  # noqa: BLE001
        logger.exception(
            "record_stage_run_failed message_id=%s stage=%s",
            message_id,
            stage,
        )
        return None
