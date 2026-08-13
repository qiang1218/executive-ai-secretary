# Agent 开发指南

本文件供 AI Agent / 开发者参考，描述项目架构、代码约定与常见开发模式。

---

## 1. 项目概览

**董事长 AI 秘书** — 面向企业最高经营决策者的可信 AI 工作台。

### 技术栈

| 层 | 技术 | 版本要求 |
|---|---|---|
| 后端 API | FastAPI + SQLAlchemy 2.0 (async) + Alembic | Python ≥ 3.12 |
| Worker | FastAPI + hermes-agent (AIAgent) | 复用 backend venv |
| 前端 | Next.js 16 + React 19 + Vite (vinext) | Node ≥ 22.13 |
| 数据库 | PostgreSQL 16 + pgvector | |
| 包管理 | uv (Python) / npm (Node) | |

### 架构拓扑

```
frontend (3000) ──HTTP──> backend API (8000)
                             │
                             ├── 写库 + NOTIFY new_job ──> PostgreSQL
                             │                                │
worker (8001) ◄── HTTP 调用 ────────────────────────────────┘
   └─ AgentRunner.chat() → AIAgent.run_conversation()
        └─ MCP 工具循环 (stdio 子进程) → 数据查询
```

- API 通过 HTTP 调用 worker 的 `POST /v1/chat/completions`（SSE 流式）
- worker 内嵌 `hermes-agent`，通过 `AIAgent` 完成 LLM + tool 调用循环
- MCP server 以 stdio 子进程方式 spawn，通过 `ENTERPRISE_ID` 环境变量实现多企业数据隔离

---

## 2. 目录结构

```
executive-ai-secretary/
├── backend/
│   ├── alembic/              # 数据库迁移
│   │   ├── versions/         # 迁移脚本（命名：<rev>_<description>.py）
│   │   └── env.py
│   ├── main.py               # 启动入口（API / Worker / 双进程模式）
│   ├── pyproject.toml        # 依赖定义（uv）
│   ├── uv.lock               # 依赖锁文件
│   ├── scripts/              # 诊断 / 种子 / 测试脚本（不进生产镜像）
│   ├── src/
│   │   ├── api/              # API 层
│   │   │   ├── deps.py       # 依赖注入（Annotated 别名）
│   │   │   ├── main.py       # FastAPI 应用工厂
│   │   │   ├── middlewares/   # 中间件
│   │   │   ├── registries/    # 路由 / 中间件注册
│   │   │   └── routes/        # 路由模块（按领域拆分）
│   │   ├── configs/           # Settings (pydantic-settings)
│   │   ├── core/              # 跨层共享（Principal, security, pagination, encryption）
│   │   ├── db/                # SQLAlchemy 引擎 + Session 工厂
│   │   ├── exceptions/        # AppError + 异常处理器
│   │   ├── logs/              # 日志配置
│   │   ├── models/            # ORM 模型（按领域拆分，re-export 聚合）
│   │   ├── repositories/      # 纯数据访问层（无业务逻辑）
│   │   ├── schemas/           # Pydantic schema（按领域拆分，re-export 聚合）
│   │   ├── services/          # 业务逻辑层
│   │   ├── utils/             # CLI 工具
│   │   └── worker/            # Worker 应用
│   │       ├── agent.py       # AgentRunner：AIAgent 封装 + MCP 注册
│   │       ├── app.py         # Worker FastAPI 应用
│   │       ├── mcp_server.py  # MCP server（stdio 子进程入口）
│   │       ├── profile_prompts.py  # Profile 任务 prompt
│   │       └── session_store.py    # 会话历史存储
│   └── tests/                 # pytest 测试
├── deploy/
│   ├── Dockerfile.backend     # 后端统一镜像（api + worker 共用）
│   ├── Dockerfile.frontend    # 前端多阶段镜像（vinext + nginx）
│   ├── docker-compose.yml     # 编排配置
│   ├── init-seed.sh           # 首次初始化脚本
│   └── nginx.conf             # nginx 反代配置
├── frontend/
│   ├── app/
│   │   ├── demo/              # Demo 原型组件
│   │   ├── globals/           # 全局 CSS（base → login → home → conversation → workbench → admin）
│   │   ├── production/        # 生产应用主体
│   │   │   ├── app.tsx        # 应用入口（会话状态机）
│   │   │   ├── api-client.ts  # HTTP 客户端（CSRF + 错误处理）
│   │   │   ├── services.ts    # API 调用层
│   │   │   ├── types.ts       # TypeScript 类型定义
│   │   │   ├── workspace*.tsx # 工作台组件
│   │   │   └── admin-shell*.tsx  # 管理后台
│   │   ├── shared/            # 跨模式共享 hooks
│   │   ├── layout.tsx         # Next.js 根布局
│   │   └── page.tsx           # 入口分发（demo / production）
│   ├── vite.config.ts         # Vite 配置（dev proxy /api → :8000）
│   ├── next.config.ts
│   ├── tsconfig.json
│   └── package.json
├── docs/                      # 架构文档
├── STARTUP.md                 # 启动指南
└── agent.md                   # 本文件
```

