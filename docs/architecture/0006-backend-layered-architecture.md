# ADR 0006：后端分层重构方案（基于参考项目 anspire_atomic_power_backend）

- 状态：提议稿，等待评审
- 日期：2026-07-31
- 适用阶段：生产化第三阶段 / 与 ADR 0004 §5 Phase 4 对齐
- 关联 ADR：
  - [ADR 0001](./0001-production-foundation.md)（安全契约不变）
  - [ADR 0003](./0003-authorization-and-audit-matrix.md)（授权与审计矩阵不变）
  - [ADR 0004](./0004-refactor-plan.md) §1.4.2（痛点）+ §3.3（目标架构）+ §5 Phase 4（路线图）
- 不在范围：前端、worker 业务逻辑实现、配置 schema 改造（已在 0004 §5 Phase 1 处理）

---

## 1. 本 ADR 解决的"剩余痛点"

ADR 0004 §1.4.2 已经描述了后端的关键问题：
> 没有 service 层、没有 repository 层、models.py 600+ 行、schemas.py 330+ 行平铺、authz.py 偏胖、错误码不统一、router 与 service / 持久化职责混杂、worker 单文件 514 行、数据库会话生命周期混乱。

在前几次重构（0004 评审反馈 + 用户此前指令）之后，已经完成：
- ✅ 顶层 `backend/` / `frontend/` 分离
- ✅ 配置统一到 `backend/src/configs/settings.py`（Pydantic）
- ✅ DB 操作脚本 Python 化到 `backend/scripts/`
- ✅ Docker secrets 方案清理

**还剩下**：纯代码组织 / 分层 / 入口收敛。下面把这一层做完。

---

## 2. 参考项目观察（按一个服务拆开看）

`D:\anchnet\anspire_atomic_power_backend` 选了 `customer` 域从路由到库的端到端作为样本：

```
customer.py(API route, 781 行)
  ↓ 调用
CustomerService(db)              ← services/customer_service.py, 纯业务
  ↓ 持有
Balances / Licenses / Customers   ← models/model.py (SQLAlchemy Base)
  ↓ 输入输出用
CustomerLoginForm                  ← models/form.py (Pydantic 输入)
CustomersPublic                    ← models/vo.py    (Pydantic 输出)
  ↓ 跨页用
Token, get_current_active_user    ← core/security.py
get_async_db / AsyncSessionLocal  ← db/__init__.py
```

参考项目的**关键设计选择**：

| 选择 | 它的做法 | 我们当前的做法 | 差异 |
| --- | --- | --- | --- |
| 层级分包 | 顶层 `api / services / models / schemas / repositories / core / tasks / utils` 一目了然 | `src/api/` 平铺 33 个 .py，仅 `routers/` 一个子目录 | 重 |
| Service 形式 | 每个域一个 `XxxService(db)` 类，事务、审计、业务规则全在内部 | `router` 自己 `db.add` / `commit` / `record_audit` | 重 |
| Repository 层 | 单独列出（虽然只示例了 2 个），意图把 SQL 集中到一处 | SQL 散落 `router`，重复 ~10 处模板 | 重 |
| Models 拆分 | `models/model.py` 表 / `models/form.py` 输入 / `models/vo.py` 输出 三分 | 一个 600+ 行 `models.py` + 一个 330+ 行 `schemas.py` | 重 |
| Worker / Task | `tasks/` 与 `services/` 平级，按调度器/调度任务分类 | `worker/main.py` 单文件 514 行 | 重 |
| Router 注册 | `api/__init__.py` 静态收集所有 `router`，主入口 `main.py` 用 `Register` 类注册 | `src/api/main.py` 写死循环 `include_router` | 中 |
| 统一响应封装 | `APIResponse.ok(data=...)` / `APIResponse.error(...)` 一个包络 | `AppError(...)` + 各路由自己 `return XxxOut(...)`，没有统一包络 | 中 |
| 主入口 | 项目根 `main.py`：FastAPI app + lifespan + 一个 `Register` 类统一装路由 / 中间件 / 静态 / 后台任务 | `src/api/main.py` 已较干净，但 lifespan 里硬编码了"初始化审计链"等业务启动逻辑 | 小 |
| DB / Redis 入口 | `db/__init__.py` 集中导出 `get_async_db / async_client / dispose_*` | `src/api/database.py` 一个文件 | 小 |
| Schema 拆分 | `schemas/<domain>_schema.py` / `schemas/api_response.py` / `schemas/pagination.py` 等 | 一个 `schemas.py` 330+ 行平铺 | 中 |
| 安全层 | `core/security.py` 同时管密码、Token、CSRF、白名单风控 | `src/api/security.py` + `src/api/authz.py` 分两个文件，CSRF 挤在 `authz.py` 内 | 中 |
| 注册中心 | `api/registries/register.py` 一个类负责中间件 / 路由 / 静态 / 后台任务 | 没有注册中心，`main.py` 内联 | 重 |

