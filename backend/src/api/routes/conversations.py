from __future__ import annotations

import copy
import json
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from api.deps import (
    ConversationServiceDep,
    ExecutivePrincipalDep,
    HermesClientDep,
    SettingsDep,
    SkillServiceDep,
)
from schemas import (
    ClarificationOut,
    ClarificationResolve,
    ConversationCreate,
    ConversationOut,
    ConversationProjectUpdate,
    ConversationUpdate,
    DiagnosticShareOut,
    MessageCreate,
    MessageEvidenceOut,
    MessageOut,
    Page,
)
from services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=Page)
async def list_conversations(
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    project_id: uuid.UUID | None = None,
    placement: Literal["unassigned", "project", "all"] = "all",
    include_archived: bool = False,
) -> Page:
    return await service.list_conversations(
        principal,
        cursor=cursor,
        limit=limit,
        project_id=project_id,
        placement=placement,
        include_archived=include_archived,
    )


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
):
    result = await service.create_conversation(payload, request, principal)
    if isinstance(result, tuple):
        return JSONResponse(status_code=result[0], content=result[1])
    return result


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: uuid.UUID,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
) -> ConversationOut:
    return await service.get_conversation(principal, conversation_id)


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
) -> ConversationOut:
    return await service.update_conversation(conversation_id, payload, request, principal)


