# new 与当前前后端功能对比与修复计划

> 范围
> - `new/` 是未切分前后端代码时的外部源码包，**禁止修改**，仅作参考。
> - `frontend/app/` + `backend/src/` 是当前实际生产代码。
> - 对比原则：相似功能若当前 backend 已有成熟实现，则**以后端为准**，不重复实现。

---

## 0. new 包简介

`new/` 是单体 Next.js 代码改造前的内部快照，结构如下：

```
new/
├── app/                         # Next.js 客户端（演示原型 + 生产入口）
├── services/api/                # FastAPI 后端（executive_ai_api）
├── services/worker/             # 异步 worker（assistant_orchestrator、file_extraction、scheduler）
├── services/hermes-runtime/     # LLM 代理（FastAPI :8020）
├── db/                          # 数据库定义 + 迁移
├── drizzle/                     # Drizzle（前端占位）
├── skills/                      # 工具调用 skill
├── scripts/                     # 启动 / 部署 / 运维
├── .github/workflows/           # CI
├── compose.yml / Dockerfile.web # 部署
└── docs/                        # 原始设计文档
```

后端具备的关键能力（来源 `new/services/api/`、`new/services/worker/`、`new/services/hermes-runtime/`）：

- LLM 接入层：Hermes-runtime (HMAC 签名) + Anspire 网关代理 + 30+ 模型白名单
- 助手编排：7 阶段流水线（scope_validate → route → rewrite → plan → mcp_execution → repair → answer）
- 业务工具：MCP Hub 30+ 工具（`new/services/api/.../business_tools.py`），capability token 鉴权
- 飞书源：`new/services/api/.../feishu.py` + `feishu_live.py`，含 3 张多维表 AppToken
- 源契约：V1/V3 两套 schema（`source_contract.py` / `source_contract_v3.py`）
- 数据摄入：`ingestion.py`（69KB）含原子三域激活、外部 TLS 校验
- 每日简报：`daily_brief.py` + `operating_data_v3.py`（45KB，物化 + 原子激活）
- 答案契约：`answer_contract.py` 5 套模板（executive_pulse 等）
- 调度：`scheduler.py`（pg_try_advisory_xact_lock 单实例 leader + Croniter）
- 文件提取：`file_extraction.py`（PDF/DOCX/XLSX/PPTX，chunks 1600/160）
- Embedding 缓存：`embedding_cache.py`（HTTPS 断点续传 + SHA256 校验）
- CLI 运维：`create-admin / create-user / configure-source / trigger-sync / reset-data / seed`
- 演示数据集：`demo_dataset.py`（26KB 完整事业部 + 客户 + 商机 + 交付 + 回款）

前端具备的关键能力（来源 `new/app/`）：

- 双入口：`app/page.tsx`（演示原型） + `app/page.production.tsx`（生产构建期替换）
- 生产装配：`production-app.tsx`（5 状态机：checking/error/anonymous/password-change/ready）
- 董事长工作台：`production-workspace.tsx`（侧栏 + 聊天舞台 + 详情抽屉 + 多种结构化回答渲染）
- 管理端：`production-admin.tsx`（4 大面板：模型服务 / 编排策略 / MCP 工具 / 经营数据）
- 公司网关鉴权：`app/chatgpt-auth.ts`（`getChatGPTUser` / `requireChatGPTUser`）
- 数据结构化渲染：`production/assistant-output.tsx`（DataAnswer / DataChart / AnswerTable / FileAnswer / ResearchAnswer / FollowUps / StructuredAnswer）
- 演示抽屉：10 个 `demoScenarios`、30 秒锁定、推屏预览（FeishuPreview daily + weekly）

---

## 1. 前端功能差异（以 new 为准）

### 1.1 已覆盖（一致）

