# ADR 0004：前后端架构重构方案（v2）

- 状态：提议稿，等待评审
- 日期：2026-07-30（v2：根据评审反馈调整）
- 适用阶段：生产化第二阶段
- 关联 ADR：[ADR 0001](./0001-production-foundation.md) / [ADR 0002](./0002-runtime-and-environment-contract.md) / [ADR 0003](./0003-authorization-and-audit-matrix.md)

本 ADR 不再重复第一阶段已经确认的安全、权限、审计、备份契约。**所有 ADR 0001～0003 的不变量、文件加密、审计链、备份与跨环境隔离保持不变**。本文件只描述代码组织、分层、依赖与开发流程的重构。

## 评审反馈（v2 调整）

| 反馈 | 落地方式 |
| --- | --- |
| 顶层目录 `backend` / `frontend` 分离，对应部署等也分离 | §3.1 顶层目录重排为 `backend/` + `frontend/`，各自独立的 `deploy/`、`Dockerfile`、`compose`、`pyproject/package` |
| 前端**不动页面风格**（下次再处理） | §3.2 / §5 阶段 3 改为**纯结构拆分**：拆组件、抽 hooks、加数据层、接 OpenAPI 类型、错误协议统一；不引入设计系统、不动 CSS、不改视觉；CSS 与 `globals.css` 整体平移到 `frontend/src/styles/`，原样不动 |
| 后端配置**统一** | §3.3 / §4.6 / §5 阶段 0 阶段 2 把分散在 `compose.yml`、`env`、脚本、Settings 的环境变量收口到 `backend/configs/` 单点；用 Pydantic 强校验 + 一份"配置清单" |
| 先改文档，审核后再处理 | 当前仅修改本文档；所有代码改动待评审通过 |

---

## 1. 现状盘点

### 1.1 体量与形态

| 区域 | 体量 | 备注 |
| --- | --- | --- |
| `app/page.tsx` | 2886 行（≈185 K 字符） | 单一客户端组件，承载所有 Demo 视图、状态、调度逻辑 |
| `app/production/production-workspace.tsx` | 1859 行 | 生产端 UI 同样是大单体 |
| `app/prototype-data.ts` | 667 行 | 嵌入业务答案、量级、人物、对话历史 |
| `app/production/*.ts(x)` | 6 个文件 | 类型、API 客户端、服务层、运行时、入口 |
| `services/api/src/...` | 33 个 py 文件 | 单 `main.py`、单 `models.py`、单 `schemas.py`、`routers/` 下 10 个 router |
| `services/worker/src/...` | 1 个 py 文件 | `main.py` 514 行，承载轮询、租约、心跳、失败分类、占位写入 |
| `db/` | 1 个 schema + 1 个 drizzle 配置 | Drizzle 仅作可选模板，**生产并未真正启用**（生产数据库是 PostgreSQL + SQLAlchemy + Alembic） |
| `scripts/` | 21 个 sh + 1 个 mjs | 围绕 compose 编排 |
| `docs/` | 13 个 md | ADR + 运维手册 |

### 1.2 关键运行形态

- 两种运行模式共存：`demo-v1.0.0`（冻结 React 单页 + 静态数据）/ `production-foundation`（真实数据库 + 真实 API）。
- 通过 `app/page.tsx` ↔ `app/page.production.tsx` 双入口；CI / Docker 用文件覆盖切换。
- 前端 dev 用 `vinext`（Next.js on Vite on Cloudflare 适配），生产用 `vinext` 的 `startProdServer` + 自定义 `web-server.mjs`。
- 后端是 FastAPI + SQLAlchemy 2.0 同步 + PostgreSQL 17 + Alembic。
- 任务层是 `worker` 单进程轮询（lease + heartbeat + retry），没有真正的分布式调度。

### 1.3 已落地的"好东西"（保留不动）

下列实现已经达到第一阶段质量，重构中**只能抽象，不能弱化**：

1. Argon2id 密码、HttpOnly Session、独立 CSRF、首次改密强制。
2. 角色 × 事业部范围 × 资源所有权三段授权；`assert_org_scope` / `scope_snapshot_is_current_for_user` / `organization_scope_predicate` 三个工具在多个 router 复用，**这是后端目前最值得保留的"分层雏形"**。
3. 审计链：每条事件 HMAC + 序号 + 前序哈希 + 链头锚定（`audit_integrity.py`）。
4. 文件加密：版本化 AES-GCM + Legacy EAIF1 兼容 + 原子轮换 + 备份证据。
5. 任务租约：`Job` + `JobAttempt` + lease_token + heartbeat + 死信；`recover_expired_leases` / `_finish_permanent_failure` / `_finish_unexpected_failure` 三个收口函数。
6. 幂等：`Idempotency-Key` 头 + 唯一索引 + 同事务回放。
7. 配置：`Pydantic Settings` + `model_validator` 启动护栏（防 Demo 密钥/明文密码在生产中启动）。
8. Docker Compose 双网络、`no-new-privileges`、cap_drop ALL、tmpfs、secret 注入。
9. Alembic 单一 head + 备份迁移兼容性校验。

### 1.4 真正的痛点

#### 1.4.1 前端

- `app/page.tsx`（Demo）与 `app/production/production-workspace.tsx`（生产）**几乎重复实现两遍**，没有任何共享抽象。
- 没有数据获取层：所有请求散落在 `useCallback` 中，错误处理不一致，**无缓存/失效/重试**。
- 没有组件抽象：表单、弹窗、确认框在每个调用点手写（**视觉风格问题不在本次范围**）。
- i18n 通过组件内硬编码 `copy[language]` 三套字典，**没有命名空间、没有 ICU**。
- 状态管理全是 `useState`，**单个组件持有 20+ 状态**。
- 演示数据 `prototype-data.ts` 与生产代码物理共存。
- `api-client.ts` 把 CSRF/Idempotency/错误格式化绑死，**没有拦截器、retry、dedupe**。
- 与后端类型**双轨维护**，schema 漂移难发现。

