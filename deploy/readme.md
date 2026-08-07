# Executive AI Secretary — Docker 部署

## 架构

```
浏览器 → nginx(:3000) ─┬─ /api/  → api(:8000) → db(:5432)
                        └─ /     → frontend-vinext(:3001)
api(:8000) → worker(:8001)   # 内部 RPC（chat completions / profile run）
```

服务说明：

| 服务              | 镜像                      | 说明                                   |
| ----------------- | ------------------------- | -------------------------------------- |
| db                | pgvector/pgvector:pg16    | PostgreSQL 16 + pgvector               |
| api               | executive-ai-backend      | FastAPI 后端，`SERVICE_ROLE=api`       |
| worker            | executive-ai-backend      | FastAPI Worker，`SERVICE_ROLE=assistant_worker` |
| frontend-vinext   | executive-ai-frontend-vinext | vinext SSR 服务，内部 :3001            |
| frontend          | executive-ai-frontend     | nginx 反向代理，对外 :3000             |
| init              | executive-ai-backend      | 一次性初始化（迁移 + 建企业 + 建用户） |

## 首次部署

### 1. 准备环境变量

```bash
cd deploy
cp .env.docker.example .env
# 编辑 .env，生产环境必须重新生成所有密钥
```

### 2. 启动数据库

```bash
docker compose up -d db
# 等待 db healthy（约 30s）
docker compose ps db
```

### 3. 跑初始化（迁移 + 建企业 + 建用户）

```bash
docker compose run --rm init
```

### 4. 启动全部服务

```bash
docker compose up -d
```

访问 `http://localhost:${FRONTEND_PORT:-3000}`，使用 init 阶段创建的账号登录。

## 日常运维

```bash
docker compose up -d            # 启动
docker compose down             # 停止
docker compose logs -f api      # 查看 API 日志
docker compose logs -f worker   # 查看 Worker 日志
docker compose restart api      # 重启 API
docker compose build            # 重新构建镜像
```

## 默认账号（仅 init 阶段创建）

| 邮箱              | 密码             | 角色           |
| ----------------- | ---------------- | -------------- |
| admin@acme.com    | AdminP@ss123!    | 管理员         |
| ceo@acme.com      | CeoP@ss123!!!    | 高管（全量）   |
| east-boss@acme.com| EastBossP@ss123! | 华东负责人     |
| admin2@acme.com   | Admin2P@ss123!!  | 副管理员       |
| fde@acme.com      | FdeP@ss123!!!    | FDE（华东）    |

生产环境请在首次登录后立即修改密码。

## 关键配置说明

- **APP_ENV**：`production` 时启用密钥强度校验，禁用 demo 数据
- **APP_MODE**：`production` / `demo`，前端通过 `NEXT_PUBLIC_APP_MODE` 在构建期切换
- **COOKIE_SECURE**：生产环境（HTTPS）必须设 `true`
- **WORKER_BASE_URL**：API 调用 worker 的地址，compose 内固定为 `http://worker:8001`
- **CAPABILITY_HMAC_KEY**：worker 与 API 之间 capability token 的 HMAC 密钥