| new 页面/能力 | 当前 frontend 实现 | 覆盖等级 |
|---|---|---|
| 登录页（邮箱+密码） | `production/app.tsx` → `ProductionLogin` | ✅ production |
| 首次改密（≥12 位 + 字母 + 数字） | `ProductionPasswordChange` | ✅ production |
| 会话 CRUD（列表/打开/重命名/归档/置顶） | `ProductionWorkspace` 侧栏 | ✅ production |
| 项目 CRUD（侧栏分组） | `ProductionWorkspace` 侧栏 | ✅ production |
| 文件上传/删除（PDF/DOCX/XLSX/PPTX） | `ProductionComposer` | ✅ production |
| 长期记忆 CRUD | `ProductionMemoryPanel` / `PreferencesWindow memory` | ✅ production |
| 简报查看（每日/每周） | `ProductionReportPanel` | ✅ production（仅展示） |
| 事业部范围筛选 | `OrganizationPicker` | ✅ production |
| 演示原型（demo mode） | `demo/prototype.tsx` | ✅ demo |
| 管理端（7 个 section） | `production/admin-shell.tsx` | ✅ production（4 个 section 占位） |

### 1.2 缺失（new 有，当前没有）

| 编号 | 功能 | new 来源 | 建议归属 |
|---|---|---|---|
| F-01 | **chatgpt-auth 网关**（公司 ChatGPT 网关头读取用户身份） | `new/app/chatgpt-auth.ts` | 前端 |
| F-02 | **明暗主题 + i18n**（zh-CN / zh-TW / en，localStorage 持久化） | `new/app/prototype-data.ts` + `PreferencesWindow` | 前端 |
| F-03 | **LLM 流式回答（SSE/WS）** | `new/app/production/production-workspace.tsx` | 前端 + 后端 |
| F-04 | **结构化回答渲染**（DataAnswer / DataChart / AnswerTable / FileAnswer / ResearchAnswer / FollowUps / StructuredAnswer） | `new/app/production/assistant-output.tsx` | 前端 |
| F-05 | **聊天交互**（Enter/Shift+Enter/Cmd+K 快捷键、字数阈值 8000、IME 组合态） | `new/app/production/production-workspace.tsx` | 前端 |
| F-06 | **追问 (FollowUps)** | `new/app/.../assistant-output.tsx` | 前端 |
| F-07 | **场景抽屉 DemoDrawer**（一键跑场景） | `new/app/page.tsx` | 前端（demo） |
| F-08 | **推屏预览 FeishuPreview**（daily / weekly） | `new/app/page.tsx` | 前端（demo） |
| F-09 | **演示账号 30 秒锁定** | `new/app/page.tsx` | 前端（demo） |
| F-10 | **多选事业部 picker** | `new/app/page.tsx` | 前端 |
| F-11 | **逾期 / 风险 / 处置建议卡**（OperationalPulse / ForecastDelta 等模板） | `new/app/page.tsx` + `answer_contract` | 前端 + 后端 |
| F-12 | **明暗主题切换** | `new/app/prototype-data.ts` | 前端 |
| F-13 | **生产端"报告手动重生成"按钮** | `new/app/production/production-workspace.tsx` | 前端 + 后端 |
| F-14 | **生产端 fde 专属 UI** | `new/app/production/production-admin.tsx` 4 大面板 | 前端 |
| F-15 | **数据源"新建/编辑组织单元"**（admin 已存在接口） | `new/app/production/production-admin.tsx` | 前端 |
| F-16 | **Executive 端"账号/数据范围"自查 UI** | `new/app/page.tsx` | 前端 |
| F-17 | **离线提示卡片**（OfflineMessage） | `new/app/page.tsx` | 前端 |
| F-18 | **MCP 工具调用调试 UI** | `new/app/production/production-admin.tsx` "MCP 工具" 面板 | 前端 |

### 1.3 仅占位（new 已有完整实现，当前仅前端 mock）