**核心借鉴**：
1. **顶层按角色分包**，不按文件用途。
2. **Service 类持有事务**（不是 router 直接 commit）。
3. **Router ≤ 30 行**：只做参数解析 + 调 service + 回包。

---

## 3. 当前项目 `src/` 目录实情

```
backend/src/
├── api/                        ← 33 个 .py，绝大多数堆在同一层
│   ├── main.py                 # FastAPI app + lifespan + 路由装载
│   ├── routers/                # 10 个，业务路由（这部分是好榜样）
│   ├── audit.py                # ┐
│   ├── audit_integrity.py      # │
│   ├── authz.py                # │
│   ├── backup_evidence.py      # │
│   ├── cli.py                  # │
│   ├── database.py             # │
│   ├── errors.py               # │
│   ├── file_key_rotation.py    # │ 平铺
│   ├── idempotency.py          # │
│   ├── job_state.py            # │
│   ├── logging_config.py       # │
│   ├── middleware.py           # │
│   ├── migration_compatibility.py  # │
│   ├── models.py               # │
│   ├── pagination.py           # │
│   ├── rotate_file_keys.py     # │
│   ├── schemas.py              # │
│   ├── security.py             # │
│   ├── seed.py                 # │
│   └── storage.py              # ┘
├── configs/
│   └── settings.py             # Pydantic Settings（已统一）
└── worker/
    └── main.py                 # 514 行单文件
```

加上 alembic：
```
backend/
├── alembic/
│   ├── env.py                  # import 链：api.database → api.models → api.audit_integrity
│   └── versions/*.py
└── alembic.ini
```

### 3.1 真正的问题清单

1. **`src/api/` 是"垃圾抽屉"**：跨页（`database`、`errors`、`logging_config`、`middleware`、`pagination`、`security`、`migration_compatibility`）、业务（`audit`、`storage`、`job_state`、`backup_evidence`、`file_key_rotation`、`rotate_file_keys`）、入口（`cli`、`seed`、`main`）混在一处。
2. **`models.py` 14 个 ORM 类平铺**，跨域耦合（identity 与 knowledge、reporting、jobs 在同一文件，import 一片）。
3. **`schemas.py` 330+ 行平铺**，输入 / 输出 / 分页 / 通用响应没分文件。
4. **`router` 自己 commit**：`record_audit(...)` + `db.commit()` 在每个端点里手动调用，重复 5 行模板在多个 router。
5. **`authz.py` 偏胖**：同时承担 principal 加载、CSRF、角色守卫、范围判定、范围快照、范围谓词、范围守门；CSRF 不属于"授权"，应当分家。
6. **`worker/main.py` 514 行**：poll / lease / heartbeat / 错误分类 / 收口函数 / 业务 handler 注册 全在一个文件。
7. **入口散乱**：`python -m api.main` / `python -m worker.main` / `python -m api.cli` / `alembic -x ...` 四种入口，互相 import `api.database / api.security / api.audit_integrity`，**`env.py` 深度依赖 api 子包**。