---

## 3. 后端代码约定

### 3.1 分层架构

```
routes (API 层) → services (业务层) → repositories (数据层) → models (ORM)
                     ↓
                  schemas (Pydantic 校验 / 序列化)
```

- **routes**: 只做 HTTP 参数解析、调用 service、返回 schema。不含业务逻辑。
- **services**: 业务逻辑核心。接收 `AsyncSession`，调用 repository / 其他 service。
- **repositories**: 纯数据访问。函数式风格，接收 session，返回 ORM 对象或原始数据。
- **models**: SQLAlchemy ORM 声明。通过 `UUIDMixin` / `TimestampMixin` 复用公共列。
- **schemas**: Pydantic v2 模型。`*In` 为请求体，`*Out` 为响应体，`*Update` 为部分更新。

### 3.2 依赖注入

路由层通过 `api/deps.py` 中的 `Annotated` 别名注入依赖：

```python
from api.deps import ExecutivePrincipalDep, ConversationServiceDep

@router.post("", response_model=ConversationOut)
async def create_conversation(
    payload: ConversationCreate,
    principal: ExecutivePrincipalDep,
    service: ConversationServiceDep,
) -> ConversationOut:
    return await service.create_conversation(principal, payload)
```

新增 Service 时在 `deps.py` 中添加对应的工厂函数 + `Annotated` 别名。

### 3.3 认证与授权

- 认证：基于 HttpOnly Cookie 的 opaque session token，`authz.py` 中 `get_current_principal` / `get_executive_principal` 校验。
- CSRF：非 GET 请求必须携带 `X-CSRF-Token` header，值匹配 `exec_csrf` cookie。
- 多租户：所有数据查询必须带 `enterprise_id` 过滤。`Principal.enterprise_id` 是当前企业的隔离边界。
- 数据范围：`DataScopeGrant` 控制用户可访问的事业部（`organization_unit_ids`）。

### 3.4 错误处理

业务错误统一抛 `AppError(status_code, code, message, details)`，由全局异常处理器转为 JSON：

```json
{"error": {"code": "...", "message": "...", "request_id": "..."}}
```

不要在 route 中直接 `raise HTTPException`，用 `AppError` 代替。

### 3.5 数据库迁移

```powershell
# 生成迁移脚本（自动 diff）
.\.venv\Scripts\alembic.exe revision --autogenerate -m "描述"

# 应用迁移
.\.venv\Scripts\alembic.exe upgrade head

# 回滚
.\.venv\Scripts\alembic.exe downgrade -1
```

约定：
- 迁移文件命名：`<revision>_<snake_case_description>.py`
- 必须在 `upgrade()` 和 `downgrade()` 中实现双向迁移
- `alembic/env.py` 使用同步 psycopg 驱动（从 asyncpg URL 自动转换）
- `target_metadata = Base.metadata`，确保 `models` 包中所有表都注册

### 3.6 配置管理

`configs/settings.py` 中 `Settings(BaseSettings)` 统一管理：
- 环境变量优先级最高（`.env` 文件次之）
- `case_sensitive=False`：环境变量名不区分大小写
- 敏感字段用 `SecretStr` 类型，通过 `.get_secret_value()` 获取明文
- `get_settings()` 使用 `@lru_cache` 单例化

### 3.7 Worker / Agent 调用链

```
API: ConversationService.prepare_message()
  → 组装 system_prompt (harness_config + profile_prompt)
  → 组装 llm_config (base_url, api_key, model, provider)
  → 组装 mcp_servers 配置
  → HTTP POST /v1/chat/completions → Worker

Worker: AgentRunner.chat()
  → _ensure_mcp_registered(enterprise_id)  # 注册 MCP server（企业隔离）
  → AIAgent.run_conversation()             # LLM + tool 调用循环
  → SSE 流式回传 → API → 前端
```

