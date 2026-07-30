# ADR 0004 重构迁移进度

> 与 [0004-refactor-plan.md](./0004-refactor-plan.md) 配套，记录 Phase 0 / Phase 1 实际执行状态。
> 状态：`IN PROGRESS` ｜ 最后更新：2026-07-30

## 整体计划（7 步）

| Step | 内容 | 状态 | 影响文件数 |
|---|---|---|---|
| 1 | 建空骨架 `backend/` `frontend/` `shared/` | ✅ DONE | 35 目录 |
| 2 | git mv 后端文件 → `backend/` | ⏳ TODO | ~15 |
| 3 | git mv 前端文件 → `frontend/` | ⏳ TODO | ~20 |
| 4 | git mv worker + 合并到 `backend/src/worker/` | ⏳ TODO | ~3 |
| 5 | 顶层 `Makefile` + 顶层 `scripts/` 改造 | ⏳ TODO | ~8 |
| 6 | Phase 1 — `backend/configs/` 单一事实源 | ⏳ TODO | ~10 新建 + 5 改 |
| 7 | 验证 `make install && make smoke` | ⏳ TODO | — |

## Step 1 已建目录（35 个）

```
backend/
├── src/{executive_ai_api, worker}
├── alembic/versions
├── deploy/{compose, postgres, nginx, environments}
├── scripts, configs, docs, tests

frontend/
├── app
├── src/
│   ├── components/{primitives, business}
│   ├── features/{auth, conversations, projects, files, memories, reports, bootstrap}
│   ├── data, auth, state, i18n, runtime, styles, types
├── public, deploy/{nginx, environments}, scripts

shared/
├── api-contracts, domain, docs
```

## Step 2 / 3 / 4 计划移动清单（待执行）

### 后端 → `backend/`

| 现状 | 目标 | 备注 |
|---|---|---|
| `services/api/src/executive_ai_api/` | `backend/src/executive_ai_api/` | 全部 py 文件 |
| `services/api/alembic/` | `backend/alembic/` | 含 `env.py` `versions/*.py` |
| `services/api/alembic.ini` | `backend/alembic.ini` | |
| `services/api/pyproject.toml` | `backend/pyproject.toml` | |
| `services/api/uv.lock` | `backend/uv.lock` | |
| `services/api/Dockerfile` | `backend/Dockerfile` | |
| `services/api/.dockerignore` | `backend/.dockerignore` | |
| `services/api/.env` | `backend/.env` | 用户本地用 |
| `services/api/local.db` | `backend/local.db` | 用户本地数据 |
| `services/api/.runtime/` | `backend/.runtime/` | secrets + uvicorn log |
| `services/api/.venv/` | `backend/.venv/` | uv 虚拟环境 |
| `deploy/postgres/` | `backend/deploy/postgres/` | 4 文件 |
| `deploy/nginx/` | `backend/deploy/nginx/` | 2 文件（**会与 frontend/deploy/nginx/ 冲突 → 仅保留 backend/deploy/nginx/，前端用静态目录**） |
| `deploy/environments/` | `backend/deploy/environments/` | 5 文件 |
| `deploy/.env.example` | `backend/.env.example` | |
| `deploy/ci-recovery-drill.example.yml` | `backend/deploy/ci-recovery-drill.example.yml` | |
| `deploy/upgrade-env-secrets.example.sh` | `backend/deploy/upgrade-env-secrets.example.sh` | |

### Worker → `backend/src/worker/`

| 现状 | 目标 | 备注 |
|---|---|---|
| `services/worker/src/` (3 文件) | `backend/src/worker/` | 合并入同一 Python 包 |
| `services/worker/pyproject.toml` | **删除**（合并到 backend/pyproject.toml） | |
| `services/worker/Dockerfile` | **删除**（共用 backend/Dockerfile + SERVICE_ROLE） | |
| `services/worker/.dockerignore` | **删除** | |

### 前端 → `frontend/`

| 现状 | 目标 | 备注 |
|---|---|---|
| `app/` (13 文件) | `frontend/app/` | **原样**移动 |
| `app/globals.css` | `frontend/src/styles/globals.css` | **原样**移动（**不动**） |
| `build/` | `frontend/build/` | 1 文件 (sites-vite-plugin.ts) |
| `public/` | `frontend/public/` | 5 文件 |
| `deploy/web-server.mjs` | `frontend/deploy/web-server.mjs` | |
| `Dockerfile.web` | `frontend/Dockerfile.web` | |
| `next.config.ts` | `frontend/next.config.ts` | |
| `vite.config.ts` | `frontend/vite.config.ts` | 包含我之前加的 /api proxy |
| `tsconfig.json` | `frontend/tsconfig.json` | |
| `package.json` | `frontend/package.json` | 包含我之前修的 vinext dev |
| `package-lock.json` | `frontend/package-lock.json` | |
| `postcss.config.mjs` | `frontend/postcss.config.mjs` | |
| `eslint.config.mjs` | `frontend/eslint.config.mjs` | |
| `examples/` | **删除**（未使用） | |