---

## 4. 目标结构

```
backend/src/
├── api/                        # Web 层（仅 HTTP 装配 + 路由）
│   ├── __init__.py             # 重新导出 app 以兼容 uvicorn
│   ├── main.py                 # 仅 FastAPI app + lifespan + 路由注册
│   ├── deps.py                 # FastAPI 依赖（get_db、get_principal、get_settings）
│   ├── lifespan.py             # lifespan 内的"启动钩子"注册
│   └── routers/                # 业务路由（保持现有 10 个文件）
│
├── core/                       # 跨页基础设施（不再 import 业务）
│   ├── __init__.py
│   ├── config.py               # 委托给 configs/settings.py，向后兼容别名
│   ├── db.py                   # engine、SessionLocal、get_db、dispose_engine
│   ├── errors.py               # AppError + ErrorCode(StrEnum) + 异常处理器注册
│   ├── logging.py              # 结构化日志配置
│   ├── middleware.py           # RequestContextMiddleware 等
│   ├── pagination.py           # Page / CursorPage 基类
│   ├── idempotency.py          # Idempotency-Key 头处理 + 唯一索引
│   ├── security/               # ← 拆 src/api/security.py
│   │   ├── password.py         # hash_password / verify_password / rehash 检测
│   │   ├── session.py          # UserSession 相关 + session_expirations
│   │   ├── csrf.py             # csrf_protect 依赖（从 authz.py 抽出）
│   │   └── ratelimit.py        # rate_limiter
│   ├── auth/                   # ← 拆 src/api/authz.py
│   │   ├── principal.py        # Principal + get_current_principal + 角色守卫
│   │   └── scope.py            # accessible_org_ids / assert_org_scope / scope snapshot
│   ├── migration_compat.py     # 备份/恢复时的兼容垫片（从 api 移过来）
│   └── response.py             # 统一 APIResponse 包络（如果决定引入）
│
├── domain/                     # ORM + 领域 dataclass（按子域拆）
│   ├── __init__.py             # 重新导出 Base 与所有模型
│   ├── base.py                 # Base + TimestampMixin + UUIDMixin + JSONType
│   ├── identity.py             # Enterprise / OrgUnit / User / UserCredential / UserSession / DataScopeGrant
│   ├── knowledge.py            # Project / Conversation / Message / MessageRun / FileAsset / ConversationFile / FileEvent / Memory / MemoryEvent
│   ├── reporting.py            # Report / ReportVersion
│   ├── jobs.py                 # Job / JobAttempt
│   ├── audit.py                # AuditEvent / AuditChainHead / IdempotencyRecord
│   └── admin.py                # AppConfig / SecretReference
│
├── repositories/               # 数据访问层（SQL 集中 + 通用查询构造器）
│   ├── __init__.py
│   ├── identity_repo.py        # user_repo / session_repo / org_repo / scope_repo
│   ├── knowledge_repo.py       # conversation_repo / message_repo / project_repo / file_repo / memory_repo
│   ├── reporting_repo.py
│   ├── job_repo.py             # claim_one / renew_lease / recover_expired_leases
│   └── audit_repo.py
│
├── services/                   # 业务服务（事务边界 + 业务规则 + 审计/幂等封装）
│   ├── __init__.py
│   ├── auth_service.py         # login / change_password / logout / list_sessions / revoke
│   ├── conversation_service.py # create / get / pin / archive / send_message
│   ├── project_service.py
│   ├── file_service.py
│   ├── memory_service.py
│   ├── report_service.py
│   ├── job_service.py          # enqueue（带 handler registry 校验）
│   ├── audit_service.py        # record_audit 封装（不再在 router 散落）
│   └── storage_service.py      # 文件加密 / 解密 / 密钥轮换的 façade
│
├── schemas/                    # Pydantic I/O（按子域拆）
│   ├── __init__.py
│   ├── common.py               # ORMModel / Page / CursorPage
│   ├── auth.py                 # LoginRequest / LoginResponse / SessionOut / MeResponse
│   ├── organization.py         # OrganizationUnitOut 等
│   ├── conversation.py
│   ├── project.py
│   ├── file.py
│   ├── memory.py
│   ├── report.py
│   ├── job.py
│   └── audit.py
│
├── worker/                     # 异步任务（多文件）
│   ├── __init__.py
│   ├── main.py                 # 信号、run() 入口（< 60 行）
│   ├── runtime.py              # poll / claim_one / renew_lease / recover_expired_leases / _finish_*
│   ├── handlers/
│   │   ├── __init__.py         # 自动注册
│   │   ├── base.py             # JobHandler 协议 + JobContext
│   │   └── system_noop.py      # 唯一一个现存的 handler
│   └── registry.py             # job_type → handler 映射 + get_handler 校验
│
└── configs/                    # 不变
    ├── __init__.py
    └── settings.py
```

