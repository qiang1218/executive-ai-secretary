# 后端初始化操作指南

> 适用于新环境部署 / 本地开发首次启动。

## 前置条件

- Python ≥ 3.12
- PostgreSQL ≥ 14（启用 `pgcrypto` 扩展）
- 已安装依赖：`pip install -e backend/`

## 1. 环境变量配置

```bash
cp backend/.env.example backend/.env
# 编辑 .env，填入真实的 DATABASE_URL / SESSION_SECRET / CSRF_SECRET / AUDIT_HMAC_KEY /
# FILE_ENCRYPTION_KEY / INTEGRATION_ENCRYPTION_KEY 等值
```

**关键变量说明**：

| 变量 | 说明 | 必填 |
|---|---|---|
| `APP_ENV` | `development` / `test` / `local-demo` / `customer-template` / `production` | ✅ |
| `APP_MODE` | `demo`（使用演示数据集）或 `production`（真实数据） | ✅ |
| `DATABASE_URL` | PostgreSQL 连接串，驱动用 `postgresql+psycopg` | ✅ |
| `FILE_STORAGE_ROOT` | 文件存储根目录（代码读此变量，**不读** `STORAGE_BACKEND`/`LOCAL_STORAGE_PATH`） | ✅ |
| `FILE_ENCRYPTION_KEY` | 文件加密密钥（32 字节 URL-safe base64） | ✅ |
| `INTEGRATION_ENCRYPTION_KEY` | 模型供应商 API key / 高管画像加密密钥（32 字节 URL-safe base64） | ✅ |
| `SESSION_SECRET` | Session 签名密钥（≥32 字符） | ✅ |
| `CSRF_SECRET` | CSRF token 签名密钥（≥32 字符） | ✅ |
| `AUDIT_HMAC_KEY` | 审计链 HMAC 密钥（≥32 字符） | ✅ |
| `TRUSTED_HOSTS` | CSV，受信任的 Host header 值 | ✅ |
| `ALLOWED_ORIGINS` | CSV，CORS 允许的前端来源 | ✅ |
| `COOKIE_SECURE` | `true`/`false`，生产环境必须 `true` | ✅ |
| `COOKIE_SAMESITE` | `lax`/`strict`/`none` | ✅ |
| `HERMES_RUNTIME_HMAC_KEY` | Hermes 网关 HMAC 密钥 | ✅ |
| `SOURCE_DATABASE_URL` | 数仓只读副本（不填则用主库） | ❌ |
| `SEED_DEMO_DATA` | `true`/`false`，是否在启动时 seed 演示数据 | ❌ |

生成密钥的命令：

```bash
# 32 字节 URL-safe base64（用于 FILE_ENCRYPTION_KEY / INTEGRATION_ENCRYPTION_KEY）
python -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

# 64 字符随机字符串（用于 SESSION_SECRET / CSRF_SECRET / AUDIT_HMAC_KEY）
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 2. 数据库迁移（Alembic）

```bash
cd backend
alembic upgrade head
```

迁移文件位于 `backend/alembic/versions/`，共 13 个版本，创建 26 张业务表 + 审计链 + 索引。

## 3. 初始化数据

### 方式 A：用 `creat.sql` 一键初始化（推荐）

`backend/scripts/creat.sql` 会创建：
- 1 个企业（`示例集团` / slug=`acme`）
- 2 个事业部（华东 / 华南）
- 5 个账号（admin / executive / sub-admin / fde）

```bash
cd backend
psql "$DATABASE_URL" -f scripts/creat.sql
```

**注意**：`creat.sql` 内部调用 `python -m api.cli create-admin` / `create-user`，所以必须在 `backend/` 目录下执行，且 `.env` 已配置好。

### 方式 B：用 CLI 逐个创建

```bash
cd backend

# 创建管理员
python -m api.cli create-admin \
  --email admin@acme.com \
  --display-name "管理员" \
  --enterprise-name "示例集团" \
  --enterprise-slug acme \
  --password-stdin <<< 'YourPassword123!'

# 创建高管
python -m api.cli create-user \
  --enterprise-slug acme \
  --email ceo@acme.com \
  --display-name "CEO" \
  --role executive \
  --enterprise-wide-scope \
  --password-stdin <<< 'YourPassword123!'
```

CLI 子命令列表：

| 命令 | 说明 |
|---|---|
| `create-admin` | 创建第一个企业管理员 + 企业 |
| `create-user` | 创建普通用户（支持 `--role` / `--organization-unit-code` / `--enterprise-wide-scope`） |
| `configure-source` | 配置数据源连接（PostgreSQL/飞书等） |
| `trigger-sync` | 手动触发数据同步 |
| `reset-data` | 重置演示运营数据 |

### 方式 C：Seed 演示数据（仅 demo 模式）

如果 `APP_MODE=demo` 且 `SEED_DEMO_DATA=true`，应用启动时会自动 seed 演示数据。

也可以手动执行：

```bash
cd backend
python -m repositories.seed acme
```

这会为 `acme` 企业创建演示用的事业部、数据源、数据域状态、每日快照等。

## 4. 启动服务

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

启动后：
- OpenAPI 文档：`http://localhost:8000/api/openapi.json`
- 健康检查：`http://localhost:8000/health/ready`

## 5. 验证

```bash
# 健康检查
curl http://localhost:8000/health/ready

# 登录（用 creat.sql 创建的 admin 账号）
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@acme.com", "password": "AdminP@ss123!"}'
```

## 初始化操作汇总

| 步骤 | 命令 | 说明 |
|---|---|---|
| 1 | `cp .env.example .env` + 编辑 | 配置环境变量 |
| 2 | `alembic upgrade head` | 创建 26 张表 |
| 3 | `psql "$DATABASE_URL" -f scripts/creat.sql` | 创建企业 + 组织 + 5 个账号 |
| 4 | `uvicorn main:app --reload` | 启动服务 |

如果 `APP_MODE=demo`，还可以在第 3 步后执行 `python -m repositories.seed acme` 加载演示数据。