关键约定：
- LLM 凭据由 API 侧从数据库解密后注入 worker，worker 不持有密钥
- `ENTERPRISE_ID` 注入 MCP 子进程 env，实现 SQL 级数据隔离
- 企业切换时先 `shutdown_mcp_servers` 再重新注册
- `requested_model_id`（用户选择的模型）必须透传到 worker 的 `llm_config["model"]`

### 3.8 个人偏好注入

会话时从 `ExecutivePersonalProfile` 读取用户偏好（称呼、金额单位、回复风格、语言），通过 `_build_profile_prompt()` 格式化为 prompt 段，追加到 system prompt 末尾。

### 3.9 代码风格

- ruff 配置在 `pyproject.toml`：`target-version = "py312"`, `line-length = 100`
- 启用规则：`E, F, I, B, UP, S, ASYNC`（`S101` assert 忽略）
- `from __future__ import annotations` 放在每个文件首行
- 类型标注：所有公开函数 / 方法必须有完整类型标注
- 文档字符串：模块级 + 公开类 / 函数必须有 docstring

### 3.10 测试约定

- 测试框架：pytest + pytest-asyncio
- 测试 DB：SQLite (aiosqlite)，通过 `conftest.py` 中的环境变量注入
- 每个测试用 `clean_database` fixture 重建表结构
- 标记：`@pytest.mark.postgres` 表示需要真实 PostgreSQL
- 运行：`.\.venv\Scripts\pytest.exe`

---

## 4. 前端代码约定

### 4.1 应用模式

`app/page.tsx` 根据 `appMode` 分发：
- `production` → `ProductionApplication`（生产模式）
- `demo` → `DemoProductPrototype`（演示原型）

`appMode` 来自 `runtime.mjs`，由构建期环境变量 `NEXT_PUBLIC_APP_MODE` 决定。

### 4.2 CSS 架构

`globals/index.css` 按顺序导入 6 个模块：
```
base.css → login.css → home.css → conversation.css → workbench.css → admin.css
```

- **base.css**: `:root` CSS 变量、reset、`html`/`body` 基础样式
- 后续模块可覆盖 base 的默认值
- CSS 变量命名：`--canvas`, `--surface`, `--ink`, `--accent` 等
- 响应式：优先使用 `clamp()`, `vw`, `vh`, `dvh` 等视口单位
- `html` / `body` / 根容器必须显式设置 `width: 100%; height: 100%` 确保填满视口

### 4.3 API 调用

`api-client.ts` 封装了统一的 `fetch` 客户端：
- 自动注入 CSRF token（从 cookie 读取，写入 `X-CSRF-Token` header）
- `ApiError` 统一错误类型（`status`, `code`, `message`, `requestId`）
- `apiClient.get/post/put/patch/delete` 方法

`services.ts` 按领域封装具体的 API 调用函数，返回强类型结果。

### 4.4 类型定义

`types.ts` 定义所有 TypeScript 类型，与后端 schema 对应：
- 后端 `*Out` schema → 前端同名 type
- `ProductionBootstrap` 聚合多个 API 响应（启动时一次性加载）

### 4.5 组件组织

- `app.tsx`: 会话状态机（`checking → anonymous → ready → error`）
- `workspace.tsx`: 工作台主体（聊天 + 报表 + 侧栏）
- `admin-shell.tsx`: 管理后台
- `workspace-views.tsx`: 工作台视图组件（模型选择器、消息列表等）
- 状态管理：React `useState` / `useCallback` / `useEffect`，无外部状态库

### 4.6 代码风格

- TypeScript strict mode
- ESLint: `eslint-config-next`
- `"use client"` 指令放在客户端组件首行
- 函数组件 + Hooks，无 class 组件
- 运行检查：`npm run typecheck` / `npm run lint`

---

## 5. 部署约定

### 5.1 Docker 部署

```bash
# 首次初始化
cp .env.docker.example .env  # 填入真实密钥
docker compose up -d db       # 等待 db healthy
docker compose run --rm init  # 迁移 + 建企业 + 建用户
docker compose up -d          # 启动全部服务
```

### 5.2 镜像策略

- **后端**: 单一镜像，通过 `SERVICE_ROLE` 环境变量切换 api / worker
- **前端**: 两阶段构建（vinext builder + nginx runner），nginx 反代 `/api/*` → api
- **数据库**: `pgvector/pgvector:pg16`