#### 1.4.2 后端

- **没有 service 层**：router 函数自己处理 ORM、事务、审计、idempotency、回包持久化。重复 5 行模板在 9 个 router 出现 100+ 次。
- **没有 repository 层**：所有 SQL 用 `select()` 散落 router，无公共查询构造器。
- **`models.py` 600+ 行**：14 个 ORM 模型在一处。
- **`schemas.py` 330+ 行**：Pydantic 模型扁平堆放，输入/输出/分页/审计未分文件。
- **`authz.py` 偏胖**：300+ 行同时承担 principal 加载、CSRF、角色守卫、范围判定、范围快照、范围谓词、范围守门；CSRF 不属于"授权"。
- **错误码不统一**：`AppError(code="xxx")` 是字符串，无枚举、无 SDK 共享。
- **ORM 与 Pydantic 直接互转**：`UserOut.model_validate(user)` 整体序列化，敏感字段外泄风险。
- **数据库会话生命周期混乱**：路由 `db: Session` 依赖注入，但 audit、scope snapshot、idempotency 又要自己 commit。
- **Worker `main.py` 514 行**：轮询、租约、心跳、错误分类、占位写入、业务 handler 注册混在一个文件。
- **没有 DTO/Mapper**：ORM 字段直接成为 API 出参。
- **没有领域事件总线**：`Job` 表承担所有异步任务，`payload_json` + `job_type` 字符串路由，**没有 schema**。
- **没有缓存层**：审计验证、Session 加载、事业部解析每次都打 DB。
- **没有 OpenAPI 客户端**：FastAPI 暴露 `/api/openapi.json`，但前端不用。
- **没有 metrics / tracing**：仅有 `JsonFormatter`，无 OTel 接入。

#### 1.4.3 跨端

- 前后端类型双轨：`app/production/types.ts` 和 `services/api/src/.../schemas.py` 各自维护。
- 错误协议不一致：后端 `{error:{code,message,request_id,details}}`，前端 `ApiError{name,status,code,requestId,details}`。
- 缺乏 **Capability 探测**：ADR 已经明确"未配置能力必须明确返回'尚未配置'"，但**目前没有结构化通道**把它传到前端。
- 缺乏合同测试、E2E / 集成测试、脚本单测。
- 顶层 Makefile 简单；CI 平台未固化。
- `tsconfig.json` 用 `target: ES2017`，与 React 19 + Node 22 不匹配。

### 1.5 后端配置分散点（本次重点）

当前配置在 **5 个地方**重复定义：

| 配置事实 | 出现位置 | 问题 |
| --- | --- | --- |
| Session/CSRF/审计/文件加密密钥 | `runtime/<env>/secrets/*` + compose `secrets:` | 命名 / 路径约束散落 |
| 数据库连接 | `compose.yml` `POSTGRES_*` + `Settings.database_url` | URL 拼接在两处，bug 风险 |
| Cookie 策略 | compose `COOKIE_SECURE` + `SESSION_COOKIE_SAMESITE` + `Settings` | 字段名不一致（`COOKIE_SECURE` vs `SESSION_COOKIE_SECURE`） |
| Worker 调度参数 | compose `WORKER_*` + `Settings.worker_*` | 默认值不一致时无强校验 |
| API 路径前缀 | `Settings.api_prefix` + 各 router | 仅一处，但**未在 compose / OpenAPI 中显式声明** |
| Demo 守护（禁止种子/默认密钥） | `Settings.validate_environment_guards` + compose `APP_ENV` + `seed_demo` | 三处必须同时正确才能保证不漏 |
| CORS / TrustedHost | `Settings.allowed_origins` / `trusted_hosts` + Nginx 配置 | 端口 8080/8180/3000 关系靠人工 |
| 启动期数据库迁移版本 | `routers/health.py` `EXPECTED_DATABASE_REVISION` | **硬编码字符串**，未与 alembic 联动 |

本次重构要求：**单一事实源 + 启动期强校验**。

---

## 2. 重构目标

把现在的"两个 demo + 一个生产底座"演进成 **一个可演进的产品形态**：

1. **顶层分离**：`frontend/` 与 `backend/` 两个独立子树，各自的部署 / Docker / 配置 / 依赖管理 / 测试 / CI。
2. **前端**：只做**结构拆分 + 数据层 + 类型共享 + 错误协议**；**页面视觉、布局、设计系统全部下一次处理**。
3. **后端**：清晰分层（Router → Service → Repository → Domain），领域化拆分，统一错误协议，统一配置管理，可观测性。
4. **跨端**：OpenAPI → 自动生成前端类型；统一错误码表；统一可观测性字段。
5. **工程**：monorepo 工具（一键开发/CI/部署）；脚本用 Make 编排 + 关键路径加 Bats 单元测试。

---

## 3. 目标架构

### 3.1 顶层目录（`backend/` 与 `frontend/` 分离）