| 编号 | 已占位 | new 完整实现 |
|---|---|---|
| F-19 | `AdminModel`（保存只 toast） | 后端需要 `models/` 配置读取 / 切换 API |
| F-20 | `AdminFeishu`（测试发送 850ms 假延迟） | 后端需要 `feishu-test-send` / 配置接口 |
| F-21 | `AdminAutomation`（保存只 toast） | 后端需要 cron 配置读写 API |
| F-22 | `AdminCapabilities`（6 条硬编码） | 后端需要 capability registry 列表 API |
| F-23 | `AdminSource` mapping tab（首版演示 UI） | 后端需要 source_contract_v3 字段映射 API |
| F-24 | `AdminSource` sync tab（`setTimeout(950)` 假装同步） | 后端需要 `/admin/sync/trigger` 触发 API |
| F-25 | `Workspace` 偏好（主题/语言/称呼/单位 全部 localStorage） | 后端需要 `PUT /preferences` |
| F-26 | `AdminSource` simulation tab 单向只读 | 后端需要 `demo-data: enable/disable` 切换接口 |

---

## 2. 后端功能差异

### 2.1 后端已实现且优于 new（**以当前 backend 为准**）

| 能力 | new 实现 | 当前 backend 实现 | 评价 |
|---|---|---|---|
| AES-256-GCM 文件加密 | `storage.py`（EAIF1/EAIF2 magic） | `core/storage.py` + 密钥环 + Legacy EAIF1 兼容 | **当前 backend 更优**：文档化的密钥轮换 + Legacy 兼容 |
| HMAC 审计链 | `audit.py` + `audit_integrity.py`（HMAC + 序号 + 链头） | `core/audit.py` + `audit_chain_heads` 链头锚定 | **当前 backend 更优**：锚点机制 + 环境保护 |
| 密钥轮换 | `file_key_rotation.py` CLI + 全量重加密 | `core/keys.py` + 密钥环 + 备份重加密 | **当前 backend 更优**：独立 runbook（`docs/production/key-rotation.md`） |
| Capability 能力白名单 | `mcp_registry.py` + `capability HMAC token` | `core/capabilities.py` capability registry | **当前 backend 等价**：JWT 风格的 capability token 更强 |
| Session/CSRF | `authz.py`（HMAC session）+ CSRF cookie | `core/authz.py` + `core/csrf.py` | **当前 backend 等价** |
| Argon2 密码 | `authz.py`（argon2-cffi） | `core/authz.py` argon2-cffi | 等价 |
| 限流 | 登录限流 | `core/middlewares/rate_limit.py` + 登录限流 | **当前 backend 更广** |
| Idempotency | `idempotency.py` replay/save_response | `core/idempotency.py` | 等价 |
| 备份恢复 | `storage.py` + `backup.py` | `scripts/backup.py` + Ed25519 清单签名 + PBKDF2 | **当前 backend 更优**：环境独立签名密钥 |
| 数据 schema（23 张表 + 3 张迁移） | `models.py` + Alembic | `models.py` + Alembic + `audit_chain_heads` | **当前 backend 等价 + 链头表** |
| Admin API（用户/组织/审计/runtime） | `routers/admin.py` | `routers/admin.py` | 等价（路径相同） |
| Executive API（会话/项目/记忆/报告/任务） | `routers/*` | `routers/*` | 等价 |
| `PersonalCenter` preferences | `preferences` 表 + 持久化（new 完整） | ❌ 当前 backend 缺失（占位） | **当前 backend 缺失**（虽然题目要求"以后端为准"——但当前 backend 确实没实现） |

### 2.2 当前 backend 缺失（new 完整实现）