### 5.3 共享卷

`runtime_data` 卷在 api 和 worker 之间共享：
- `/app/runtime/files`: 上传文件落盘（api 写、worker 读）
- `/app/runtime/skills_active`: HERMES_HOME（api 写入 skill、worker 通过 hermes-agent 读取）

### 5.4 依赖管理

- 后端: `uv lock` 生成 `uv.lock`，`uv sync --extra hermes` 安装
- Docker 构建用 `--frozen` 确保 lock 文件一致
- 新增 Python 依赖：编辑 `pyproject.toml` → `uv lock` → 提交两个文件
- 新增 npm 依赖：`npm install <pkg>` → 提交 `package.json` + `package-lock.json`

---

## 6. 常见开发模式

### 6.1 新增 API 端点

1. 在 `schemas/` 中定义 `*In` / `*Out` Pydantic 模型
2. 在 `models/` 中确认 / 新增 ORM 模型（需要迁移则跑 `alembic revision`）
3. 在 `repositories/` 中添加数据访问函数
4. 在 `services/` 中实现业务方法
5. 在 `api/deps.py` 中添加 Service 依赖别名（如果新增 service）
6. 在 `api/routes/<domain>.py` 中添加路由端点
7. 在 `api/routes/__init__.py` 的 `_ROUTE_MODULES` 中注册（如果是新文件）

### 6.2 新增前端页面

1. 在 `types.ts` 中定义 TypeScript 类型
2. 在 `services.ts` 中封装 API 调用
3. 在 `app/production/` 中创建组件
4. 在 `workspace.tsx` 或 `admin-shell.tsx` 中集成
5. 在 `globals/` 中添加 CSS（新文件需在 `index.css` 中 `@import`）

### 6.3 修改数据库 Schema

1. 修改 `models/<domain>.py` 中的 ORM 声明
2. `alembic revision --autogenerate -m "描述"`
3. 检查生成的迁移脚本（autogenerate 不完美，需人工校验）
4. `alembic upgrade head`
5. 更新对应的 `schemas/` Pydantic 模型
6. 更新前端 `types.ts`

### 6.4 添加 MCP 工具

1. 在 `worker/mcp_server.py` 中实现工具函数
2. 确保函数有完整的类型标注（MCP 自动从签名生成 schema）
3. 确保所有 SQL 查询带 `enterprise_id` 过滤
4. 在 `services/mcp_registry.py` 中注册工具元数据

---

## 7. 关键注意事项

### 7.1 Windows 开发

- 项目主要在 Windows 上开发，路径用 `\` 分隔
- `main.py` 中 monkey-patch `subprocess.Popen` 强制 UTF-8 编码，避免 gbk 解码崩溃
- `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` 环境变量对子进程生效

### 7.2 安全红线

- **永远不要**在代码中硬编码密钥、密码、API key
- 敏感字段用 `SecretStr`，通过 `.get_secret_value()` 获取
- 文件加密用 `FILE_ENCRYPTION_KEY`，集成凭据用 `INTEGRATION_ENCRYPTION_KEY`
- LLM 凭据由 API 从数据库解密后注入 worker，worker 不持有密钥
- 所有用户输入必须经过 Pydantic 校验，不要直接使用 `request.json()`

### 7.3 多租户隔离

- 所有数据查询必须带 `enterprise_id` 过滤
- MCP 子进程通过 `ENTERPRISE_ID` 环境变量隔离
- 企业切换时必须 `shutdown_mcp_servers` 再重新注册
- `DataScopeGrant` 控制事业部级数据访问权限

### 7.4 提交规范

Commit message 格式：`type(scope): 描述`

类型：
- `feat`: 新功能
- `fix`: 修复
- `refactor`: 重构
- `docs`: 文档
- `deploy`: 部署配置
- `deps`: 依赖

示例：
```
feat(chat): 用户个人偏好注入 system prompt
fix(deps): 将 mcp 纳入 uv.lock，修复 Docker 环境下 MCP 工具不注册
fix(chat): 助手回复改为左头像+右卡片 chat 布局
```

### 7.5 不提交的文件

- `backend/scripts/_*.py`: 诊断 / 临时脚本
- `backend/scripts/*.txt`: 调试输出
- `.env`: 环境变量（含密钥）
- `__pycache__/`, `.venv/`, `node_modules/`, `.next/`
