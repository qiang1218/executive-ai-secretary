# 后续优化规划设计

> 本文档基于对现有代码的完整探查，提出五个优化方向的设计方案。每个方向包含：现状、目标、设计方案、操作步骤、影响范围。**本文档仅作设计，不修改代码。**

---

## 目录

1. [前端报告输出优化](#1-前端报告输出优化)
2. [每日经营报告加入邮件爬取与待办提醒](#2-每日经营报告加入邮件爬取与待办提醒)
3. [后端模型列表优化](#3-后端模型列表优化)
4. [后端查询改写的测试与优化](#4-后端查询改写的测试与优化)
5. [后端 Skill / MCP 路由机制](#5-后端-skill--mcp-路由机制)

---

## 1. 前端报告输出优化

### 1.1 现状

| 维度 | 现状 |
|------|------|
| 报告组件 | `ProductionDailyBriefPanel`（晨间简报）+ `ProductionReportPanel`（每日/每周报告），均在 `workspace.tsx` 中 |
| 数据格式 | `Report.content` 是 `Record<string, unknown>` 通用 JSON，前端用 `firstText()`/`recordItems()` 按候选 key 名提取字段 |
| 渲染方式 | 结构化卡片：摘要 + 指标栏 + 变化列表 + 行动项 + 来源折叠 |
| AI 对话回答 | `AssistantOutputRenderer` 渲染 `ChairmanAnswer`（data 类）和 `ExecutiveGeneralAnswer`（general 类），含模板化决策卡片 |
| 痛点 | ① `content` 无 schema 约束，字段名靠候选 key 猜测，新增字段需改前端；② general 类的 `draft_markdown` 用 `<pre>` 原文展示，无 Markdown 渲染；③ 报告与 AI 对话回答两套渲染逻辑割裂；④ 无导出能力（PDF/复制） |

### 1.2 目标

- 报告内容契约化：后端输出固定 schema，前端按 schema 渲染，不再猜 key
- Markdown 渲染：general 类回答和报告的文本段落支持 Markdown
- 统一渲染层：报告与 AI 对话回答共用一套卡片组件
- 导出能力：支持复制为文本、导出 PDF（可选）

### 1.3 设计方案

#### 1.3.1 报告内容 schema 化

定义统一的 `ReportContent` schema（TypeScript 类型 + 后端 pydantic model 双向对齐）：

```typescript
// frontend/app/production/types.ts 新增
type ReportContent = {
  schema_version: 1;
  headline: string;                    // 标题
  summary: string;                     // 摘要（支持 Markdown）
  data_as_of: string | null;           // 数据截止时间
  metrics?: ReportMetric[];            // 关键指标
  sections?: ReportSection[];          // 分段内容（变化、风险、机会等）
  action_items?: string[];             // 行动项
  source_summary?: string;             // 来源/口径
  decision_readiness?: "ready" | "partial" | "stale";  // 决策就绪度
};

type ReportMetric = {
  label: string;
  value: string;
  delta?: string;        // 环比/同比变化
  trend?: "up" | "down" | "flat";
  unit?: string;
};

type ReportSection = {
  title: string;
  kind: "change" | "risk" | "opportunity" | "note";
  items: string[];       // 每项支持 Markdown
};
```

后端在生成报告时（`run_assistant_job` 的 data/general profile 输出）按此 schema 结构化，写入 `Report.content_json`。

#### 1.3.2 引入 Markdown 渲染

- 轻量方案：用 `marked` + `dompurify`（已有 React 生态，无额外重依赖）
- 应用范围：`ReportContent.summary`、`ReportSection.items[]`、`ExecutiveGeneralAnswer.draft_markdown`
- 替换现有 `<pre>` 原文展示为 `<div dangerouslySetInnerHTML={ sanitized(marked(text)) } />`

#### 1.3.3 统一卡片组件

抽取 `workspace.tsx` 和 `assistant-output.tsx` 的共性渲染逻辑到 `frontend/app/production/report-cards/`：

```
report-cards/
  MetricRail.tsx        // 指标栏（复用现有 executive-metric-rail）
  SectionList.tsx       // 分段列表（变化/风险/机会）
  ActionItems.tsx       // 行动项有序列表
  SourceSummary.tsx     // 来源折叠
  MarkdownText.tsx      // Markdown 渲染封装
  ReportView.tsx        // 组合以上组件的完整报告视图
```

`ProductionReportPanel` 和 `AssistantOutputRenderer`（data 类）都改为渲染 `<ReportView content={...} />`。

#### 1.3.4 导出能力

- **复制为文本**：在 `ReportView` 顶部加"复制"按钮，把 schema 内容序列化为纯文本（Markdown → 纯文本）
- **导出 PDF**（可选，后期）：用浏览器 `window.print()` + 打印样式，或引入 `react-to-print`

### 1.4 操作步骤

1. 定义 `ReportContent` schema，写入 `frontend/app/production/types.ts`
2. 创建 `report-cards/` 目录，抽取并实现 5 个子组件
3. 改造 `ProductionReportPanel`：从 `report.content` 按 schema 解析（保留对旧格式的兼容降级）
4. 改造 `AssistantOutputRenderer`：data 类输出适配 `ReportContent` schema
5. 引入 `marked` + `dompurify`，实现 `MarkdownText` 组件
6. 替换 general 类的 `<pre>` 为 `MarkdownText`
7. 加"复制"按钮，实现文本序列化
8. 后端：在 `assistant_orchestrator.py` 的 `_data` / `_general` 输出处，按 schema 结构化输出

### 1.5 影响范围

| 层 | 文件 | 改动类型 |
|----|------|----------|
| 前端 | `types.ts` | 新增 schema 类型 |
| 前端 | `report-cards/*` | 新建组件 |
| 前端 | `workspace.tsx` 的 `ProductionReportPanel` | 重构渲染逻辑 |
| 前端 | `assistant-output.tsx` | 重构 data/general 渲染 |
| 前端 | `package.json` | 加 `marked`、`dompurify` 依赖 |
| 后端 | `assistant_orchestrator.py` | 输出结构化对齐 schema |

---

## 2. 每日经营报告加入邮件爬取与待办提醒

### 2.1 现状

| 维度 | 现状 |
|------|------|
| 邮件功能 | **完全不存在**（无 smtp/imap/pop3 代码，`User.email` 仅用于账户系统） |
| 定时任务框架 | **已完备**：`ScheduledTask` + `scheduler.py` + `runner.py` + `Job` 队列 + lease/heartbeat/重试/dead-letter |
| 数据同步模式 | `run_data_sync_job` 已支持飞书/PG 源，有完整的增量同步（`SourceCheckpoint.cursor_value`）、域状态追踪（`DataDomainStatus`）、运行记录（`DataSyncRun`） |
| 每日简报 | `daily_brief.py` 的 `build_daily_brief()` 已有 attention item 机制，按域聚合关注事项 |
| 扩展点 | `DataSource.source_type` 可扩展；`execute_job_handler()` 可加新 job_type；`DOMAIN_ORDER` 可加新域 |

### 2.2 目标

- 定时爬取指定邮箱的经营相关邮件
- 从邮件中提取待办事项（如会议通知、审批要求、客户回复等）
- 将邮件待办注入每日晨间简报的 attention items
- 在前端晨间简报面板中展示邮件来源的待办

### 2.3 设计方案

#### 2.3.1 整体架构

```
ScheduledTask(task_type="email.fetch", cron="0 */2 * * *")
  │
  ▼
scheduler.py: enqueue_due_tasks()
  │  创建 Job(job_type="email.fetch", payload={data_source_id})
  ▼
runner.py: execute_job_handler()
  │  分发到 run_email_fetch_job(job, settings)
  ▼
email_ingestion.py: run_email_fetch_job()
  ├─ 连接 IMAP 服务器
  ├─ 读取 SourceCheckpoint.cursor_value（上次 UID）
  ├─ 拉取新邮件（UID > cursor）
  ├─ 解析邮件：主题、发件人、正文、附件名、时间
  ├─ 待办识别：规则匹配 + LLM 辅助分类
  ├─ 写入 FactEmail 表（结构化存储）
  ├─ 更新 SourceCheckpoint（新 cursor）
  └─ 更新 DataSyncRun（status=completed）
       │
       ▼
daily_brief.py: build_daily_brief()
  ├─ 查询 FactEmail 中未完成的待办
  ├─ 按 attention 规则生成 DailyBriefItem
  └─ 注入到 items 列表（domain="email"）
       │
       ▼
前端 ProductionDailyBriefPanel 展示
```

#### 2.3.2 数据模型

**新增 `FactEmail` 表**：

```python
# backend/src/models/data_source.py 新增
class FactEmail(Base):
    __tablename__ = "fact_email"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    enterprise_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprises.id"))
    data_source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_sources.id"))
    message_uid: Mapped[int]           # IMAP UID
    message_id: Mapped[str]            # 邮件 Message-ID header
    subject: Mapped[str]
    sender: Mapped[str]
    recipients: Mapped[list[str]]      # JSON array
    received_at: Mapped[datetime]
    body_text: Mapped[str | None]      # 纯文本正文
    body_html: Mapped[str | None]      # HTML 正文（可选）
    attachment_names: Mapped[list[str]]  # JSON array
    # 待办识别结果
    todo_category: Mapped[str | None]  # meeting/approval/customer_reply/action_required/other
    todo_due_at: Mapped[datetime | None]
    todo_summary: Mapped[str | None]   # 一句话待办摘要
    todo_status: Mapped[str]           # pending/done/ignored
    fingerprint: Mapped[str]           # 内容指纹（去重）
    created_at: Mapped[datetime]
```

**扩展 `DataSource`**：
- `source_type` 新增值 `"email"`
- `configuration_json` 存 IMAP 配置：`{host, port, use_ssl, username, folder}`
- `secret_reference_key` 引用环境变量中的邮箱密码

#### 2.3.3 邮件爬取与待办识别

**IMAP 连接**（`email_ingestion.py`）：
- 用 Python 标准库 `imaplib` + `email` 模块，无额外依赖
- 支持 imaplib.IMAP4_SSL（推荐）和 IMAP4
- 增量拉取：`imap.uid('search', None, f'UID {last_uid+1}:*')`

**待办识别策略**（两层）：

第一层：规则匹配（快、确定性强）
```python
RULES = [
    {"pattern": r"会议|开会|join|meeting", "category": "meeting"},
    {"pattern": r"审批|approval|approve", "category": "approval"},
    {"pattern": r"请回复|请确认|请查阅|action required", "category": "action_required"},
    {"pattern": r"客户|报价|合同|交付", "category": "customer_reply"},
]
```

第二层：LLM 辅助分类（可选，针对规则未命中的邮件）
- 调 hermes `general` profile，输入邮件主题+正文前 500 字
- 输出 `{is_todo: bool, category: str, summary: str, due_at: str | null}`
- 限制：只对 sender 在联系人列表或主题含关键词的邮件调 LLM，控制成本

#### 2.3.4 注入每日简报

扩展 `daily_brief.py`：
```python
DOMAIN_ORDER = ["opportunity", "delivery", "collection", "target", "email"]  # 新增 email

def _email_attention_items(db, enterprise_id, scope):
    emails = db.scalars(
        select(FactEmail)
        .where(
            FactEmail.enterprise_id == enterprise_id,
            FactEmail.todo_status == "pending",
            FactEmail.todo_due_at.is_not(None),
            FactEmail.todo_due_at <= utc_now() + timedelta(days=1),
        )
        .order_by(FactEmail.todo_due_at)
        .limit(5)
    ).all()
    return [
        DailyBriefItem(
            domain="email",
            title=e.todo_summary or e.subject,
            detail=f"来自 {e.sender}",
            severity="medium" if e.todo_due_at <= utc_now() else "low",
        )
        for e in emails
    ]
```

#### 2.3.5 前端展示

`ProductionDailyBriefPanel` 已支持 `domain` 标签，只需：
- 在 `DailyBriefDomainReadiness` 中加 `"email"` 域
- attention item 的 domain 标签显示为"邮件"
- 点击邮件类 item 可展开邮件详情（主题、发件人、摘要）

### 2.4 操作步骤

1. 新建 `backend/src/models/email.py`，定义 `FactEmail` 表
2. 新建 Alembic migration 创建 `fact_email` 表
3. 新建 `backend/src/services/email_ingestion.py`，实现 IMAP 连接 + 邮件拉取 + 解析
4. 实现待办识别：规则匹配函数 + LLM 辅助分类（调 hermes general）
5. 在 `runner.py` 的 `execute_job_handler()` 加 `"email.fetch"` 分支
6. 在 `scheduler.py` 的 `ensure_default_tasks()` 为 `source_type="email"` 的 DataSource 创建默认 ScheduledTask
7. 扩展 `daily_brief.py`：`DOMAIN_ORDER` 加 `"email"`，实现 `_email_attention_items()`
8. 扩展 `DataSource.source_type` 校验，支持 `"email"`
9. 后端加邮件源配置 API（管理后台配置 IMAP 连接）
10. 前端：`ProductionDailyBriefPanel` 适配 email 域展示
11. settings.py 加 IMAP 默认配置项（超时、最大拉取数等）

### 2.5 影响范围

| 层 | 文件/目录 | 改动类型 |
|----|-----------|----------|
| 后端 | `models/email.py` | 新建 |
| 后端 | `alembic/versions/xxx_email.py` | 新建 migration |
| 后端 | `services/email_ingestion.py` | 新建 |
| 后端 | `worker/runner.py` | 加 job_type 分支 |
| 后端 | `worker/scheduler.py` | 加默认 task |
| 后端 | `services/daily_brief.py` | 扩展域 |
| 后端 | `services/ingestion.py` | 扩展 source_type 校验 |
| 后端 | `api/routes/admin_*.py` | 加邮件源配置 API |
| 后端 | `configs/settings.py` | 加 IMAP 配置 |
| 前端 | `workspace.tsx` 的 `ProductionDailyBriefPanel` | 适配 email 域 |

### 2.6 风险与注意事项

- **IMAP 兼容性**：不同邮箱（Exchange/Gmail/腾讯企业邮）IMAP 实现有差异，需测试
- **密码安全**：邮箱密码通过 `secret_reference_key` 存环境变量，不落库
- **LLM 成本**：待办识别的 LLM 调用需限制频率（只对规则未命中的邮件）
- **邮件隐私**：`FactEmail.body_text` 存正文，需考虑脱敏（如隐藏其他收件人）

---

## 3. 后端模型列表优化

### 3.1 现状

| 维度 | 现状 |
|------|------|
| 模型定义 | backend `anspire.py` 有 53 个模型（38 chat + 15 non-chat），含 `family`/`profile`/`capability` 元数据 |
| 镜像 | hermes-runtime `main.py` 有 `ANSPIRE_MODEL_IDS` frozenset（38 个 chat ID），**与 backend 手动同步** |
| 数据库 | `model_provider_configs`（企业级供应商配置）+ `enterprise_model_authorizations`（企业×模型授权） |
| profile 映射 | **无映射**——一个模型走所有 profile（route/rewrite/plan/data/general 共用同一 model_id） |
| 痛点 | ① 两处模型列表手动同步，易漂移；② 无 profile 级模型路由（如 route 用便宜模型、data 用强模型）；③ 模型元数据不够丰富（无上下文窗口、单价、延迟档位）；④ 前端模型选择器无法按场景推荐 |

### 3.2 目标

- 模型列表单一数据源（SSOT），消除双处同步
- 支持 profile 级模型路由（不同 stage 用不同模型）
- 丰富模型元数据（上下文窗口、价格档位、能力标签）
- 前端模型选择器支持按场景推荐

### 3.3 设计方案

#### 3.3.1 模型目录单一数据源

将 `anspire.py` 的 `ANSPIRE_CHAT_MODELS` 作为唯一权威源，hermes-runtime 不再硬编码：

**方案**：hermes-runtime 启动时（或 embedded 模式首次调用时）从 backend 获取模型白名单。

- remote 模式：新增 `GET /internal/model-catalog` 端点（HMAC 鉴权），返回 `{model_ids: [...], version: "..."}`
- embedded 模式：直接 import `anspire.ANSPIRE_MODEL_IDS`
- hermes-runtime 的 `ProviderConfig.approved_model` 校验改为运行时从 backend 获取白名单，缓存 5 分钟

**降级**：若 backend 不可达，用 hermes-runtime 内置的 fallback 白名单（冻结快照，随版本发布）。

#### 3.3.2 profile 级模型路由

新增配置项 `MODEL_PROFILE_OVERRIDES`，允许企业为不同 profile 指定不同模型：

```python
# settings.py 新增
model_profile_overrides: dict[str, str] = Field(default_factory=dict)
# 示例: {"route": "glm-5.1", "data": "glm-5.2", "general": "gpt-5.4-mini"}
# 未配置的 profile 回退到 enterprise default model
```

在 `assistant_orchestrator.py` 解析模型时：

```python
def _resolve_model(settings, job, conversation, profile):
    # 1. profile 级覆盖（最高优先级）
    override = settings.model_profile_overrides.get(profile)
    if override:
        return override
    # 2. 会话级选择
    if conversation.selected_model_id:
        return conversation.selected_model_id
    # 3. 企业默认
    return model_config.model_id
```

#### 3.3.3 丰富模型元数据

扩展 `anspire.py` 的模型定义：

```python
# 当前
{"id": "glm-5.2", "name": "GLM-5.2", "family": "GLM", "profile": "旗舰复杂推理"}

# 扩展后
{
    "id": "glm-5.2",
    "name": "GLM-5.2",
    "family": "GLM",
    "profile": "旗舰复杂推理",
    "context_window": 128000,        # 新增：上下文窗口
    "max_output_tokens": 8192,       # 新增：最大输出
    "price_tier": "high",            # 新增：价格档位 low/medium/high
    "latency_tier": "medium",        # 新增：延迟档位
    "capabilities": ["reasoning", "code", "multilingual"],  # 新增：能力标签
    "recommended_profiles": ["data", "general"],  # 新增：推荐用于哪些 profile
}
```

#### 3.3.4 前端模型选择器优化

`GET /api/v1/models` 返回扩展后的元数据，前端：
- 按 `family` 分组展示
- 按 `recommended_profiles` 标注"推荐用于：经营分析"
- 按 `price_tier` 显示价格指示器
- 默认选中企业配置的 default model

### 3.4 操作步骤

1. 扩展 `anspire.py` 的 `ANSPIRE_CHAT_MODELS`，补齐 `context_window`/`price_tier`/`latency_tier`/`capabilities`/`recommended_profiles` 字段
2. 新增 `GET /internal/model-catalog` 端点（供 hermes-runtime remote 模式拉取白名单）
3. 改造 hermes-runtime `ProviderConfig.approved_model`：运行时从 backend 获取白名单（embedded 直接 import，remote 走 HTTP），带缓存
4. settings.py 加 `model_profile_overrides` 配置
5. `assistant_orchestrator.py` 的模型解析链加 profile override 逻辑
6. `GET /api/v1/models` 和 `GET /api/v1/admin/models` 返回扩展元数据
7. 前端模型选择器组件按 family 分组 + 推荐标注 + 价格指示

### 3.5 影响范围

| 层 | 文件 | 改动类型 |
|----|------|----------|
| 后端 | `services/anspire.py` | 扩展元数据字段 |
| 后端 | `api/routes/models.py` | 返回扩展元数据 |
| 后端 | `api/routes/admin_models.py` | 返回扩展元数据 |
| 后端 | `api/routes/internal.py`（或新建） | 新增 model-catalog 端点 |
| 后端 | `configs/settings.py` | 加 `model_profile_overrides` |
| 后端 | `worker/assistant_orchestrator.py` | 模型解析链加 profile override |
| hermes-runtime | `main.py` | `approved_model` 改为运行时获取 |
| 前端 | 模型选择器组件 | 分组 + 推荐 + 价格 |

---

## 4. 后端查询改写的测试与优化

### 4.1 现状

| 维度 | 现状 |
|------|------|
| rewrite 函数 | `assistant_orchestrator.py` 的 `_rewrite()`，调 hermes `rewrite` profile |
| 输入 | question、conversation_context、organizations、available_tools、harness_config |
| 输出 | `normalized_question`、`metrics`、`analysis_goals`、`entities`、`time_range`、`comparison`、`filters`、`sort`、`limit`、`reference_sources`、`unresolved_ambiguities` |
| 下游消费 | `_plan` 用 `available_tools` + rewrite 结果选工具；`_data` 用 authorized_results + rewrite 的 entities/time_range 对齐证据 |
| 测试 | **无专门测试**——`tests/` 下无 rewrite 相关用例 |
| 痛点 | ① 无测试，改写质量无保障；② LLM 输出不稳定，偶发 JSON 解析失败；③ `unresolved_ambiguities` 产生后无后续处理（直接透传，用户体验差）；④ 时间范围解析依赖 LLM，对"上季度"、"最近三个月"等相对时间表达易出错 |

### 4.2 目标

- 建立 rewrite 测试集，覆盖典型经营问题
- 提升 JSON 解析稳定性
- 优化相对时间解析
- `unresolved_ambiguities` 有兜底策略

### 4.3 设计方案

#### 4.3.1 测试集设计

新建 `backend/tests/test_rewrite.py`，分三层：

**第一层：黄金用例集（golden cases）**

```python
# tests/fixtures/rewrite_cases.json
[
  {
    "id": "case_001",
    "question": "上季度华东事业部回款完成率怎么样",
    "expected": {
      "normalized_question": "上季度华东事业部回款完成率",
      "entities": {"organization_unit": "华东", "metric": "回款完成率"},
      "time_range": {"type": "relative_quarter", "offset": -1},
      "comparison": None,
      "unresolved_ambiguities": []
    }
  },
  {
    "id": "case_002",
    "question": "对比下华东和华南最近三个月的商机转化",
    "expected": {
      "entities": {"organization_unit": ["华东", "华南"], "metric": "商机转化率"},
      "time_range": {"type": "relative_months", "offset": -3},
      "comparison": {"type": "cross_unit", "dimension": "organization_unit"}
    }
  },
  // ... 20-30 个典型用例
]
```

**第二层：单元测试（mock LLM 输出）**

```python
# tests/test_rewrite.py
def test_rewrite_extracts_relative_quarter():
    """验证相对时间'上季度'被正确解析"""
    mock_response = {"text": json.dumps({"normalized_question": "...", "time_range": {...}})}
    with patch("worker.assistant_orchestrator.run_hermes", return_value=mock_response):
        result = _rewrite(settings, "上季度华东回款率", ...)
        assert result["time_range"]["type"] == "relative_quarter"
```

**第三层：集成测试（真实调 LLM，标记 slow）**

```python
@pytest.mark.slow
@pytest.mark.parametrize("case", load_rewrite_cases())
def test_rewrite_with_real_llm(case):
    """调真实 hermes，验证输出结构合规性（不验证精确值）"""
    result = _rewrite(settings, case["question"], ...)
    assert "normalized_question" in result
    assert isinstance(result["entities"], dict)
    # 结构合规即可，值允许波动
```

#### 4.3.2 JSON 解析稳定性优化

当前 `parse_json_response()` 只处理 code fence 包裹，需增强：

```python
# hermes_client.py 增强 parse_json_response
def parse_json_response(text: str) -> dict[str, Any]:
    value = text.strip()
    # 1. 去 code fence
    if value.startswith("```"):
        value = value.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    # 2. 尝试直接解析
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        # 3. 提取第一个 JSON 对象（处理 LLM 输出前后多余文本）
        match = re.search(r'\{[\s\S]*\}', value)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError as exc:
                raise HermesRuntimeError("hermes_invalid_route", "无法解析 JSON") from exc
        else:
            raise HermesRuntimeError("hermes_invalid_route", "无 JSON 对象")
    # 4. schema 校验（关键字段存在性）
    if not isinstance(parsed, dict):
        raise HermesRuntimeError("hermes_invalid_route", "非对象")
    return parsed
```

#### 4.3.3 相对时间解析增强

在 `_rewrite()` 之后加一个后处理步骤，用规则修正 LLM 的时间解析：

```python
# assistant_orchestrator.py 新增
RELATIVE_TIME_PATTERNS = [
    (r"上季度|上个季度|上一季度", {"type": "relative_quarter", "offset": -1}),
    (r"本季度|这个季度|当前季度", {"type": "relative_quarter", "offset": 0}),
    (r"最近三个月|近三个月|过去三个月", {"type": "relative_months", "offset": -3}),
    (r"上月|上个月|一个月前", {"type": "relative_month", "offset": -1}),
    (r"本月|这个月|当月", {"type": "relative_month", "offset": 0}),
    (r"上周|上个星期|上一周", {"type": "relative_week", "offset": -1}),
    (r"本周|这周|这个星期", {"type": "relative_week", "offset": 0}),
]

def _postprocess_time_range(question: str, llm_time_range: dict | None) -> dict:
    """用规则修正 LLM 的时间解析，规则优先于 LLM。"""
    for pattern, spec in RELATIVE_TIME_PATTERNS:
        if re.search(pattern, question):
            return spec
    return llm_time_range or {"type": "unknown"}
```

#### 4.3.4 unresolved_ambiguities 兜底

当 rewrite 产生 `unresolved_ambiguities` 时，不直接透传，而是：

```python
def _handle_rewrite_ambiguities(rewrite_result, question):
    ambiguities = rewrite_result.get("unresolved_ambiguities", [])
    if not ambiguities:
        return rewrite_result, None
    # 生成澄清问题
    clarification = generate_clarification_question(ambiguities)
    # 返回 clarification route，让 _route 走 clarification 分支
    return rewrite_result, {
        "route": "clarification",
        "clarification_question": clarification,
    }
```

### 4.4 操作步骤

1. 新建 `tests/fixtures/rewrite_cases.json`，编写 20-30 个黄金用例
2. 新建 `tests/test_rewrite.py`，实现三层测试
3. 增强 `hermes_client.parse_json_response()`，加 JSON 对象提取 + schema 校验
4. 在 `assistant_orchestrator.py` 新增 `_postprocess_time_range()`，在 `_rewrite()` 调用
5. 实现 `_handle_rewrite_ambiguities()`，在 `_rewrite()` 返回后处理
6. 运行测试集，根据失败用例迭代 prompt（`harness_config.prompts.rewrite`）
7. 把测试加入 CI（mock 层默认跑，real LLM 层标记 slow 手动触发）

### 4.5 影响范围

| 层 | 文件 | 改动类型 |
|----|------|----------|
| 后端 | `tests/fixtures/rewrite_cases.json` | 新建 |
| 后端 | `tests/test_rewrite.py` | 新建 |
| 后端 | `worker/hermes_client.py` | 增强 `parse_json_response` |
| 后端 | `worker/assistant_orchestrator.py` | 加 `_postprocess_time_range`、`_handle_rewrite_ambiguities` |

---

## 5. 后端 Skill / MCP 路由机制

### 5.1 现状

| 维度 | 现状 |
|------|------|
| MCP 工具注册 | 双层：`mcp_registry.py` 硬编码 11 个内置工具 + 数据库 `mcp_tool_definitions`（企业自定义组合工具） |
| 工具执行 | `mcp_app.py` 的 `/v1/tools/call` HTTP 端点，`business_tools.py` 实现 |
| 路由决策 | `_route()` 调 hermes route profile，输出 route（data/general/clarification）+ candidate_tools |
| fast_rule | `match_fast_rule()` 按 harness_config 的规则匹配，命中则跳过 LLM 路由 |
| planner | `_plan()` 调 hermes plan profile，从 available_tools 选工具 + 参数 |
| hermes toolsets | 固定 `--toolsets context_engine`，与 backend 的 MCP 工具是**两套体系** |
| Skill | **无独立 skill 机制**——hermes-agent 内部有 skill 概念，但 backend 侧未暴露 |
| 痛点 | ① hermes 的 `context_engine` toolset 与 backend MCP 工具割裂，无法联动；② route 阶段的 candidate_tools 未被 plan 阶段有效利用；③ 无 skill 抽象（可复用的多工具编排模板）；④ 新增一个业务场景需改多处（工具定义+路由规则+prompt） |

### 5.2 目标

- 统一 hermes toolset 与 backend MCP 工具的边界
- route 阶段的 candidate_tools 有效传递给 plan
- 引入 skill 抽象：可复用的"工具编排模板"
- 新增业务场景时改动最小化

### 5.3 设计方案

#### 5.3.1 厘清 hermes toolset 与 backend MCP 的边界

当前混淆点：hermes 的 `context_engine` toolset 和 backend 的 MCP 工具都叫"工具"，但职责不同。

**明确边界**：
- **hermes 内置 toolset（context_engine 等）**：hermes-agent 进程内的能力（如文件读取、代码执行、会话记忆检索），**不可被 backend 配置**，由 `--toolsets` 参数控制
- **backend MCP 工具**：企业经营数据查询工具（get_opportunity_funnel 等），通过 `available_tools` 注入到 prompt，由 hermes 在 plan 阶段选择并调用

**设计**：backend MCP 工具不依赖 hermes toolset，而是通过 prompt 注入 + HTTP 回调（`/v1/tools/call`）实现。hermes 的 `context_engine` 保留但仅用于 hermes 内部的上下文管理，不参与业务工具调用。

#### 5.3.2 route → plan 的 candidate_tools 传递

当前 `_route` 输出的 `candidate_tools` 未被 `_plan` 利用。优化：

```python
# assistant_orchestrator.py
def _route(settings, question, ...):
    response = run_hermes(settings, profile="route", ...)
    route = parse_json_response(response["text"])
    # route 已有 candidate_tools 字段
    return route, route_response

def _plan(settings, question, rewrite_result, available_tools, candidate_tools, ...):
    # 把 candidate_tools 作为 hint 传给 plan
    # plan prompt 增加: "优先考虑这些工具: {candidate_tools}"
    plan_input = {
        "question": question,
        "available_tools": available_tools,
        "candidate_tools": candidate_tools or [],  # 新增：route 的提示
        ...
    }
    response = run_hermes(settings, profile="plan", payload=plan_input, ...)
    return parse_json_response(response["text"])
```

同时在 `harness_config.prompts.plan` 中加入对 candidate_tools 的使用说明。

#### 5.3.3 引入 Skill 抽象

**Skill 定义**：一组预置的工具编排模板，描述"某个业务场景需要哪些工具、什么参数、什么顺序"。

```python
# backend/src/models/config.py 新增
class SkillDefinition(Base):
    __tablename__ = "skill_definitions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    enterprise_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprises.id"))
    name: Mapped[str]                       # 如 "opportunity_analysis"
    display_name: Mapped[str]
    description: Mapped[str]
    trigger_patterns: Mapped[list[str]]     # JSON: ["商机", "机会", "漏斗"]
    required_tools: Mapped[list[str]]       # JSON: ["get_opportunity_funnel", "get_sales_forecast"]
    default_arguments: Mapped[dict]         # JSON: {"limit": 50}
    prompt_template: Mapped[str | None]     # 该 skill 的专用 prompt 片段
    is_enabled: Mapped[bool] = mapped_column(default=True)
    version: Mapped[int] = mapped_column(default=1)
```

**Skill 匹配**：在 `_route` 之前加 skill 匹配层（类似 fast_rule 但更丰富）：

```python
def match_skill(question: str, skills: list[SkillDefinition]) -> SkillDefinition | None:
    """按 trigger_patterns 匹配 skill。"""
    for skill in skills:
        if any(pattern in question for pattern in skill.trigger_patterns):
            return skill
    return None

# 在 run_assistant_job 中
skill = match_skill(question, load_skills(db, enterprise_id))
if skill:
    # 跳过 route + plan，直接用 skill 的 required_tools + default_arguments
    calls = [{"tool": t, "arguments": skill.default_arguments} for t in skill.required_tools]
    route = {"route": "data", "route_source": "skill", "matched_skill": skill.name}
else:
    route, _ = _route(...)
    if route["route"] == "data":
        plan = _plan(..., candidate_tools=route.get("candidate_tools", []))
        calls = plan["calls"]
```

#### 5.3.4 Skill 管理后台

新增 `GET/POST/PATCH/DELETE /api/v1/admin/skills`：
- 列出企业所有 skill
- 创建/编辑/删除 skill
- 测试 skill 匹配（输入问题，返回匹配的 skill）
- 启用/禁用 skill

### 5.4 操作步骤

1. 在 `harness_config.py` 文档化 hermes toolset 与 backend MCP 工具的边界（注释 + README）
2. 改造 `_plan()`：接收 `candidate_tools` 参数，注入到 plan prompt
3. 更新 `harness_config.prompts.plan`：加入 candidate_tools 使用说明
4. 新建 `models/config.py` 的 `SkillDefinition` 表
5. 新建 Alembic migration 创建 `skill_definitions` 表
6. 新建 `services/skill_registry.py`：实现 `match_skill()`、`load_skills()`
7. 在 `assistant_orchestrator.py` 的 `run_assistant_job` 中加 skill 匹配层
8. 新建 `api/routes/admin_skills.py`：skill CRUD + 测试
9. 前端管理后台加 skill 配置页面（可选，后期）
10. 预置几个常用 skill（如 opportunity_analysis、delivery_risk、collection_aging）

### 5.5 影响范围

| 层 | 文件 | 改动类型 |
|----|------|----------|
| 后端 | `models/config.py` | 新增 `SkillDefinition` |
| 后端 | `alembic/versions/xxx_skill.py` | 新建 migration |
| 后端 | `services/skill_registry.py` | 新建 |
| 后端 | `worker/assistant_orchestrator.py` | 加 skill 匹配层 + `_plan` 传 candidate_tools |
| 后端 | `api/routes/admin_skills.py` | 新建 |
| 后端 | `services/harness_config.py` | 文档化边界 |

---

## 实施优先级建议

| 方向 | 优先级 | 理由 | 预估工作量 |
|------|--------|------|-----------|
| 4. 查询改写测试与优化 | P0 | 无测试是最大风险，且改动集中在 hermes_client + orchestrator，见效快 | 2-3 天 |
| 3. 模型列表优化 | P1 | 双处同步是隐患，profile 路由价值高 | 2-3 天 |
| 5. Skill/MCP 路由 | P1 | skill 抽象能显著降低新场景接入成本 | 3-4 天 |
| 1. 前端报告输出优化 | P2 | 体验提升，但不阻塞功能 | 3-5 天 |
| 2. 邮件爬取与待办提醒 | P2 | 功能完整但依赖多（IMAP/解析/LLM 分类） | 5-7 天 |

建议按 P0 → P1 → P2 顺序推进，每个方向独立交付，互不阻塞。