### 4.1 关键设计决策

#### 4.1.1 `core/` 和 `domain/` 谁先 import？

- `core/` 不允许 import `domain / repositories / services / schemas`。
- `domain/` 可以 import `core.config`（用于 `server_default` 等只读配置），但不 import `repositories / services`。
- `repositories/` 可以 import `domain / core.db`，但不 import `services`。
- `services/` 可以 import `domain / repositories / core`，但不 import `routers / schemas`（schemas 由 `routers` import）。
- `routers/` 可以 import `services / schemas / core.deps`，**禁止直接 import `domain`**（除非要 `model_validate`，这种情况通过 schemas 转换）。

用 ruff 的 `TID` / `import-linter` 配置将上述规则固化为 CI 门禁（`contracts.py`）。

#### 4.1.2 Service 协议

```python
# core/deps.py（共享）
class AuthServiceProto(Protocol):
    def login(self, *, form: LoginRequest, request: Request, response: Response) -> LoginResponse: ...
    def change_password(self, principal: Principal, form: ChangePasswordRequest) -> LoginResponse: ...

def get_auth_service(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthServiceProto:
    return AuthService(db=db, settings=settings)
```

Router 形如：

```python
@router.post("/login", response_model=LoginResponse)
def login(
    form: LoginRequest,
    request: Request,
    response: Response,
    service: Annotated[AuthServiceProto, Depends(get_auth_service)],
) -> LoginResponse:
    return service.login(form=form, request=request, response=response)
```

每个端点 ≤ 30 行；禁止 `db.add / db.commit / record_audit` 出现在 router。

#### 4.1.3 审计与幂等的封装

- `services/audit_service.py` 提供 `record(db, request, action, *, actor=None, session=None, target_type=None, target_id=None, outcome="success")`，**内部处理 commit 协调**（不替上层 commit）。
- 幂等由 `core/idempotency.py` 提供 `IdempotencyGuard` 装饰器，挂在需要幂等的端点上：

```python
@router.post("/conversations", response_model=ConversationOut,
             dependencies=[Depends(idempotency_guard)])
def create_conversation(...): ...
```

#### 4.1.4 Worker 拆分

```python
# worker/handlers/base.py
class JobHandler(Protocol):
    job_type: str
    def handle(self, ctx: JobContext) -> dict: ...

# worker/handlers/system_noop.py
class SystemNoopHandler:
    job_type = "system.noop"
    def handle(self, ctx: JobContext) -> dict:
        return {"ok": True}

# worker/registry.py
_registry: dict[str, JobHandler] = {}
def register(handler: JobHandler) -> None: ...
def get_handler(job_type: str) -> JobHandler: ...   # 未注册抛 JobHandlerNotConfigured

# worker/main.py（< 60 行）
from worker.runtime import run
if __name__ == "__main__":
    run()
```

