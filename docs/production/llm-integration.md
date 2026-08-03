# LLM 接入 — Anspire 网关 / Hermes 代理

> 状态:已实施骨架 (P-01 / P-02),真实生产凭证待补
> 负责模块:``backend/src/services/hermes_client.py``

## 概述

``hermes_client.fetch_completion`` 同步返回 LLM 完成结果。当前实现走 ``fallback_dummy`` 模式(直接 echo prompt 长度),不接外部网关。

## 模型白名单

``MODEL_WHITELIST`` (30+ 模型),调用方传入的 model 不在白名单中时返回错误:

- qwen3-32b / qwen3-8b / qwen3-72b
- doubao-pro-32k / doubao-pro-128k
- gpt-4o / gpt-4o-mini / gpt-5
- claude-sonnet-4 / claude-opus-4
- gemini-2.5-pro / gemini-2.5-flash
- open-gateway://qwen-max / qwen-plus / ernie-4.5 / hunyuan-pro / spark-pro
- local-llama-3.3-70b / local-mistral-large-2 / local-phi-4 / local-command-r-plus
- internal-mock

## 环境变量

| 名称 | 必填 | 描述 |
|---|---|---|
| ``ANSPIRE_GATEWAY_URL`` | 否 | 网关基础 URL;空白时走 fallback |
| ``ANSPIRE_GATEWAY_KEY`` | 否 | API key |
| ``ANSPIRE_GATEWAY_HMAC_SECRET`` | 否 | HMAC 签名密钥 |

## 接入流程 (P-21 后续)

1. ``fetch_completion`` 检测 ``ANSPIRE_GATEWAY_URL`` 是否配置
2. 用 HMAC-SHA256 签请求头部 (timestamp + body digest + path)
3. POST 到 ``{ANSPIRE_GATEWAY_URL}/v1/chat/completions``
4. 失败重试 3 次 (指数回退)
5. 5xx 错误 → ``AppError(503, "llm_unavailable", ...)``

## 流式回答 (P-04)

``fetch_streaming`` 接受 ``on_token`` 回调,按 token 切分文本推送:

- token 切分:按空白
- 失败:抛 ``AppError``
- 上层 caller (orchestrator) 把 token 包装成 ``event: token`` 推 SSE
