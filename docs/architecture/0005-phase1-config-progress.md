# ADR 0005：后端配置统一（Phase 1）实施进度

> 状态：Phase 1 MVP 框架就位，详细迁移待后续 commit
> 日期：2026-07-30
> 关联：[ADR 0004 §4.1 + §5 Phase 1](./0004-refactor-plan.md)

## 概要

Phase 1 的目标是把分散在 5 个地方的运行时配置收口到
`backend/configs/` 单一事实源。本次提交**只搭框架**，不破坏
现有 `backend/src/api/config.py:Settings` 的运行行为。

## 已完成（本次 commit）

| 文件 | 作用 |
|---|---|
| `backend/configs/README.md` | 解释新结构 + Phase 1 进度 + 后续 commit 计划 |
| `backend/configs/__init__.py` | 暴露 schema 类 |
| `backend/configs/schema.py` | Pydantic `AppConfig` + 6 个子 config（占位） |
| `backend/configs/loader.py` | 配置加载器（占位，`--validate` 暂时报"未完成"） |
| `backend/configs/profile.local-demo.yaml` | local-demo 环境配置（骨架） |
| `backend/configs/profile.customer-template.yaml` | customer-template 配置（骨架） |
| `backend/configs/profile.production.yaml` | production 配置（骨架） |
| `backend/configs/secrets.schema.yaml` | secret 文件路径 + 权限约束（占位） |
| `backend/configs/alembic-revision.txt` | 当前 alembic head：`c5d91f4a8b72` |
| `backend/scripts/check-config-drift.sh` | 漂移检测脚本（CI 用） |
| `backend/docs/configuration.md` | 配置文档 |

## 未完成（后续 commit）

1. **完整 `schema.py`**：补齐所有 Pydantic 字段（audit_hmac_key,
   file_encryption_key, file_storage_root, etc.），全部从现有
   `Settings` 字段搬过来
2. **完整 `loader.py`**：实现 `load_active_profile()`：
   - 读 `APP_ENV` 环境变量
   - 加载对应 `profile.<env>.yaml`
   - 叠加 secret 文件路径（不读 secret 内容）
   - 跑 `AppConfig.model_validator` 启动护栏
   - 返回 `AppConfig` 实例
3. **改 `backend/src/api/config.py`**：把 `Settings`
   改为**薄壳**，从 `get_settings()` 调 `loader.load_active_profile()`。
   **保留相同 import path** 让所有 router 无需改
4. **改 `compose.yml`**：删 8+ 个业务环境变量，改 `env_file:`
   指向 `backend/deploy/environments/<env>.env`
5. **改 `routers/health.py`**：`EXPECTED_DATABASE_REVISION` 改读
   `AppConfig.api.expected_alembic_revision`（从 `configs/alembic-revision.txt`）
6. **完整 `check-config-drift.sh`**：扩 BUSINESS_ENV_VARS，加
   scripts/ 目录扫描
7. **生成 `alembic-revision.txt` 的脚本**：`scripts/generate-configs.sh`
   在 alembic head 变化时自动更新 `configs/alembic-revision.txt`
8. **容器入口前置 validate**：`backend/Dockerfile` 第一步
   `python -m api.configs.loader --validate`
9. **测试**：扩 `tests/test_config_validation.py` 覆盖 6 条护栏分支

## 风险评估

- **本次 commit 风险低**：新文件不修改现有代码，
  `backend/src/api/config.py` 仍正常工作
- **后续 commit 风险中**：重写 `Settings` 委托需要仔细测试
  alembic + uvicorn 启动；如未完整迁移，可能出现
  Pydantic ValidationError
- **commit 顺序建议**：先 1+2+3（schema 完整 + loader + Settings 委托）
  → 单独 commit，测试通过 → 4+5（compose + health） → 6+7+8（CI + Dockerfile）

## 验证

- ✅ `python -c "from backend.configs import AppConfig, ProfileConfig"` 不会
  报错（schema 可 import）
- ✅ `bash backend/scripts/check-config-drift.sh` 暂不会 fail（grep 路径不含业务 env var）
- ⏸ `python -m api.configs.loader --validate` 当前返回 2
  （Phase 1 未完成占位）
- ⏸ 后端 uvicorn 启动 + alembic upgrade head + 登录测试：未变更（应仍工作）

## 不在 Phase 1 范围

- 后端分层（Router → Service → Repository）— Phase 4
- 跨端契约（ErrorCode 枚举 + OpenAPI codegen）— Phase 2
- 前端结构拆分（不动视觉）— Phase 3
- 可观测性（OTel + metrics）— Phase 5