未注册的 `job_type` 在 **enqueue 阶段** 抛错（参考项目 `JobHandlerNotConfigured`）而不是被 worker 处理时才发现。

#### 4.1.5 Alembic env.py 现代化

`alembic/env.py` 改为：

```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from core.config import get_settings
from domain.base import Base  # ← 不再 import api.models / api.audit_integrity
import domain  # noqa: F401 — 确保所有 model 被 import 注册

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata

# ... 其余 alembic 标准模板 ...
```

`alembic.ini` 的 `script_location` 保持 `alembic`。**`alembic/versions/*.py` 内容不改**，只是 import 路径可能需要从 `api.models import X` 改成 `from domain.identity import X`，这是 **机械替换**。

---

## 5. 迁移路线（按阶段，每阶段独立合并、回滚、回归）

**前置原则**：
- 每阶段结束 `make smoke` 与 `make test` 绿；49 个 pytest + 6 个 skipped 不得回归。
- 一次只动一个层级（layer）或一个域（domain），不混合 PR。
- 安全契约（authz、audit_integrity、storage）**只搬位置，不改语义**。

### Phase A：搬出 `core/`（horizontal 切片，1 周）

1. 新建 `backend/src/core/`。
2. 文件逐一搬迁 + import 改名（**纯移动，零行为变化**）：
   - `api/database.py` → `core/db.py`
   - `api/errors.py` → `core/errors.py`（同时引入 `ErrorCode(StrEnum)`，先用字符串别名维持兼容）
   - `api/logging_config.py` → `core/logging.py`
   - `api/middleware.py` → `core/middleware.py`
   - `api/pagination.py` → `core/pagination.py`
   - `api/idempotency.py` → `core/idempotency.py`
   - `api/migration_compatibility.py` → `core/migration_compat.py`
3. `api/security.py` 拆为 `core/security/{password,session,ratelimit}.py`（csrf 留到 Phase B）。
4. `api/main.py` 的 `lifespan` 函数搬到 `core/lifespan.py`；`api/main.py` 只留下 FastAPI app 与路由 `include_router`。
5. 加 `core/__init__.py` 重导出，让旧导入路径 `from api.database import engine` 仍可用 1 个版本（DeprecationWarning），下个版本删除。
6. 全部 alembic 迁移文件 import 路径同步刷新：`from api.models import Enterprise` → `from domain.identity import Enterprise`（先不动 `models.py`，等 Phase C 再拆）。
7. 49 pytest 必须全绿。

**完成定义**：
- `core/` 内 8 个文件，职责清晰可一眼看懂
- `src/api/` 只剩 `main.py / deps.py / routers/ / __init__.py + 一些临时 re-export shim`
- alembic `env.py` 仅 import `core.db / core.config / domain.<某个>`，不再 import `api`

### Phase B：拆 `authz.py` 与 CSRF（horizontal，0.5 周）

1. `api/authz.py` 拆为 `core/auth/principal.py`（principal + 角色守卫）与 `core/auth/scope.py`（scope snapshot / predicate / 守门）。
2. CSRF 从 `authz.py` 抽出到 `core/security/csrf.py`，原 `csrf_protect` 函数搬迁。
3. `api/authz.py` 删除（不再保留 shim，已 Phase A 内部 import 全部更新）。

### Phase C：拆 `domain/`（horizontal，1 周）

1. 新建 `backend/src/domain/base.py`：`Base`、`TimestampMixin`、`UUIDMixin`、`JSONType`、`new_uuid`。
2. 将 `api/models.py` 14 个 ORM 类按子域拆到 `domain/{identity,knowledge,reporting,jobs,audit,admin}.py`。
3. 拆除 `event.listens_for(AuditEvent, "before_insert")` 中的 `from .audit_integrity import prepare_audit_event` 懒加载；保持行为一致。
4. `api/models.py` 删除；`api/audit_integrity.py` 改为 import `domain.audit`。
5. `api/schemas.py` 暂不动（Phase D 拆）。

