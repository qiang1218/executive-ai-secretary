# MCP 工具 / Orchestrator / Hermes 网关架构

> 状态:已实施 (P-15 / P-16 / P-03 / P-01 / P-02)
> 负责模块:
> - ``backend/src/core/mcp_registry.py`` (MCP 工具注册表)
> - ``backend/src/services/business_tools.py`` (业务工具实现)
> - ``backend/src/api/routers/mcp.py`` (``/v1/tools`` & ``/v1/tools/call``)
> - ``backend/src/services/hermes_client.py`` (Hermes / Anspire 网关代理)
> - ``backend/src/worker/assistant_orchestrator.py`` (7 阶段流水线)
> - ``backend/src/schemas/answer_contract.py`` + ``services/answer_contract.py`` (5 套答案契约)

## 设计

**核心原则**(与 ``new`` 包的差异标注):
- **以后端实现为准**:能力白名单 / 审计链 / 加密 / 密钥轮换 已在 current backend 实现,不从 new 复制
- **加功能不改变目录结构**:MCP / Hermes / Orchestrator 全部嵌入已有目录
- **可独立测试**:业务工具 + 答案契约 + orchestrator 都用纯 Python,无 FastAPI 依赖

## 7 阶段流水线

```
[user prompt] → scope_validate → route → rewrite → plan → mcp_execution → repair → answer
```

- **scope_validate**:确认 prompt 不空 + 命中主体的事业部授权
- **route**:根据关键词路由到 ``executive_pulse / data_answer / forecast_delta / operational_pulse / general_answer`` 5 套契约
- **rewrite**:扩展为完整 query (P-21 后续接入)
- **plan**:分析需要的 MCP 工具 (P-21 后续接入)
- **mcp_execution**:派发到 ``core.mcp_registry.invoke_tool`` (已实施)
- **repair**:调用 ``services.answer_contract.validate_answer`` (已实施)
- **answer**:序列化 ``AnswerContract`` JSON 推回客户端 (P-04 SSE 接入)

## 答案契约 — 5 套模板

| 模板 | 必填字段 | 典型回答 |
|---|---|---|
| ``executive_pulse`` | ``summary``, ``cards`` | 高层经营摘要 (5 张卡) |
| ``data_answer`` | ``summary``, ``table`` | 经营数据 (DataCard + 表格) |
| ``forecast_delta`` | ``summary``, ``chart`` | 商机预测偏差 (趋势小图) |
| ``operational_pulse`` | ``summary``, ``warnings`` | 逾期 / 风险 / 处置建议 |
| ``general_answer`` | ``summary`` | 通用 |

校验规则:
- 引用 (citations) 必须以 ``ref://`` 开头
- 表格 row 长度等于列数
- summary 长度 ≤ 1500 字
- warnings ≤ 5

## Hermes 网关代理

``services/hermes_client.py::fetch_completion`` 接受 ``model`` + ``prompt``:

- 模型白名单 30+ (``MODEL_WHITELIST`` 集合)
- 当 ``settings.anspire_gateway_url`` 为空时走 ``fallback_dummy`` (echo prompt 长度)
- 真实接入 P-21 后续:HMAC 签名头部 + 速率限制 + 重试

## MCP 工具列表

``GET /api/v1/tools`` 返回 ``core.mcp_registry.list_tools()`` 全部注册的工具。

``POST /api/v1/tools/call`` 接受 ``{name, arguments}``,委派到 ``invoke_tool``。

当前 9 个示例工具(全部 demo 模式 echo):

| 工具 | scope | capability |
|---|---|---|
| ``executive_pulse`` | data | data.business |
| ``revenue_overview`` | data | data.business |
| ``operations_overview`` | data | data.business |
| ``project_overview`` | data | data.project |
| ``forecast_overview`` | data | data.forecast |
| ``search_business`` | data | data.search |
| ``search_files`` | files | files.read |
| ``public_search`` | external | external.search |
| ``ask_follow_up`` | meta | meta.basic |

## 后续任务

- P-21:plan 阶段用 ``mcp.call_tool`` 派发 + Anspire 真实调用
- P-26:答案契约 → SSE 事件流 (P-04 已实施)