```
executive-ai-secretary/
├── backend/                          # 全部后端代码（替换 services/）
│   ├── src/
│   │   └── api/         # 详见 §3.3
│   ├── src/worker/                   # 任务 worker（合并入 backend，详见 §4.5）
│   ├── tests/
│   ├── alembic/
│   ├── alembic.ini
│   ├── pyproject.toml                # uv-managed
│   ├── uv.lock
│   ├── Dockerfile
│   ├── deploy/                       # 后端专属部署资产
│   │   ├── compose/
│   │   │   ├── docker-compose.yml
│   │   │   ├── docker-compose.customer.yml
│   │   │   └── conf.d/
│   │   ├── postgres/
│   │   │   ├── ensure-runtime-role.sh
│   │   │   ├── backup-entrypoint.sh
│   │   │   └── …
│   │   ├── nginx/                    # 反向代理：仅由后端 compose 引用
│   │   │   ├── nginx.conf
│   │   │   └── conf.d/default.conf
│   │   └── environments/
│   │       ├── local-demo.env.example
│   │       ├── customer-template.env.example
│   │       └── production.env.example
│   ├── configs/                      # 配置单一事实源（详见 §4.6）
│   │   ├── schema.py                 # Pydantic 配置 schema（含启动护栏）
│   │   ├── loader.py
│   │   ├── profile.<env>.yaml        # 每个环境的可公开配置
│   │   ├── secrets.schema.yaml       # secret 文件名 / 路径 / 权限 schema
│   │   └── README.md
│   ├── scripts/                      # 后端专属脚本
│   │   ├── seed-demo.sh
│   │   ├── backup.sh
│   │   ├── restore.sh
│   │   ├── rotate-file-keys.sh
│   │   └── verify-release-bundle.sh
│   └── docs/
│       ├── operations.md
│       └── env-matrix.md
│
├── frontend/                         # 全部前端代码（替换 app/、build/、db/、drizzle/、deploy/web-server.mjs）
│   ├── app/                          # Next.js App Router 入口（保留 RSC 能力）
│   │   ├── (auth)/login/
│   │   ├── (workspace)/
│   │   │   ├── home/
│   │   │   ├── chat/[conversationId]/
│   │   │   ├── projects/[projectId]/
│   │   │   ├── memory/
│   │   │   ├── history/
│   │   │   └── settings/
│   │   ├── layout.tsx
│   │   └── page.tsx                  # 单一入口（替换双 page 切换）
│   ├── src/
│   │   ├── components/               # 拆细的展示组件（**不动视觉**）
│   │   │   ├── primitives/           # 与设计系统无关的纯拆分
│   │   │   └── business/             # AnswerCard / MetricGrid / SectionList / FileChip …
│   │   ├── features/                 # 业务切片（每个切片：数据 hook + UI）
│   │   │   ├── auth/
│   │   │   ├── conversations/
│   │   │   ├── projects/
│   │   │   ├── files/
│   │   │   ├── memories/
│   │   │   ├── reports/
│   │   │   └── bootstrap/
│   │   ├── data/                     # 数据层
│   │   │   ├── api-client.ts         # 拦截器：retry、CSRF、Idempotency、错误归一
│   │   │   ├── query-client.ts       # TanStack Query
│   │   │   └── errors.ts             # 错误码枚举
│   │   ├── auth/                     # Session / Route Guard
│   │   ├── state/                    # Zustand：仅 UI 临时态
│   │   ├── i18n/                     # i18next + ICU（仅结构，**不替换文案**）
│   │   ├── runtime/                  # appMode 解析（替换 runtime.mjs）
│   │   ├── styles/                   # 整体平移现有 globals.css，**原样不动**
│   │   └── types/                    # OpenAPI 自动生成 + 内部类型
│   ├── public/                       # 资源文件
│   ├── deploy/                       # 前端专属部署资产
│   │   ├── nginx/                    # SPA 静态资源服务（仅在生产 compose 中使用）
│   │   ├── web-server.mjs            # 平移原 deploy/web-server.mjs
│   │   └── environments/
│   │       ├── local-demo.env.example
│   │       └── production.env.example
│   ├── scripts/
│   │   ├── assert-production-artifact.mjs
│   │   └── export-openapi.mjs
│   ├── next.config.ts
│   ├── vite.config.ts                # 保留 vinext 适配
│   ├── tsconfig.json
│   ├── package.json
│   ├── package-lock.json
│   ├── postcss.config.mjs
│   ├── eslint.config.mjs
│   ├── Dockerfile.web
│   └── README.md
│
├── shared/                           # 跨前后端的"零依赖"共享
│   ├── api-contracts/                # OpenAPI schema + 生成的 TS 类型 + 错误码枚举
│   │   ├── openapi.json              # 由 backend 脚本生成
│   │   ├── errors.ts                 # codegen 后的 ErrorCode 枚举
│   │   └── types.gen.ts              # codegen 后的请求/响应类型
│   ├── domain/                       # 跨前后端的领域常量、状态机定义
│   │   ├── roles.ts
│   │   ├── job-status.ts
│   │   └── message-status.ts
│   └── docs/                         # 跨端共享的 API 文档
│       └── openapi-usage.md
│
├── docs/                             # 项目级 ADR / 运维 / 设计（保留并扩展）
│   ├── architecture/
│   ├── production/
│   └── releases/
│
├── scripts/                          # 项目级编排脚本
│   ├── lib/runtime.sh
│   ├── compose.sh                    # 改为调 backend/deploy/compose/
│   ├── prepare-env.sh
│   ├── start.sh
│   ├── stop.sh
│   ├── status.sh
│   ├── smoke-test.sh
│   ├── test-infra.sh
│   └── lib/
│
├── Makefile                          # 顶层入口（详见 §3.5）
├── README.md
├── .gitignore
├── .editorconfig
├── .nvmrc                            # Node 22.13+
├── .python-version                   # Python 3.12+
└── package.json                      # 顶层仅 devDeps：prettier、bats 触发器等
```

**目录迁移对应表**：