**完成定义**：
- `domain/` 7 个文件，每个 ≤ 250 行
- pytest 全绿；`inspect.signature` 行为不变

### Phase D：拆 `schemas/`（horizontal，0.5 周）

按子域拆 `api/schemas.py`，删 `api/schemas.py`。

### Phase E：引入 `services/` 与 `repositories/`（按子域纵切，3 周）

按域逐个迁移 router，一次一域：

**E.0 基线**：抽 `core/deps.py` 的 `get_<x>_service` 协议工厂；建立 `services/audit_service.py` 收口 `record_audit` 行为（不替换 router 的调用，**先建立目标，再迁移调用**）。

**E.1 identity 域**（0.5 周）：
- `repositories/identity_repo.py`：user / session / org / scope
- `services/auth_service.py`：login / change_password / logout / list_sessions / revoke_session
- `routers/auth.py` 改造为仅依赖 `AuthService`

**E.2 knowledge 域**（1 周）：
- `repositories/knowledge_repo.py`：5 个子 repo
- `services/{conversation,project,file,memory}_service.py`
- 改造 4 个 router

**E.3 reporting 域**（0.5 周）：
- `reporting_repo.py` + `report_service.py` + `routers/reports.py`

**E.4 audit / job / storage**（1 周）：
- `services/audit_service.py` 完成替换（router 不再直接 `record_audit`）
- `services/job_service.py` + `repositories/job_repo.py`，router `/jobs` 调 `JobService.list / cancel`
- `services/storage_service.py` 包装现有 `storage.py` 加密接口

每域改造结束时，`grep -r "record_audit\|db.commit()" src/api/routers/` 的命中应当**逐步减少到 0**。

### Phase F：worker 拆分（0.5 周）

1. 拆 `worker/main.py`：
   - `worker/runtime.py`：保留当前 `claim_one` / `process` / `renew_lease` / `recover_expired_leases` / `_finish_*` 共 ~400 行
   - `worker/main.py` 仅 `signal` + `runtime.run()`
2. 引入 `worker/handlers/{base,system_noop}.py` 与 `worker/registry.py`。
3. 当前 `execute_job_handler` 内部 `if job.job_type == "system.noop"` 改为 `runtime.handle(job) → registry.get_handler(job.job_type).handle(ctx)`。
4. `execute_job_handler` 函数删除。

### Phase G：移除 shim，固化 `import-linter`（0.5 周）

1. 删除 Phase A 的 re-export shim。
2. 引入 `import-linter` 配置，固化 §4.1.1 的 import 边界。
3. 更新所有 `backend/scripts/*.py` 的 import。
4. Makefile 新增 `make lint:contracts`。

---

## 6. 与已有 ADR 的关系

| ADR | 状态 | 本 ADR 如何衔接 |
| --- | --- | --- |
| 0001 安全契约 | 已落地 | **不改 security 主流程**，只搬位置；Argon2id / Session / CSRF 行为不变 |
| 0003 授权与审计矩阵 | 已落地 | `assert_org_scope / scope_snapshot_is_current / organization_scope_predicate` 三个工具**保留并搬到 `core/auth/scope.py`** |
| 0004 §1.4.2 痛点 | 已描述 | 本 ADR 把其中 8 条具体落地为"哪个文件搬到哪、什么顺序" |
| 0004 §3.3 目标架构 | 抽象描述 | 本 ADR 是它的"图纸"，加上了 5 个 Phase 的**可执行切割** |
| 0004 §5 Phase 4 路线图 | 已规划 | 本 ADR 的 Phase E 即对应 0004 §5 Phase 4 |

---

## 7. 完成定义（DoD）