| 编号 | 能力 | new 来源 | 影响页面 |
|---|---|---|---|
| B-01 | **LLM 接入层**（Hermes-runtime + Anspire 网关 + 30+ 模型白名单） | `new/services/hermes-runtime/` + `new/services/api/.../anspire.py` + `hermes_client.py` | `production-workspace.tsx`（聊天）、`AdminModel` |
| B-02 | **assistant_orchestrator 7 阶段流水线** | `new/services/worker/.../assistant_orchestrator.py` | 全部对话路径 |
| B-03 | **MCP 工具调用层**（30+ 业务工具） | `new/services/api/.../business_tools.py` + `mcp_registry.py` | `AdminCapabilities`、对话工具调用 |
| B-04 | **源契约 V3 ingestion** | `new/services/api/.../source_contract_v3.py` + `ingestion.py` | `AdminSource`、对话数据源 |
| B-05 | **飞书数据源 ingestion** | `new/services/api/.../feishu.py` + `feishu_live.py` | `AdminSource` |
| B-06 | **飞书推送** | `new/services/api/.../feishu.py`（推送） | `AdminFeishu`、每日/每周推送 |
| B-07 | **Scheduler 调度**（pg_try_advisory_xact_lock leader 选举 + Croniter） | `new/services/worker/.../scheduler.py` | `AdminAutomation`、每日/每周任务 |
| B-08 | **文件提取**（PDF/DOCX/XLSX/PPTX，chunks 1600/160） | `new/services/worker/.../file_extraction.py` | 文件上传后端解析 |
| B-09 | **Embedding 缓存**（HTTPS 断点续传 + SHA256 校验） | `new/services/worker/.../embedding_cache.py` | 追问 / 检索增强 |
| B-10 | **每日简报生成** | `new/services/api/.../daily_brief.py` + `operating_data_v3.py` | `AdminAutomation` 推送、workspace 报告 |
| B-11 | **答案契约**（5 套模板） | `new/services/api/.../answer_contract.py` | 聊天结构化输出 |
| B-12 | **Hermes 模型白名单**（30+ 模型） | `new/services/api/.../anspire.py` | `AdminModel`、模型路由 |
| B-13 | **CLI 运维**（create-admin / create-user / configure-source / trigger-sync / reset-data / seed） | `new/services/api/.../cli.py` | 部署 / 运维 |
| B-14 | **演示数据集** | `new/services/api/.../demo_dataset.py`（26KB） | 仅 demo 模式 |
| B-15 | **MCP `execute_business_tool`** 接口 | `new/services/api/.../mcp_app.py` /v1/tools/call | MCP 工具调用 |

### 2.3 当前 backend 已有但未挂载的能力

| 能力 | 文件 | 现状 |
|---|---|---|
| `PersonalCenter` preferences | `routers/` | 仅有用户偏好接口骨架，无 `preferences` 表 + 读写 API |
| `claude_client` / `hermes_client` | `services/llm/` | 可能不存在，需要 `git ls-files backend/src/services/` 确认 |
| `JobService` 完整 send_message | `services/conversation_service.py` | `send_message` 抛 `NotImplementedError`（实际走 router） |
| `AuthService` 6 个方法 | `services/auth_service.py` | 全部 `NotImplementedError`，业务仍在 `routers/auth.py` |

---

## 3. 关键相似功能的对齐结论（按"后端为准"原则）

| 维度 | new 实现 | 当前 backend 实现 | 结论 |
|---|---|---|---|
| **审计链** | HMAC + 序号 + 链头 | HMAC + 序号 + **链头锚点 + 锚点备份** | **当前 backend 优先**（更完整） |
| **文件加密** | AES-256-GCM + EAIF1/EAIF2 magic | AES-256-GCM + 密钥环 + EAIF1 Legacy | **当前 backend 优先** |
| **密钥轮换** | CLI 一键轮换 | 文档化 runbook + 备份重加密（更安全） | **当前 backend 优先** |
| **能力白名单** | capability HMAC token | capability JWT-style token | **当前 backend 优先** |
| **Session / CSRF** | HMAC session + CSRF cookie | 等价 | **当前 backend 优先**（保留） |
| **限流** | 登录限流 | 通用 + 登录限流 | **当前 backend 优先** |
| **备份恢复** | AES-256-CBC + PBKDF2 | + Ed25519 清单签名 | **当前 backend 优先** |
| **Schema 范围** | 23 张表 | 23 张表 + 3 张迁移（链头/锚点） | **当前 backend 优先** |
| **审计 anchor** | `AuditChainHead` + `chain_scope` | `audit_chain_heads` 锚点 + 序号 | **当前 backend 优先** |
| **LLM 接入** | Hermes + Anspire | ❌ 缺失 | **必须实现**（B-01） |
| **MCP 工具** | 30+ 业务工具 | ❌ 缺失 | **必须实现**（B-03） |
| **飞书源** | FeishuBitable + LiveSnapshot | ❌ 缺失 | **必须实现**（B-05） |
| **飞书推送** | 应用凭证 + 推送 | ❌ 缺失 | **必须实现**（B-06） |
| **Scheduler** | pg advisory lock + Croniter | ❌ 缺失 scheduler | **必须实现**（B-07） |
| **每日简报生成** | daily_brief + operating_data_v3 | ❌ 缺失 | **必须实现**（B-10） |
| **答案契约** | 5 套模板 | ❌ 缺失 | **必须实现**（B-11） |