| 现状 | 目标 |
| --- | --- |
| `app/` | `frontend/app/` + `frontend/src/`（拆分） |
| `app/production/` | `frontend/src/features/` + `frontend/src/data/` + `frontend/src/auth/` |
| `app/globals.css` | `frontend/src/styles/globals.css`（**原样不动**） |
| `app/prototype-data.ts` | 删除；其内容迁移到 `backend/src/api/seed/sanitized_fixtures.py` |
| `build/sites-vite-plugin.ts` | `frontend/scripts/sites-vite-plugin.ts` 或并入 `vite.config.ts` |
| `db/`, `drizzle/` | 删除（Drizzle 在生产中未启用） |
| `services/api/` | `backend/src/api/` |
| `services/worker/` | `backend/src/worker/`（合并入同一 Python 包） |
| `deploy/nginx/` | `backend/deploy/nginx/`（API / Web 共用反代） |
| `deploy/postgres/` | `backend/deploy/postgres/` |
| `deploy/environments/` | `backend/deploy/environments/` |
| `deploy/web-server.mjs` | `frontend/deploy/web-server.mjs` |
| `scripts/` | 顶层保留编排（`compose.sh`、`smoke-test.sh` 等），`backend/scripts/` 放后端专属 |
| `docs/` | 保留根目录 |

### 3.2 前端目标架构（**不动视觉**）

```
frontend/
├── app/                              # Next.js App Router（保留 RSC 能力）
├── src/
│   ├── components/                   # 拆细的展示组件（**复用现有 CSS 类名**）
│   │   ├── primitives/               # 不带视觉风格的纯拆分
│   │   └── business/                 # AnswerCard / MetricGrid / SectionList / FileChip
│   ├── features/                     # 业务切片（每个切片：数据 hook + UI）
│   │   ├── auth/                     # 登录/会话/改密/Session 心跳
│   │   ├── conversations/            # 会话 + 消息 + 任务
│   │   ├── projects/                 # 项目 CRUD
│   │   ├── files/                    # 上传/下载/解析状态
│   │   ├── memories/                 # 长期记忆
│   │   ├── reports/                  # 简报
│   │   └── bootstrap/                # 启动态探测
│   ├── data/                         # 数据层
│   │   ├── api-client.ts             # 拦截器：retry、CSRF、Idempotency、错误归一
│   │   ├── query-client.ts           # TanStack Query
│   │   └── errors.ts                 # 错误码枚举
│   ├── auth/                         # Session / Route Guard
│   ├── state/                        # Zustand 仅 UI 临时态
│   ├── i18n/                         # i18next（仅结构，**不替换现有 copy[language] 文案**）
│   ├── runtime/                      # appMode 解析（替换 runtime.mjs）
│   ├── styles/                       # 整体平移 globals.css，**原样不动**
│   └── types/                        # OpenAPI 自动生成 + 内部类型
└── …
```

**关键选型**：

| 关注点 | 选型 | 备注 |
| --- | --- | --- |
| 数据获取 | TanStack Query v5 | 替代散落的 useCallback + fetch |
| 表单 | React Hook Form + Zod | 仅用于新增/修改；现有表单渐进迁移 |
| 状态 | Zustand（仅 UI 临时态） | 业务态仍用 TanStack Query |
| 类型 | `openapi-typescript` + `openapi-zod` | 与后端 OpenAPI 同步 |
| 错误 | `ErrorCode(StrEnum)` 共享 | 后端定义，前端 codegen |
| 路由 | Next.js App Router | 与现有 RSC 兼容 |

**本次明确不动**：

- `frontend/src/styles/globals.css` 整体平移，**原样保留**（颜色 token、字体、间距、阴影、按钮样式）
- `frontend/app/page.tsx` 与 `frontend/app/production/production-app.tsx` 的**视觉**部分不重构（仅做组件/hook 拆分）
- 演示态（`app/page.tsx` + `prototype-data.ts`）改为一个**开关**而非两份代码：保留 `app/demo/`，运行时根据 `appMode === "demo"` 渲染；删除 Docker build 阶段对 `app/page.production.tsx` 的覆盖
- 不引入设计系统、不引入组件库替换现有 UI
- i18n 仅做**结构接入**（命名空间拆分），不替换文案、不替换命名、不引入 ICU
- 主题（light/dark）与 ProfilePreferences 行为不变

### 3.3 后端目标架构（Clean-ish 三层 + 领域）

```
backend/src/api/
├── main.py                           # 仅 FastAPI app 装配 + lifespan
├── core/
│   ├── config.py                     # 委托给 backend/configs/schema.py
│   ├── errors.py                     # AppError + ErrorCode 枚举 + 错误→HTTP 映射
│   ├── logging.py                    # 结构化日志 + OTel 接入点
│   ├── db.py                         # engine、SessionLocal、依赖注入
│   ├── security/                     # 拆分原 security.py
│   │   ├── password.py
│   │   ├── session.py
│   │   ├── csrf.py
│   │   └── rate_limit.py
│   ├── time.py
│   ├── pagination.py
│   ├── idempotency.py
│   ├── http.py                       # 通用依赖（get_db/get_settings/get_principal）
│   └── observability/                # metrics/tracing
├── domain/                           # 领域层：与框架无关
│   ├── identity/                     # User, Enterprise, OrgUnit, DataScopeGrant, Session
│   ├── knowledge/                    # Conversation, Message, Project, File, Memory
│   ├── reporting/                    # Report, ReportVersion
│   ├── jobs/                         # Job, JobAttempt, JobLifecycle（FSM）
│   ├── audit/                        # AuditEvent, AuditChain, AuditSigner
│   ├── storage/                      # Storage, KeyRing, EncryptedObject
│   └── admin/                        # Capability / FeatureFlag
├── repositories/                     # 数据访问：纯 SQLAlchemy，无业务
├── services/                         # 业务服务：编排 + 事务
├── routers/                          # FastAPI 路由：仅 HTTP 解析 + 调 service（≤ 30 行）
├── schemas/                          # Pydantic 入参/出参
├── workers/                          # 异步任务（替换 services/worker）
│   ├── __init__.py
│   ├── runtime.py                    # 轮询、lease、heartbeat
│   ├── handlers/
│   │   ├── assistant_response.py     # 留接口
│   │   ├── file_extract.py           # 留接口
│   │   ├── report_generate.py        # 留接口
│   │   ├── system_noop.py            # 已存在
│   │   └── base.py                   # JobHandler 协议
│   └── registry.py                   # job_type → handler 映射
├── cli/                              # argparse 子命令
└── seed/                             # 演示数据（隔离于生产代码路径）
```