整体 DoD：
- `backend/src/` 顶层仅有 `api / core / domain / repositories / services / schemas / worker / configs` 八个目录，每个目录的角色一眼可读。
- `src/api/` 仅含 `main.py / deps.py / __init__.py / routers/`。
- `src/api/routers/` 任意 `*.py` 单文件 ≤ 250 行；单端点函数 ≤ 30 行。
- `grep -r "record_audit\|db.add\|db.commit" src/api/routers/` 命中数为 0。
- `worker/main.py` ≤ 60 行；handler 注册通过 `worker.registry` 完成。
- `import-linter` 边界规则 CI 通过。
- 49 pytest + 6 skipped 全绿；新增 `tests/test_service_auth.py` / `tests/test_job_registry.py` 覆盖 Phase E/F 新增逻辑。

---

## 8. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
| --- | --- | --- | --- |
| Phase E 引入 service 层时漏改 `assert_org_scope` 调用导致越权 | 中 | 高 | 引入 `core/auth/scope.py` 的**覆盖测试**（10 个越权场景）；每次合并 E.* 时跑一次 |
| 拆 `authz.py` 时破坏 principal 加载链 | 中 | 高 | Phase B 单独一 PR，旧 `api.authz` 路径保留 shim 直至 Phase G |
| 拆 `domain/` 时 alembic autogenerate 误识别 | 低 | 中 | 整个 Phase C 期间 `offline = true`，**不跑 autogenerate**；迁移文件手写 |
| Worker 拆分引入 lease 死锁 | 低 | 高 | Phase F 之前必跑 `tests/test_worker_lease.py`；拆分后行为完全等价 |
| Service 类持有事务导致连接占用过长 | 中 | 中 | 单 service 函数 ≤ 50 行，禁用 `time.sleep` 等阻塞调用；超时仍由 alembic 外的连接池控制 |
| `import-linter` 与现有 ruff 冲突 | 低 | 低 | import-linter 走独立 make target，与 ruff 不冲突 |

---

## 9. 文档与 ADR 更新

完成全部 5 个 Phase 后同步：
- 本 ADR 0006 标记为"已落地"
- 更新 ADR 0004 状态：Phase 4 完成
- 写一份 `backend/src/README.md` 说明目录角色
- 把 §4 移到 `docs/architecture/backend-layered-architecture.md` 作为常驻索引

---

## 10. 评审要点

请在评审时给出"同意 / 反对 / 需要修改"：

1. **顶层目录命名**：本 ADR 用 `core / domain / repositories / services / schemas / worker`，是否接受？还是希望统一为 `infrastructure / application / interfaces` 这种 DDD 风格？
2. **`domain/` 还是 `models/`**：本 ADR 倾向 `domain/`（DDD 语义），接受？
3. **Service 协议用 Protocol 还是 ABC**：本 ADR 推荐 Protocol（结构性子类型）；可否？
4. **是否引入 `core/response.py` 统一 APIResponse 包络**：参考项目有，我们当前没；引入会动所有现有 router 的响应形态，影响较大，**本 ADR 暂不引入**，仅记录为未来议题，是否同意？
5. **是否引入 `import-linter` 作为 CI 门禁**：可接受？
6. **本 ADR 与 ADR 0004 §5 Phase 4 的关系**：本 ADR 是否完全替换 0004 §5 Phase 4？或者 0004 §5 Phase 4 改为引用本 ADR？
7. **Phase A 的 re-export shim**：是否同意保留一个版本？还是希望直接破坏式升级？
8. **每阶段的时长估计**：A 1 周 / B 0.5 周 / C 1 周 / D 0.5 周 / E 3 周 / F 0.5 周 / G 0.5 周，**总 7 周**。是否需要拆分到多个迭代？

收到评审反馈后开始 Phase A；按每个 Phase 单独合并 + 测试 + 评审，**不一次性 big-bang**。