---

## 4. 修复计划

按"前后端分工"列修复任务。每项给出 **依赖 / 阻塞 / 工作量（大/中/小）** 评估。

### 阶段 1：打通 LLM 与数据骨架（最关键，最阻塞）

| 编号 | 任务 | 归属 | 依赖 | 阻塞 | 工作量 |
|---|---|---|---|---|---|
| P-01 | 实现 **hermes-runtime** 后端服务（FastAPI `:8020`，HMAC 签名 HTTP 客户端） | backend | — | B-01/B-02/B-12 | 大 |
| P-02 | 实现 **Anspire 网关代理**（`open-gateway.anspire.ai/v6` HMAC 签名，30+ 模型白名单） | backend | P-01 | B-01 | 大 |
| P-03 | 实现 **assistant_orchestrator**（7 阶段流水线只先打通 scope_validate → route → answer 三阶段） | backend worker | P-01 | 聊天 | 大 |
| P-04 | 前端接入 **SSE 流式回答**（替换 750ms 轮询） | frontend | P-03 | F-03 | 中 |
| P-05 | 前端实现 **assistant-output.tsx** 的结构化回答渲染（DataAnswer / DataChart / AnswerTable / FileAnswer / ResearchAnswer / FollowUps） | frontend | P-03 | F-04/F-06 | 大 |
| P-06 | 后端实现 **daily_brief + operating_data_v3 物化**（PATCH 风格，不要 V1 全量） | backend | P-01 | B-10 | 大 |
| P-07 | 后端实现 **答案契约**（5 套模板） | backend | P-03 | B-11 | 中 |
| P-08 | 后端实现 **answer_contract 验证**（作为 7 阶段中 last 阶段的 contract repair） | backend | P-07 | F-04 | 中 |

### 阶段 2：源 + 推送 + 调度（运营闭环）

| 编号 | 任务 | 归属 | 依赖 | 阻塞 | 工作量 |
|---|---|---|---|---|---|
| P-09 | 实现 **source_contract_v3**（Pydantic schema + 批量校验） | backend | — | B-04 | 中 |
| P-10 | 实现 **feishu source ingestion**（3 张多维表 AppToken + 物化 + 原子激活） | backend | P-09 | B-05 | 大 |
| P-11 | 实现 **Scheduler**（pg_try_advisory_xact_lock leader + Croniter） | backend worker | — | B-07 | 中 |
| P-12 | 实现 **飞书推送**（应用凭证 + 推送 + 测试发送 API） | backend | P-11 | B-06/F-20 | 中 |
| P-13 | 后端实现 **Executor / Jobs 扩展**（指向 report.generate / file.extract / source.sync / webhook.deliver） | backend | P-06/P-10 | B-13 | 中 |
| P-14 | 后端实现 **CLI 运维**（create-admin / create-user / configure-source / trigger-sync / reset-data / seed） | backend | P-09 | B-13 | 中 |

### 阶段 3：工具 + 文档 + 体验