### 顶层 `scripts/` 改造

| 现状 | 处理 |
|---|---|
| `scripts/compose.sh` | 改调用 `backend/deploy/compose/` |
| `scripts/start.sh`, `stop.sh`, `status.sh` | 改 `cd backend` 后调 docker compose |
| `scripts/smoke-test.sh` | 改端点路径适配新结构 |
| `scripts/backup.sh`, `restore.sh`, `verify-backup.sh` | 路径前加 `backend/` |
| `scripts/upgrade-env-secrets.sh` | 移到 `backend/deploy/`，保留 `scripts/` 软链或直接调用 |
| `scripts/seed-demo.sh`, `bootstrap-admin.sh`, `create-executive.sh` | 移到 `backend/scripts/` |
| `scripts/assert-production-artifact.mjs` | 移到 `frontend/scripts/` |
| `scripts/resolve-alembic-head.py` | 移到 `backend/scripts/` |
| `scripts/build-production.sh` | 移到 `frontend/scripts/`（前端专属） |
| `scripts/start-release.sh` | 移到 `backend/scripts/`（后端专属） |
| `scripts/test-infra.sh` | 移到 `backend/scripts/` |
| `scripts/logs.sh` | 留顶层（调 docker compose） |

### 删除

- `db/`（Drizzle，生产未启用）
- `drizzle/`（同上）
- `services/`（整体，已迁出）
- `deploy/`（整体，已迁出）
- `examples/`（未使用）
- `tests/`（顶层空目录，迁到 `backend/tests/`）

### 顶层保留 / 新增

- `Makefile`（按 §3.5 改造）
- `README.md`（更新）
- `.gitignore`（更新：`/frontend/node_modules`、`/backend/.venv` 等）
- `.nvmrc`（新增：Node 22.13+）
- `.python-version`（新增：Python 3.12+）
- `package.json`（顶层只保留 devDeps，**不引入 pnpm workspace**）
- `pyproject.toml`（顶层占位或不建）
- 顶层 `scripts/` 留 5-6 个编排脚本

## Phase 1 配置统一（Step 6）

按 §4.1：

```
backend/configs/
├── schema.py                  # Pydantic AppConfig + DatabaseConfig + CookieConfig + WorkerConfig + ApiConfig + ProfileConfig
├── loader.py                  # 从 yaml + env + secret 合并
├── profile.local-demo.yaml
├── profile.customer-template.yaml
├── profile.production.yaml
├── secrets.schema.yaml
├── alembic-revision.txt       # 由 alembic 脚本生成
└── README.md
```

**改动**：
- `backend/src/executive_ai_api/config.py` 改为薄壳，委托给 `backend/configs/schema.py`
- 启动护栏统一到 `AppConfig.model_validator`
- `compose.yml` 业务环境变量删除，改 `env_file: backend/deploy/environments/<env>.env`
- `routers/health.py` 的 `EXPECTED_DATABASE_REVISION` 改读 config
- 容器入口前置 `python -m executive_ai_api.configs.loader --validate`
- 新建 `backend/scripts/check-config-drift.sh`

## 当前 git 状态

```
modified:   app/page.tsx
modified:   package-lock.json
modified:   package.json
modified:   vite.config.ts
deleted:    app/page.production.tsx
untracked:  backend/ frontend/ shared/  ← 本次新建（空目录）
untracked:  docs/architecture/0004-refactor-plan.md
untracked:  docs/architecture/0004-migration-status.md  ← 本文件
untracked:  scripts/create_admin.py
untracked:  services/api/.env  services/api/local.db  services/api/.runtime/  ← 不应该提交
```

## 建议执行顺序

1. **用户先 commit 当前 6 个 uncommitted changes**（v3: dev server 修复 + page.production 删除）
2. **用户 commit 我新增的辅助文件**（create_admin.py + 本 status 文档 + refactor-plan v2）
3. 我开始 Step 2 `git mv`（这是无逻辑变更的纯移动）
4. 我开始 Step 3 `git mv`
5. 我开始 Step 4 worker 合并
6. 我开始 Step 5 Makefile + 顶层 scripts
7. 我开始 Step 6 Phase 1 配置统一
8. 我跑 Step 7 验证

**rollback plan**：每个 Step 独立 commit，每步失败可 `git reset --hard HEAD~1` 回退。

## 不在本 PR 范围（按用户决定）

- `app/prototype-data.ts`（667 行）— 下个 PR 迁到 `backend/src/executive_ai_api/seed/sanitized_fixtures.py`
- Phase 2 跨端契约
- Phase 3 前端结构拆分
- Phase 4 后端分层
- Phase 5/6 可观测性 + 演进接口
