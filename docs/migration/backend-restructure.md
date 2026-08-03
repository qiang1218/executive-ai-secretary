# 后端目录迁移总结

> 日期：2026-08-03
> 范围：`new/services/api/src/executive_ai_api/`（约 28000 行 / 65 个 Python 模块）
> 目标：`backend/src/`，按 `anspire_atomic_power_backend` 的"路由 / 服务 / 仓储"三层架构

## 最终状态

```
======================================================================
PYTEST:                 137 passed, 5 skipped, 0 failed   (exit code 0)
APP 装配:                董事长人工智能研究员 API | 72 paths | Register= Register
_legacy_api 残留引用:    0 matches in src/ + tests/
======================================================================
```

`_legacy_api/` 目录已**彻底删除**，零残留引用。所有真实代码已下沉到三层架构目标包。

## 目标结构

```
backend/src/
├── api/                          # 路由层 + 顶层装配
│   ├── __init__.py               # 暴露 Register, create_app, middlewares, routes
│   ├── main.py                   # create_app(routes, middlewares) 应用工厂
│   ├── deps.py                   # FastAPI Annotated 依赖（SessionDep / PrincipalDep / ...）
│   ├── middlewares/
│   │   └── __init__.py           # RequestContextMiddleware
│   ├── registries/
│   │   └── register.py           # Register 类：set_router / set_extra_middlewares
│   └── routes/                   # 17 个 router 子模块（admin / auth / conversations / ...）
├── configs/                      # 配置层
│   ├── __init__.py
│   └── settings.py               # Settings / get_settings / 密钥轮换
├── core/                         # 通用基础能力
│   ├── security.py               # hash_password / utc_now / RateLimiter / ...
│   └── pagination.py             # encode_cursor / decode_cursor
├── db/                           # 数据库
│   └── session.py                # Base / engine / SessionLocal / get_db
├── exceptions/                   # 异常与 handler
│   └── errors.py
├── logs/                         # 日志
│   └── config.py                 # JsonFormatter / configure_logging
├── middleware/                   # middleware 兼容层
│   └── __init__.py               # RequestContextMiddleware
├── models/                       # ORM 模型
│   └── __init__.py               # Base / 全部表类
├── repositories/                 # 仓储：8 个数据访问模块
│   ├── audit.py / audit_integrity.py / seed.py
│   ├── migration_compatibility.py / operating_data_reset.py
│   └── personal_data_migration.py / rotate_file_keys.py / rotate_integration_keys.py
├── schemas/                      # Pydantic schema
│   └── __init__.py
├── services/                     # 业务服务：25 个领域模块
│   ├── ingestion.py / business_tools.py / daily_brief.py
│   ├── anspire.py / authz.py / capabilities.py
│   └── ...（其余 20 个）
├── utils/                        # CLI / 任务状态
│   ├── cli.py
│   └── job_state.py
└── worker/                       # 异步 worker
    ├── file_key_rotation.py / hermes_client.py
    ├── integration_key_rotation.py
    ├── mcp_app.py / mcp_registry.py
    └── __init__.py               # 懒加载，避免与 services 循环导入
```

## 装配入口

`backend/main.py`（用户预写）：

```python
from api import Register, create_app, middlewares, routes
app = create_app(routes, middlewares)
```

`api.create_app(routes, middlewares)` 内部流程：

1. `configure_logging(settings.log_level)`
2. `lifespan` 启动期初始化审计链 + 校验关键密钥
3. 注册 `CORS` / `TrustedHost` / `RequestContext` 中间件
4. 注册 `AppError` / `HTTPException` / `RequestValidationError` 全局异常 handler
5. 按 `routes.public_routers` / `routes.protected_routers` 分组挂载业务 router
6. 自定义 OpenAPI（`sessionCookie` 安全方案 + `X-CSRF-Token` 强约束）

OpenAPI 实际暴露 **72 个 path**。

## 关键技术决策

1. **sys.modules 替换桩（过渡期）**：下沉过程中，`_legacy_api/<X>.py` 曾用 `sys.modules[__name__] = _mod` 把自己替换为目标模块对象。这样 `from _legacy_api import seed` 拿到的就是 `repositories.seed` 模块对象本身，monkeypatch 操作的是真实模块。

2. **懒加载防循环**：`services/__init__.py` 和 `worker/__init__.py` **不主动 import 子模块**，而是通过 `__getattr__` + `importlib.import_module` 懒加载。这是因为 `services.business_tools` ↔ `worker.mcp_app` / `worker.mcp_registry` 之间存在双向依赖。

3. **`api/routes/__init__.py` 自动注册 router**：用 `_ensure_loaded()` 在导入时加载所有 router，分组为 `public_routers` / `protected_routers` / `all_routers`，并自动处理 `admin_models` 的双 router 情况。

4. **Windows 平台兼容**：`storage.py` 在 Windows 上跳过 directory fsync；`config.py` 在 Windows 上跳过 group/other 权限位检查。

## 测试结果

```
$ python -m pytest tests/ -q
..................................................................s...s. [ 51%]
..................................................sssss.......s.....     [100%]
137 passed, 5 skipped, 0 failed
```

跳过的 5 个用例：

* `tests/test_daily_brief.py::test_daily_brief_assembles_metrics_from_recent_snapshots`
* `tests/test_daily_brief.py::test_daily_brief_handles_missing_or_partial_data`
* `tests/test_postgres_*.py::...`（3 个）—— 依赖 PostgreSQL

## 后续可选优化

迁移已完成。如果未来要把函数式代码改为 anspire 风格的 class 形式，可按以下顺序：

1. **models/**：把 `models/__init__.py` 按领域拆成 `user.py` / `organization.py` / `audit.py` / ...
2. **schemas/**：把 `schemas/__init__.py` 按领域拆成 `auth.py` / `data.py` / `conversations.py` / ...
3. **repositories/**：把每个模块重写为 `<Domain>Repository` 类，构造器接收 `Session`
4. **services/**：把每个模块重写为 `<Domain>Service` 类，构造器接收 `Session` + `<Domain>Repository`
5. **api/routes/**：把 `Depends(get_db)` 改为 `Depends(get_<domain>_repository)` 等

每步完成后跑测试确认无回归。
