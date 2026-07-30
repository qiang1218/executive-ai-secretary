# Backend Configuration

> **Phase 1 实施进度**：MVP 框架就位，详细迁移待后续 commit。
> 完整计划见 `docs/architecture/0004-refactor-plan.md` §4.1 + §5 Phase 1。

## 当前（Phase 1 未完成时）

后端配置从环境变量读，定义在 `backend/src/executive_ai_api/config.py`。
Pydantic Settings 自动从 `backend/.env`（gitignored）加载。

启动期强校验已经在 `config.py:model_validator` 实现：默认密钥
拒绝、生产环境 demo 种子拒绝、三个 secret 互不相同。

## Phase 1 目标

把所有配置收口到 `backend/configs/`：
- `profile.<env>.yaml` — 公开配置（按 env 划分）
- `secrets.schema.yaml` — secret 文件约束
- `schema.py` — Pydantic `AppConfig` + 子 config
- `loader.py` — yaml + env + secret 合并

`executive_ai_api.config.Settings` 委托给 `backend.configs`。

## 怎么新增环境变量

Phase 1 完成后：
1. 在 `backend/configs/schema.py` 加 Pydantic 字段
2. 在对应 `profile.<env>.yaml` 写值
3. （如果是 secret）在 `secrets.schema.yaml` 加 schema，部署时把 secret 文件挂进容器
4. 跑 `backend/scripts/check-config-drift.sh` 确认 `compose.yml` 没冗余

## 启动期校验

容器入口执行 `python -m executive_ai_api.configs.loader --validate`，
失败直接拒启动（fail-closed）。

## alembic 期望版本

`backend/configs/alembic-revision.txt` 写死当前 head revision：
`c5d91f4a8b72`。新增 migration 时更新此文件。
