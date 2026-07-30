# `backend/configs/` — 配置单一事实源

> **Phase 1 实施进度**：框架就位，详细迁移待后续 commit。
> 详见 `docs/architecture/0004-refactor-plan.md` §4.1 + §5 Phase 1。

## 目标

把当前散落在 5 个地方的环境变量 / 配置文件 / secret 文件
收口到 `backend/configs/` 这一棵树下，用 Pydantic 强校验 + 一份
"配置清单"作为唯一事实源。

## 当前状态（2026-07-30）

- ✅ 目录骨架就位
- ✅ 3 个 profile YAML 占位
- ✅ `schema.py` / `loader.py` 占位
- ✅ `secrets.schema.yaml` 占位
- ❌ **未**委托 `backend/src/executive_ai_api/config.py`（现有 Settings 仍然直接读 env）
- ❌ **未**改 `compose.yml`（仍含业务环境变量）
- ❌ **未**改 `routers/health.py` 的硬编码 `EXPECTED_DATABASE_REVISION`
- ❌ **未**写 `alembic-revision.txt`（Phase 1 完成时由 alembic 脚本生成）
- ❌ **未**写 `check-config-drift.sh`

## 目录结构

```
backend/configs/
├── README.md                          # 本文件
├── schema.py                          # Pydantic AppConfig（占位）
├── loader.py                          # 配置加载器（占位）
├── profile.local-demo.yaml            # local-demo 环境
├── profile.customer-template.yaml     # customer-template 环境
├── profile.production.yaml            # production 环境
├── secrets.schema.yaml                # secret 文件名 / 路径 / 权限约束（占位）
└── alembic-revision.txt               # 由 alembic 脚本生成的 head revision（待生成）
```

## 与现有代码的关系（Phase 1 完成时）

`backend/src/executive_ai_api/config.py` 的 `Settings` 类未来
**委托**给本目录的 schema：

```python
# 未来代码（Phase 1 完成时）
from executive_ai_api.configs import schema, loader

def get_settings():
    return loader.load_active_profile()
```

## 当前能用但未走 `configs/` 的事实源

| 事实源 | 当前位置 | Phase 1 完成后 |
|---|---|---|
| 数据库连接 | `Settings.database_url` 读 `DATABASE_URL` env | `AppConfig.database.url` 从 `profile.*.yaml` |
| Cookie 策略 | `Settings.session_cookie_secure` 等 | `AppConfig.cookie.*` |
| Worker 调度参数 | `Settings.worker_*` | `AppConfig.worker.*` |
| API 路径前缀 | `Settings.api_prefix` | `AppConfig.api.prefix` |
| 启动护栏 | `Settings.model_validator` 内部 | 抽到 `AppConfig.model_validator` + 子 config |
| alembic 期望版本 | `routers/health.py` 硬编码 | `AppConfig.api.expected_alembic_revision` |
| CORS / TrustedHost | `Settings.allowed_origins` 等 | `AppConfig.api.cors_allowed_origins` 等 |

## 后续 commit 计划

1. 写完整 `schema.py`（所有 Pydantic 子 config）
2. 写 `loader.py`（从 yaml + env + secret 合并）
3. 改 `backend/src/executive_ai_api/config.py` 委托 `schema.py`
4. 改 `compose.yml` 删业务环境变量，改 `env_file:`
5. 改 `routers/health.py` 读 `config.api.expected_alembic_revision`
6. 写 `alembic-revision.txt` 生成脚本
7. 写 `check-config-drift.sh`（CI 漂移检测）

## 启动期强校验

`AppConfig.model_validator(mode="after")` 统一做：
- 生产环境拒绝默认密钥 / 演示种子 / debug
- cookie secure + samesite 一致性
- 三个 secret (SESSION/CSRF/AUDIT) 互不相同
- 启动期 alembic head 匹配 `expected_alembic_revision`

`backend/Dockerfile` 入口执行 `python -m executive_ai_api.configs.loader --validate`，失败直接拒启动。