| 编号 | 任务 | 归属 | 依赖 | 阻塞 | 工作量 |
|---|---|---|---|---|---|
| P-15 | 实现 **MCP 工具注册表**（30+ 业务工具的 capability token 鉴权） | backend | P-02 | B-03 | 大 |
| P-16 | 实现 **`/v1/tools/call` MCP 接口** | backend | P-15 | B-15 | 中 |
| P-17 | 实现 **文件提取**（PDF/DOCX/XLSX/PPTX，chunks 1600/160） | backend worker | — | B-08 | 中 |
| P-18 | 实现 **Embedding 缓存**（HTTPS 断点续传 + SHA256 校验） | backend worker | P-17 | B-09 | 中 |
| P-19 | 实现 **PersonalCenter preferences**（PUT 偏好 API，无需 localStorage 全量化） | backend | — | F-25 | 小 |
| P-20 | **admin-shell** 中 model / feishu / automation / source-mapping / source-sync / capabilities 全部接入对应后端 API | frontend | P-12/P-13/P-14 | F-19~F-24 | 中 |
| P-21 | **admin-shell** 新增"数据源 - 新建/编辑组织单元"表单 | frontend | — | F-15 | 小 |
| P-22 | **admin-shell** 拆 fde 专属 section（运行状态 / 能力白名单的 fde 视图） | frontend | P-16 | F-14 | 中 |
| P-23 | **workspace** 接入 chatgpt-auth 网关（hook 在 layout.tsx） | frontend | — | F-01 | 小 |
| P-24 | **workspace** 接入正式偏好 API（替换 localStorage） | frontend | P-19 | F-25 | 中 |
| P-25 | **workspace** 接入明暗主题 + i18n（zh-CN/zh-TW/en） | frontend | — | F-02/F-12 | 中 |
| P-26 | **workspace** 补"报告手动重生成"按钮 | frontend | P-13 | F-13 | 小 |
| P-27 | **demo/prototype.tsx** 补 chatgpt-auth、FollowUps、推屏预览 FeishuPreview、30 秒锁定、场景抽屉 | frontend | — | F-07/F-08/F-09/F-11 | 中 |
| P-28 | **demo/prototype.tsx** 补 IME 组合态、字数阈值、Cmd+K 快捷键 | frontend | — | F-05 | 小 |
| P-29 | **demo/prototype.tsx** 补多选事业部 picker | frontend | — | F-10 | 小 |
| P-30 | **demo/prototype.tsx** 补离线提示卡片 | frontend | — | F-17 | 小 |
| P-31 | **admin-shell** 补 MCP 工具调用调试 UI（MCP 工具面板） | frontend | P-16 | F-18 | 中 |

### 阶段 4：测试 / 演练 / 文档

| 编号 | 任务 | 归属 | 工作量 |
|---|---|---|---|
| P-32 | 写 **LLM 集成测试**（mock Anspire，验证 7 阶段流水线） | backend | 中 |
| P-33 | 写 **MCP 工具调用测试** | backend | 中 |
| P-34 | 写 **飞书源 ingestion 集成测试** | backend | 中 |
| P-35 | 写 **scheduler leader 选举测试** | backend | 小 |
| P-36 | 写 **assistant-output 渲染快照测试** | frontend | 中 |
| P-37 | 更新 **docs/architecture/**（新增 MCP / Hermes / Scheduler / ingest ADR） | docs | 中 |
| P-38 | 写 **docs/production/llm-integration.md**（Anspire 接入 + 密钥 + 限流） | docs | 中 |
| P-39 | 整理 **docs/migration/new-vs-current.md**（本文件） | docs | 已完成 |

---

## 5. 一次执行建议（最少改动让 admin 端不再占位）

按"以后端为准"原则，最有价值的最小改动集：

1. **P-13**（Jobs 扩展）解锁最短闭环：`POST /jobs` 当前仅允许 `report.generate` / `file.extract`；扩展后允许 `source.sync` / `webhook.deliver` / `assistant.run`。**先把同步、推送任务挂到 jobs 体系**，admin 端从 placeholder 切到真实触发。
2. **P-20**：admin-shell 中 6 个 section 接入 jobs 触发。
3. **P-19 / P-24**：偏好 API + frontend 替换 localStorage（最小最干净）。
4. **P-21**：数据源"新建/编辑组织单元"（接口已存在仅前端未挂）。

执行后：admin 端 4 个占位 section 中的 2 个（data section + automation）会真正落地；workspace 偏好从 localStorage 切到正式 API；admin 数据源可以完整 CRUD。

要继续推进哪一阶段？可以直接给我阶段编号。