**核心原则**：

1. **Router ≤ 30 行**：只做参数解析、调 service、回包。**禁止 router 直接 `db.add`、直接 `record_audit`、直接 commit**。
2. **Service 拥有事务边界**：`with session.begin(): ...` 在 service 内部；service 不返回 ORM，**只返回 domain 对象或 schema**。
3. **Repository 纯 CRUD**：返回 ORM 或标量，不做权限判断。
4. **Domain 模型与 ORM 解耦**：domain 用 `dataclass` 或 Pydantic（不依赖 SQLAlchemy），由 `mappers` 转换；ORM 仅作持久化细节。
5. **错误码用枚举**：`ErrorCode(StrEnum)` 全局唯一，前后端共享。
6. **审计/限流/幂等用装饰器/中间件**。
7. **Worker 是 service 的消费者**：通过 `JobService.enqueue` 入队，handler 内部仍然调 service 完成实际工作；**handler 不再直接操作 DB**。

### 3.4 跨端契约

- OpenAPI schema 由 FastAPI 自动生成；`frontend/scripts/export-openapi.mjs` 启动时或 CI 中执行，落到 `shared/api-contracts/openapi.json`。
- `shared/api-contracts` 用 `openapi-typescript` 生成 `types.gen.ts`，用 `openapi-zod` 生成 Zod schema。
- 错误码枚举从后端 Python `StrEnum` 自动生成前端 `errors.ts`。
- `Idempotency-Key`、`X-CSRF-Token`、`X-Request-ID` 在前端 API 客户端拦截器统一注入。
- `request_id` 跨前后端串联：前端从响应头读取，纳入日志/错误展示。

### 3.5 顶层 Makefile（统一入口）

```makefile
# 顶层入口，分 backend/ 与 frontend/ 子 makefile
install:        ; ./scripts/install.sh        # pnpm install + uv sync
lint:           ; $(MAKE) -C backend lint && $(MAKE) -C frontend lint
typecheck:      ; $(MAKE) -C backend typecheck && $(MAKE) -C frontend typecheck
test:           ; $(MAKE) -C backend test && $(MAKE) -C frontend test
e2e:            ; ./scripts/e2e.sh           # Playwright 跨端
up:             ; ./scripts/start.sh $(ENV)   # 调 backend/deploy/compose
down:           ; ./scripts/stop.sh $(ENV)
status:         ; ./scripts/status.sh $(ENV)
smoke:          ; ./scripts/smoke-test.sh $(ENV)
backup:         ; ./scripts/backup.sh $(ENV)
restore:        ; ./scripts/restore.sh $(ENV)
config:         ; ./scripts/compose.sh $(ENV) config
contracts:      ; $(MAKE) -C frontend contracts   # 拉后端 OpenAPI 生成前端类型
```

---

## 4. 关键设计决策

### 4.1 后端配置统一（本次重点）

**目标**：所有运行时配置**单点定义 + 强校验**，删除 5 个事实源，删除 4 处硬编码。

**目录**：

```
backend/configs/
├── schema.py                 # Pydantic：所有可调环境变量 + secret 文件约束
├── loader.py                 # 从 yaml + env + secret 文件合并为 Settings
├── profile.local-demo.yaml
├── profile.customer-template.yaml
├── profile.production.yaml
├── secrets.schema.yaml       # secret 文件名 / 路径 / 权限（mode 0o600 等）
├── alembic-revision.txt      # 由 alembic 脚本生成；健康检查读取
└── README.md
```

**schema.py 示例结构**：

```python
class DatabaseConfig(BaseModel):
    host: str
    port: int = 5432
    runtime_user: str
    runtime_password_file: Path
    backup_user: str
    backup_password_file: Path
    migrator_user: str
    migrator_password_file: Path
    name: str
    pool_size: int = 10
    max_overflow: int = 20

class CookieConfig(BaseModel):
    secure: bool
    samesite: Literal["lax", "strict", "none"]
    session_name: str = "exec_session"
    csrf_name: str = "exec_csrf"

class WorkerConfig(BaseModel):
    poll_seconds: float
    lease_seconds: int
    heartbeat_seconds: int
    job_max_attempts: int
    retry_base_seconds: float
    retry_max_seconds: float

class ApiConfig(BaseModel):
    prefix: str = "/api/v1"
    cors_allowed_origins: list[str]
    trusted_hosts: list[str]
    expected_alembic_revision: str  # 由 alembic 脚本生成

class ProfileConfig(BaseModel):
    env: Literal["local-demo", "customer-template", "production", "test", "development"]
    mode: Literal["demo", "production"]
    seed_demo_data: bool
    debug: bool

class AppConfig(BaseModel):
    profile: ProfileConfig
    database: DatabaseConfig
    cookie: CookieConfig
    worker: WorkerConfig
    api: ApiConfig
    secrets: SecretsConfig
    # ... 启动护栏由 model_validator 统一
```

**事实源替换**：

| 之前的事实源 | 替换为 |
| --- | --- |
| `compose.yml` 中 `POSTGRES_HOST` 等环境变量 | `backend/configs/profile.<env>.yaml` + schema |
| `compose.yml` 中 `COOKIE_SECURE` / `SESSION_COOKIE_SAMESITE` | `CookieConfig.secure` / `samesite` |
| `compose.yml` 中 `WORKER_*` | `WorkerConfig.*` |
| `routers/health.py` 硬编码 `EXPECTED_DATABASE_REVISION = "c5d91f4a8b72"` | `ApiConfig.expected_alembic_revision`，由 `scripts/generate-configs.sh` 在迁移 head 变化时重新生成 |
| `Settings.allowed_origins` / `trusted_hosts` | `ApiConfig.cors_allowed_origins` / `trusted_hosts` |
| `Settings.validate_environment_guards` | 拆分到 `ProfileConfig` 与 `DatabaseConfig` 的 `model_validator` |