@router.patch("/{conversation_id}/project", response_model=ConversationOut)
async def update_conversation_project(
    conversation_id: uuid.UUID,
    payload: ConversationProjectUpdate,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
) -> ConversationOut:
    return await service.update_conversation_project(
        conversation_id, payload, request, principal
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_conversation(
    conversation_id: uuid.UUID,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
):
    await service.archive_conversation(conversation_id, request, principal)


@router.post("/{conversation_id}/pin", response_model=ConversationOut)
async def pin_conversation(
    conversation_id: uuid.UUID,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
) -> ConversationOut:
    return await service.pin_conversation(conversation_id, request, principal)


@router.delete("/{conversation_id}/pin", response_model=ConversationOut)
async def unpin_conversation(
    conversation_id: uuid.UUID,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
) -> ConversationOut:
    return await service.unpin_conversation(conversation_id, request, principal)


@router.get("/{conversation_id}/messages", response_model=Page)
async def list_messages(
    conversation_id: uuid.UUID,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
    after_sequence: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> Page:
    return await service.list_messages(
        principal,
        conversation_id,
        after_sequence=after_sequence,
        limit=limit,
    )


@router.get(
    "/{conversation_id}/messages/{message_id}",
    response_model=MessageOut,
    summary="获取单条消息（轻量 polling）",
)
async def get_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
) -> MessageOut:
    return await service.get_message(principal, conversation_id, message_id)


@router.post(
    "/{conversation_id}/clarifications/{clarification_id}",
    response_model=ClarificationOut,
)
async def resolve_clarification(
    conversation_id: uuid.UUID,
    clarification_id: uuid.UUID,
    payload: ClarificationResolve,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
) -> ClarificationOut:
    return await service.resolve_clarification(
        conversation_id, clarification_id, payload, request, principal
    )


@router.get(
    "/{conversation_id}/messages/{message_id}/evidence",
    response_model=list[MessageEvidenceOut],
)
async def get_message_evidence(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
) -> list[MessageEvidenceOut]:
    return await service.get_message_evidence(principal, conversation_id, message_id)


@router.post(
    "/{conversation_id}/messages",
    status_code=status.HTTP_200_OK,
)
async def create_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
    hermes_client: HermesClientDep,
    skill_service: SkillServiceDep,
    settings: SettingsDep,
) -> StreamingResponse:
    # 1. 创建 user message（落库）— service 返回 user_message + 上下文消息 + LLM 配置 + harness prompt + scope
    user_msg, context_messages, conv, llm_config, harness_prompt, scope_snapshot_for_llm = await service.prepare_message(
        conversation_id, payload, request, principal
    )
    system_prompt, harness_marker = harness_prompt

    # 2. 构造 worker 请求
    # 按 settings 截断历史：保留最后 N+1 条（N 条历史 + 本轮 user）。
    # context_messages 已按 sequence 升序，最后一条即本轮 user。
    # 截断在 API 侧完成，避免 worker 与 hermes 处理超大 messages 数组。
    max_msgs = settings.conversation_history_max_messages
    if max_msgs > 0 and len(context_messages) > max_msgs + 1:
        context_messages = context_messages[-(max_msgs + 1):]
    messages_for_worker = [
        {"role": m.role, "content": m.content} for m in context_messages
    ]

    # 查询已启用的 skill slugs，注入 worker 供 hermes-agent 加载
    enabled_skill_slugs = await skill_service.list_enabled_slugs()


    # 3. 返回 SSE 流
    async def event_stream():
        full_content: list[str] = []
        # 收集一轮 assistant turn 中所有工具调用，供 ``done`` 事件带回给
        # 前端、并写入 ``content_json``，刷新会话后还能复现 tool 活动。
        tool_steps: list[dict[str, Any]] = []
        try:
            async for event in hermes_client.stream_chat(
                conversation_id=str(conversation_id),
                messages=messages_for_worker,
                base_url=llm_config["base_url"],
                api_key=llm_config["api_key"],
                provider=llm_config.get("provider", "openai"),
                api_mode=llm_config.get("api_mode", "chat_completions"),
                model=llm_config["model"],
                enterprise_id=str(principal.enterprise_id),
                system_prompt=system_prompt,
                skills=enabled_skill_slugs,
                organization_scope=scope_snapshot_for_llm,
            ):
                if event.type == "delta":
                    full_content.append(event.content)
                    yield (
                        "data: "
                        + json.dumps(
                            {"type": "delta", "content": event.content},
                            ensure_ascii=False,
                        )
                        + "\n\n"
                    )
                elif event.type == "tool_start":
                    tool_steps.append(
                        {
                            "name": event.tool or "工具调用",
                            "status": "running",
                            "args": event.args or {},
                        }
                    )
                    yield (
                        "data: "
                        + json.dumps(
                            {
                                "type": "tool_start",
                                "tool": event.tool,
                                "args": event.args or {},
                            },
                            ensure_ascii=False,
                        )
                        + "\n\n"
                    )
                elif event.type == "tool_complete":
                    step = next(
                        (
                            s
                            for s in tool_steps
                            if (s.get("name") == event.tool) and s.get("status") == "running"
                        ),
                        None,
                    )
                    if step is not None:
                        step["status"] = "done"
                        if event.result is not None:
                            step["result"] = (
                                event.result
                                if isinstance(event.result, str)
                                else json.dumps(event.result, ensure_ascii=False)
                            )
                    yield (
                        "data: "
                        + json.dumps(
                            {
                                "type": "tool_complete",
                                "tool": event.tool,
                                "result": event.result,
                            },
                            ensure_ascii=False,
                        )
                        + "\n\n"
                    )
                elif event.type in (
                    "turn_start",
                    "turn_end",
                    "step",
                    "thinking",
                    "interim_assistant",
                    "status",
                ):
                    # 阶段事件：直接透传 type / content / data 给前端
                    payload: dict[str, Any] = {"type": event.type}
                    if event.content:
                        payload["content"] = event.content
                    if event.data is not None:
                        payload["data"] = event.data
                    yield (
                        "data: "
                        + json.dumps(payload, ensure_ascii=False)
                        + "\n\n"
                    )
                elif event.type == "done":
                    # 写 assistant message（一次落库）；把本轮 tool_steps 也写进
                    # ``content_json``，避免刷新会话后丢失工具调用轨迹。
                    content = event.content or "".join(full_content)
                    content_json = {
                        "tool_steps": [copy.deepcopy(step) for step in tool_steps],
                    }
                    assistant_msg = await service.save_assistant_message(
                        conversation_id,
                        content,
                        request,
                        principal,
                        content_json=content_json,
                    )
                    yield (
                        "data: "
                        + json.dumps(
                            {
                                "type": "done",
                                "message_id": str(assistant_msg.id),
                                "content": content,
                                "tool_steps": tool_steps,
                            },
                            ensure_ascii=False,
                        )
                        + "\n\n"
                    )
                elif event.type == "error":
                    yield (
                        "data: "
                        + json.dumps(
                            {"type": "error", "error": event.error},
                            ensure_ascii=False,
                        )
                        + "\n\n"
                    )
        except Exception as e:
            yield (
                "data: "
                + json.dumps({"type": "error", "error": str(e)}, ensure_ascii=False)
                + "\n\n"
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/{conversation_id}/messages/{message_id}/diagnostic-share",
    response_model=DiagnosticShareOut,
)
async def share_message_diagnostic(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
) -> DiagnosticShareOut:
    return await service.share_message_diagnostic(
        conversation_id, message_id, request, principal
    )


@router.delete(
    "/{conversation_id}/messages/{message_id}/diagnostic-share",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_message_diagnostic(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    request: Request,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
):
    await service.revoke_message_diagnostic(
        conversation_id, message_id, request, principal
    )
