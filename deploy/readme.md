cd deploy
# 1. 生成 .env（首次）
# 2. 先启动 db
API_PORT=8080 FRONTEND_PORT=3080 docker compose up -d db
# 3. 等 db healthy 后，跑数据库迁移+初始化
API_PORT=8080 FRONTEND_PORT=3080 docker compose run --rm init
# 4. 启动全部服务
API_PORT=8080 FRONTEND_PORT=3080 docker compose up -d