**启动护栏**：

- `AppConfig.model_validator(mode="after")` 统一做"生产环境拒绝默认密钥/演示种子/Debug" 等所有护栏。
- 容器入口（`backend/Dockerfile`）第一步执行 `python -m api.configs.loader --validate`，失败直接拒绝启动。
- `compose.yml` 改为通过 `env_file: backend/deploy/environments/<env>.env` 注入，**不再在 compose 顶层定义业务环境变量**。

### 4.2 错误协议

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `error.code` | `ErrorCode(StrEnum)` | 机器可读，全局唯一 |
| `error.message` | string | 用户可读，可本地化 |
| `error.request_id` | string | 与后端日志关联 |
| `error.details` | object \| null | 结构化补充（如字段错误列表） |
| `error.docs_url` | string \| null | 指向内部文档的链接 |

错误码示例（节选）：

```
auth.invalid_credentials / auth.session_expired / auth.csrf_failed
auth.password_change_required / auth.rate_limited
resource.not_found / resource.forbidden / resource.conflict / resource.validation_error
scope.forbidden
job.not_found / job.not_cancelable / job.expired
file.too_large / file.unsupported_type / file.integrity_error / file.key_unavailable
audit.chain_invalid
internal.unexpected
integration.not_configured   # 第一阶段专有：未配置的能力
```

### 4.3 数据层（前端）

- **TanStack Query** 替代散落的 `useCallback + fetch`。
- **错误码枚举** 替代 `ApiError.code` 字符串。
- **拦截器** 在 `api-client.ts` 注入 CSRF/Idempotency/Request-ID。
- **SWR 语义**：默认 `staleTime: 30s`；关键页用 `prefetchQuery` 在 RSC 预取。

### 4.4 状态管理

- **Zustand**（仅 UI 临时态）：侧栏、菜单、主题、Toast、ProfilePreferences。
- **业务态**：全部交给 TanStack Query。
- 不引入 Redux / Redux Toolkit / Jotai。

### 4.5 任务与可配置能力

`Job.job_type` 仍是字符串，但由 `workers/registry.py` 做注册表 + schema 校验：

```python
class JobHandler(Protocol):
    job_type: str
    payload_schema: type[BaseModel]
    def handle(self, ctx: JobContext) -> JobResult: ...
```

未注册的 `job_type` 会被 `enqueue` 阶段直接拒绝（**而不是被 worker 抛 `integration_not_configured` 才发现**）。

Worker **合并入** `backend/src/worker/`，单仓库多 Python 进程，部署阶段仍可拆为独立容器（同一镜像不同 `SERVICE_ROLE=worker`）。

### 4.6 权限模型

`authz.py` 拆为：

- `core/security/`：密码、Session 令牌、CSRF
- `core/auth/principal.py`：`Principal` 数据类 + `get_current_principal`、`get_executive_principal`、`require_roles`
- `core/auth/scope.py`：`accessible_organization_unit_ids`、`assert_org_scope`、`build_scope_snapshot`、`scope_snapshot_is_current_for_user`、`organization_scope_predicate`
- `core/auth/csrf.py`：`csrf_protect` 依赖

业务侧使用：

```python
@router.post("/conversations", response_model=ConversationOut)
def create_conversation(
    payload: ConversationCreate,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
):
    return service.create(payload=payload)
```

权限检查在 service 内部首行执行，**而不是在 router**。

### 4.7 不在本 ADR 范围

- 前端视觉与设计系统（用户明确要求本次不动）
- 真实 Hermes/MCP/数据接入实现
- 飞书推送与主动简报
- 离线安装包
- 多租户
- 替换 vinext

---

## 5. 重构路线图

> **原则**：每步独立合并、部署、回滚；**不引入 big-bang 切换**。每阶段结束 `make smoke` 与 `make test` 全绿；现有 11 个 pytest + 3 个 worker pytest 不得回归。

### Phase 0：目录分离 + 工程底盘（1.5 周）

1. 顶层目录重排：建立 `backend/`、`frontend/`、`shared/` 三个子树，**功能不变，目录变更**。
2. `frontend/` 平移：
   - `app/`, `build/`, `db/`, `drizzle/`, `deploy/web-server.mjs`, `Dockerfile.web`, `next.config.ts`, `vite.config.ts`, `tsconfig.json`, `package.json`, `eslint.config.mjs`, `postcss.config.mjs` 原样迁入。
   - `globals.css` 整体迁入 `frontend/src/styles/globals.css`，**原样不动**。
3. `backend/` 平移：
   - `services/api/` → `backend/src/api/`
   - `services/worker/` → `backend/src/worker/`
   - `deploy/postgres/`、`deploy/nginx/`、`deploy/environments/` → `backend/deploy/`
4. `shared/` 初始空架子（`api-contracts/`、`domain/`）。
5. 顶层 `Makefile`：
   - `make install` / `make lint` / `make typecheck` / `make test` / `make e2e` / `make up` / `make down` / `make smoke` / `make backup` / `make restore` / `make release` / `make contracts`
6. 顶层脚本：`scripts/compose.sh`、`scripts/start.sh`、`scripts/smoke-test.sh` 等调 `backend/deploy/compose/`。
7. 给所有 bash 脚本加 Bats 单元测试（happy path + 3 个失败分支）。
8. 添加 `engines` 字段锁定 Node 22.13+ / Python 3.12+。

