# Executive AI Secretary 启动指南

本文件包含前端、后端 API、worker 三个服务的本地启动命令。

> 约定：项目根目录为 `d:\anchnet\executive-ai-secretary`，下文用 `%ROOT%` 代指。

---

## 架构说明

hermes-runtime 已合并进 worker 进程（`backend/src/worker/hermes_runtime.py`），**不再作为独立服务/目录存在**。

```
frontend (3000) ──HTTP──> backend API (8000)
                             │
                             ├── 写库 + NOTIFY new_job ──> PostgreSQL
                             │                                │
worker ◄── LISTEN new_job ───────────────────────────────────┘
   └─ claim_one → ThreadPoolExecutor 异步执行 process
        └─ hermes_runtime.execute_run() 进程内调用
             └─ subprocess: hermes --oneshot (MCP 工具循环) → Anspire
```

worker 支持并发执行（`WORKER_CONCURRENCY`，默认 2），claim 与 process 解耦，单个 job 阻塞不会卡住其他 job。

---

## 1. 前端（frontend）

技术栈：Next.js 16 + React 19 + Vite（vinext），Node ≥ 22.13，默认端口 `3000`。

```powershell
# 1) 进入目录
Set-Location $env:ROOT\frontend

# 2) 首次需安装依赖
npm install

# 3) 启动开发服务（http://localhost:3000）
npm run dev
```

- 生产模式：`npm run build` 后 `npm run start`
- 类型检查：`npm run typecheck`
- 代码检查：`npm run lint`

---

## 2. 后端 API（backend）

技术栈：FastAPI + Uvicorn + SQLAlchemy + Alembic，Python ≥ 3.12，使用 `uv` 管理依赖。

```powershell
# 1) 进入目录
Set-Location $env:ROOT\backend

# 2) 首次需创建虚拟环境并安装依赖
uv venv
uv sync

# 3) 启动 API（http://0.0.0.0:8000）
.\.venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000
```

- 开发热重载：`.\.venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000 --reload`
- 数据库迁移（首次或 schema 变更后）：`.\.venv\Scripts\alembic.exe upgrade head`
- 配置项（数据库、hermes 等）见 `backend/src/configs/settings.py`，可通过环境变量覆盖。

---

## 3. Worker（backend/src/worker，内置 hermes-runtime）

Worker 复用 backend 的虚拟环境与代码，通过 `main.py` 的 `--worker` 参数启动，独立占用进程轮询 jobs 表。hermes-runtime 内嵌在 worker 进程中，无需单独启动。

### 环境准备

worker 需要 `hermes-agent` 依赖，安装方式：

```powershell
Set-Location $env:ROOT\backend
uv sync --extra hermes
```

### 启动命令

```powershell
# 纯 worker 模式（前台运行，不启动 API）
$env:SERVICE_ROLE = "assistant_worker"
.\.venv\Scripts\python.exe main.py --worker

# 开发模式：worker 后台线程 + API 同进程
$env:SERVICE_ROLE = "assistant_worker"
.\.venv\Scripts\python.exe main.py --worker --api
```

### 关键配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `SERVICE_ROLE` | `api` | worker 模式需设为 `assistant_worker` |
| `WORKER_CONCURRENCY` | `2` | 进程内并发执行 job 数，建议与 `HERMES_MAX_CONCURRENT_RUNS` 对齐 |
| `WORKER_POLL_SECONDS` | `2.0` | 兜底轮询间隔（NOTIFY 机制下仅在超时或通知丢失时触发） |
| `WORKER_LEASE_SECONDS` | `60` | job 租约时长 |
| `WORKER_HEARTBEAT_SECONDS` | `15` | 心跳续约间隔 |

### 事件驱动模型

worker 使用 PostgreSQL **LISTEN/NOTIFY** 事件驱动：API 创建 job 时发 `NOTIFY new_job`，worker 收到通知才 claim，无 job 时阻塞等待（零空轮询）。每 60s 做一次兜底 claim，处理 NOTIFY 丢失的边界情况。

claim 到 job 后丢进 `ThreadPoolExecutor` 异步执行 `process`，主线程立即处理下一条通知。`claim_one` 使用 `SELECT FOR UPDATE SKIP LOCKED`，多 worker 实例并发安全。

---

## 启动顺序建议

1. **backend API**（前端依赖）
2. **worker**（轮询 jobs 表，被 API 写入）
3. **frontend**（依赖 backend API）

各服务默认端口：

| 服务          | 端口  |
| ------------- | ----- |
| frontend      | 3000  |
| backend API   | 8000  |
| worker        | 无（后台进程，轮询数据库） |