**完成定义**：

- `make install && make lint && make test && make typecheck` 一次通过
- `make up && make smoke` 复现第一阶段全部行为
- `frontend/Dockerfile.web` 仍能正常构建；`backend/Dockerfile` 仍能正常构建
- CI 流水线绿

### Phase 1：后端配置统一（1.5 周，本次重点）

1. 建立 `backend/configs/`（schema.py / loader.py / profile.*.yaml / secrets.schema.yaml）。
2. `Settings` 重写为 `AppConfig`，**所有环境变量从 `backend/configs/` 单一事实源加载**。
3. 删除 `compose.yml` 中所有业务环境变量定义，改为 `env_file:` 指向 `backend/deploy/environments/<env>.env`。
4. `routers/health.py` 的 `EXPECTED_DATABASE_REVISION` 改为读 `ApiConfig.expected_alembic_revision`（由 `scripts/generate-configs.sh` 在 head 变化时自动写回）。
5. **启动护栏统一**到 `AppConfig.model_validator`，删除分散在 `Settings` 内的护栏。
6. 容器入口 `exec` 前置 `python -m api.configs.loader --validate`。
7. 写 `backend/configs/README.md` 列出"如何新增环境变量 / 改默认"流程。
8. `backend/scripts/check-config-drift.sh`：扫描 `compose.yml` 中残留业务环境变量，CI 阶段失败即拒绝合并。

**完成定义**：

- `backend/deploy/environments/<env>.env` 与 `backend/configs/profile.<env>.yaml` 字段一致
- `compose.yml` 不再含业务环境变量（仅 `COMPOSE_PROJECT_NAME` 等 Compose 元变量）
- 11 个 pytest 全绿
- 新增 `tests/test_config_validation.py` 覆盖 6 条护栏分支

### Phase 2：跨端契约（1 周）

1. 后端 `core/errors.py` 引入 `ErrorCode(StrEnum)`。
2. 全部 `AppError(code="xxx")` → `AppError(code=ErrorCode.xxx)`。
3. 错误响应增加 `error.docs_url`。
4. `backend/scripts/export_openapi.py`：导出 `shared/api-contracts/openapi.json`。
5. `frontend/scripts/codegen-types.mjs`：`openapi-typescript` + `openapi-zod` 生成 TS 与 Zod 类型。
6. 前端 `data/errors.ts`：从 `shared/api-contracts/errors.ts` 引入；`data/api-client.ts` 拦截器改造。
7. `request_id` 串联：前端拦截器把 `X-Request-ID` 写入 store。

**完成定义**：

- 现有 11 个 pytest 全部通过
- 新增 `tests/test_error_codes.py` 覆盖所有 ErrorCode
- `make contracts` 在 CI 流水线中跑通

### Phase 3：前端结构拆分（**不动视觉**）（3 周）

按切片分次提交，每片一个 PR：

1. **数据层骨架**（0.5 周）：
   - 引入 TanStack Query
   - `data/api-client.ts` 拦截器（CSRF/Idempotency/Request-ID/retry/错误归一）
   - `data/query-client.ts` + query keys 工厂
2. **components 拆细**（1 周）：
   - 把 `production-workspace.tsx` 中的展示组件按职责抽到 `components/business/`
   - **复用现有 CSS 类名**；**不改任何样式**
   - 拆出 `AnswerCard`、`MetricGrid`、`SectionList`、`FileChip`、`Toast`、`ConfirmDialog` 等
3. **features 切片**（1 周）：
   - `features/auth/`（login / change-password / session / heartbeat）
   - `features/conversations/`（list / get / send / pin / archive / messages 流）
   - `features/projects/`、`files/`、`memories/`、`reports/`、`bootstrap/`
4. **App Router 拆分**（0.5 周）：
   - `frontend/app/(auth)/login/`
   - `frontend/app/(workspace)/home/`, `chat/[conversationId]/`, `projects/[projectId]/`, `memory/`, `history/`, `settings/`
   - i18next 接入（**仅结构**，不替换现有 copy[language]）
   - `app/page.tsx` 与 `app/page.production.tsx` 合并为单 `app/page.tsx` + `appMode` 开关
   - 删除 `app/prototype-data.ts`、`app/production/runtime.mjs`

**完成定义**：

- `production-workspace.tsx` 长度下降到 ≤ 400 行（仅"页面装配 + 路由 + 全局 Provider"）
- 单个组件文件 ≤ 250 行
- 视觉、布局、CSS 100% 与现状一致（人工对比 + 视觉回归）
- 新增组件单测 + Playwright 关键路径
- 演示态（Demo 模式）单独走 `app/demo/`，构建时不再覆盖 page.tsx

### Phase 4：后端分层改造（3 周）

按领域逐个迁移：

1. **identity 域**（1 周）：`domain/identity/`、`repositories/identity_repo.py`、`services/auth_service.py`；迁移 `routers/auth.py`。
2. **knowledge 域**（1 周）：`conversations` / `projects` / `files` / `memories` 全部迁到 service；ORM ↔ domain mappers。
3. **reporting / jobs / admin / audit / storage**（1 周）：
   - 统一 storage 抽象（保留 `LocalEncryptedStorage` 作为实现）
   - 引入 `JobHandler` 协议与 registry
   - Worker 改造为 `workers/runtime.py` + `workers/handlers/*`
   - `audit_integrity.py` 收口到 `domain/audit/`

**完成定义**：

- 每个 router ≤ 30 行
- `pytest -q` 全绿；service 单测覆盖业务分支 ≥ 70%
- `ruff check .` 与 `mypy` 干净

### Phase 5：可观测性（1 周）

1. OpenTelemetry SDK 接入。
2. `/metrics` 暴露 Prometheus 指标。
3. 前端 `request_id` 透传 + 错误上报接口。
4. `tsconfig.base.json` 升级 `target: ES2022`、`strict: true`、`noUncheckedIndexedAccess: true`。
5. `vitest` + `playwright` + `bats` 引入。

### Phase 6：演进接口（1 周，留作第二阶段）

1. `backend/src/integrations/` 留目录 + 空协议（Hermes/MCP 适配器）。
2. `backend/src/scheduler/` 留目录（cron / 主动简报触发器）。
3. `frontend/admin/` 留目录（管理层 SPA）。
4. `domain/admin/capability.py` 实现 `FeatureFlag` 数据模型与查询接口。

---

## 6. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
| --- | --- | --- | --- |
| 大改动破坏现有安全契约 | 中 | 高 | Phase 1 之前**绝不动** `core/security/`、`audit_integrity.py`、`storage.py`；每阶段结束 `make smoke` 必须通过 |
| Router 改写时遗漏 `assert_org_scope` 导致越权 | 中 | 高 | `assert_org_scope` 改为 service 内部第一行；新增 `tests/postgres_authorization_matrix.py` 覆盖 10 个越权场景 |
| TanStack Query 引入导致首屏变慢 | 低 | 中 | 默认 `staleTime: 30s`、关键页用 `prefetchQuery` 在 RSC 预取 |
| OpenAPI 生成类型与手写类型冲突 | 中 | 低 | 阶段 2 之前**不删** 手写 types.ts；新类型作为 alias 并存；阶段 3 才删除手写版本 |
| pnpm workspace 与现有 npm scripts 冲突 | 中 | 中 | 顶层 `package.json` 的 `dev/build/test` 入口保持；内部用 `pnpm -r` |
| Alembic 迁移与新 ORM 字段不一致 | 中 | 高 | 阶段 4 改 ORM 时只增字段、绝不删字段；新增字段默认 `nullable=True` 或带 server default |
| 旧 Demo 前端误回退 | 低 | 高 | `Dockerfile.web` 删除 `cp app/page.production.tsx app/page.tsx`；CI 阶段扫描构建产物包含 `prototype-data` 字符串即失败 |
| `vinext` 升级破坏生产启动 | 低 | 高 | 锁定 `vinext@0.0.50`；升级走独立 PR + 完整 e2e |
| Bash 脚本重写引入回滚风险 | 中 | 中 | 用 `bats` 单元测试覆盖所有 happy path；保留旧脚本 `*.legacy.sh` 一版本 |
| 配置集中后误删环境变量 | 中 | 高 | `backend/scripts/check-config-drift.sh` 在 CI 扫描 `compose.yml` 残留业务环境变量 |
| 前后端目录分离后 Docker 网络错配 | 中 | 中 | `backend/deploy/compose/` 引用 `frontend/deploy/nginx/` 显式路径；`make up` 前先 `make config` 校验 |

---

## 7. 验证与回归

每个阶段必须通过的最小回归集：

- `make lint && make typecheck && make test`：全绿。
- `make e2e`：登录 / 改密 / 创建会话 / 发送消息 / 上传文件 / 创建项目 / 创建记忆 / 创建报告 / 创建事业部 / 撤销 Session / 审计验证。
- `make security:scan`：依赖审计 + 密钥扫描 + 容器漏洞扫描。
- 越权测试矩阵：来自 ADR 0003 的 10 个场景。
- 备份演练：至少一次"破坏性恢复"全流程通过。
- **视觉回归**（仅前端阶段 3）：Playwright `expect(page).toHaveScreenshot()` 关键页面。

---

## 8. 文档与 ADR 更新

重构推进时同步更新：

- 本文件 0004：本 ADR 永久保留
- 新增 0005：后端分层与目录
- 新增 0006：前端结构拆分（**不动视觉**）
- 新增 0007：跨端类型与错误协议
- 新增 0008：后端配置统一（`backend/configs/`）
- 替换 `docs/production/` 下"组件说明"为新结构索引

---

## 9. 评审要点

需要决策的开放问题（请在评审时给出意见）：

1. **顶层目录名**：`backend/` + `frontend/` 是否可接受？还是希望 `services/backend/` + `apps/frontend/` 这样的更深嵌套？
2. **Worker 合并**：是否同意把 `services/worker/` 合并进 `backend/src/worker/`，**同一 Python 包、同一镜像、不同 SERVICE_ROLE**？还是保留独立包（独立 pyproject、独立部署）？
3. **配置 schema 位置**：`backend/configs/`（与代码共存）还是 `config/`（项目根）？当前 ADR 倾向 `backend/configs/`，因为与运维相关的资源都收在 `backend/deploy/` 下。
4. **配置 schema 格式**：YAML（更适合人编辑）还是纯 Python（更适合复杂校验）？当前 ADR 给的是 Python Pydantic + YAML profile，YAML 只放值、Python 放 schema 与护栏。
5. **删除 `prototype-data.ts` 的时间点**：阶段 3 末 vs 阶段 4 末？当前 ADR 定在阶段 3 末（前端结构拆分完成时）。
6. **CI 平台**：GitHub Actions / GitLab CI / 其他？现有脚本是否需要兼容多平台？
7. **顶层包管理**：是否同意引入 pnpm workspace（前端）+ uv workspace（后端）？还是维持现状 npm + uv 双轨？
8. **前端数据层是否就绪**：TanStack Query v5 是否可接受？还是希望保留手写 fetch + 简单 hook？
9. **错误码管理**：`ErrorCode` 由后端单点定义 + 前端 codegen（推荐）vs 共享包内定义？

请逐项给出"同意 / 反对 / 需要修改"，我会在收到反馈后开始 Phase 0。Phase 0 与 Phase 1（本次重点：后端配置统一）会按你的确认顺序串行推进；Phase 2 之后可视评审节奏分批启动。
