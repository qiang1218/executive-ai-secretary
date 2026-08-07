#!/bin/bash
# ============================================================
# Executive AI Secretary — 一次性用户初始化脚本
# ============================================================
# 功能：
#   1. 等待数据库就绪
#   2. 跑 Alembic 迁移（如果未跑过）
#   3. 创建企业 + 组织单元（SQL）
#   4. 创建 5 个用户（CLI）
#
# 幂等：所有操作都 ON CONFLICT DO NOTHING，可重复执行
#
# 用法：
#   docker compose run --rm init
#   或手动：bash deploy/init-seed.sh
# ============================================================
set -euo pipefail

echo "[init] 开始初始化..."

# ─── 1. 等待数据库就绪 ────────────────────────────────────────
echo "[init] 等待数据库就绪..."
MAX_WAIT=60
WAITED=0
while ! python -c "
import sys, psycopg
try:
    conn = psycopg.connect('${DATABASE_URL}'.replace('postgresql+asyncpg://','postgresql://').replace('+psycopg',''), connect_timeout=3)
    conn.close()
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    WAITED=$((WAITED + 1))
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo "[init] 数据库等待超时（${MAX_WAIT}s），退出"
        exit 1
    fi
    echo "[init] 数据库未就绪，重试 ${WAITED}/${MAX_WAIT}..."
    sleep 1
done
echo "[init] 数据库已就绪"

# ─── 2. 跑 Alembic 迁移 ───────────────────────────────────────
echo "[init] 执行 Alembic 迁移..."
alembic upgrade head
echo "[init] 迁移完成"

# ─── 3. 创建企业 + 组织单元 ──────────────────────────────────
echo "[init] 创建企业 + 组织单元..."
python -c "
import sys
sys.path.insert(0, 'src')
from sqlalchemy import text
from db.session import engine

with engine.begin() as conn:
    conn.execute(text('CREATE EXTENSION IF NOT EXISTS pgcrypto'))

    conn.execute(text('''
        INSERT INTO enterprises (id, name, slug, is_active, settings_json, created_at, updated_at)
        VALUES (gen_random_uuid(), '示例集团', 'acme', true,
                '{\"fixture\": \"docker-bootstrap\"}'::jsonb,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (slug) DO NOTHING
    '''))

    conn.execute(text('''
        INSERT INTO organization_units
            (id, enterprise_id, parent_id, name, code, unit_type,
             enabled_for_analysis, data_connected, sort_order, is_active,
             config_json, created_at, updated_at)
        SELECT gen_random_uuid(), e.id, NULL, u.name, u.code, 'business_unit',
               true, true, u.sort_order, true,
               '{\"fixture\": \"docker-bootstrap\"}'::jsonb,
               CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM enterprises e,
             (VALUES
                 ('华东事业部', 'east-china', 10),
                 ('华南事业部', 'south-china', 20)
             ) AS u(name, code, sort_order)
        WHERE e.slug = 'acme'
        ON CONFLICT (enterprise_id, code) DO NOTHING
    '''))

print('[init] 企业 + 组织单元创建完成')
"

# ─── 4. 创建用户 ─────────────────────────────────────────────
echo "[init] 创建用户..."

# 密码通过 stdin 传入，避免命令行参数泄露
create_admin() {
    local email="$1" password="$2" display="$3"
    echo "[init]   创建管理员: $email"
    echo "$password" | python -m utils.cli create-admin \
        --email "$email" \
        --display-name "$display" \
        --enterprise-name "示例集团" \
        --enterprise-slug acme \
        --password-stdin \
        --no-force-password-change 2>&1 | grep -v "already exists" || true
}

create_user() {
    local email="$1" password="$2" display="$3" role="$4" extra="$5"
    echo "[init]   创建用户: $email ($role)"
    echo "$password" | python -m utils.cli create-user \
        --enterprise-slug acme \
        --email "$email" \
        --display-name "$display" \
        --role "$role" \
        $extra \
        --password-stdin \
        --no-force-password-change 2>&1 | grep -v "already exists" || true
}

# 管理员
create_admin "admin@acme.com" "AdminP@ss123!" "示例管理员"

# 高管（企业全量数据权限）
create_user "ceo@acme.com" "CeoP@ss123!!!" "示例高管" "executive" "--enterprise-wide-scope"

# 华东负责人（仅华东数据权限）
create_user "east-boss@acme.com" "EastBossP@ss123!" "华东负责人" "executive" "--organization-unit-code east-china"

# 副管理员
create_user "admin2@acme.com" "Admin2P@ss123!!" "示例副管理员" "enterprise_admin" "--enterprise-wide-scope"

# FDE（华东前线交付工程师）
create_user "fde@acme.com" "FdeP@ss123!!!" "示例 FDE" "fde" "--organization-unit-code east-china"

echo "[init] 用户创建完成"

# ─── 5. 汇总 ─────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "[init] 初始化完成！"
echo "============================================================"
echo ""
echo "可用账号："
echo "  admin@acme.com / AdminP@ss123!       (管理员)"
echo "  ceo@acme.com / CeoP@ss123!!!         (高管, 企业全量)"
echo "  east-boss@acme.com / EastBossP@ss123! (华东负责人)"
echo "  admin2@acme.com / Admin2P@ss123!!    (副管理员)"
echo "  fde@acme.com / FdeP@ss123!!!         (FDE, 华东)"
echo ""
echo "前端地址: http://localhost:${FRONTEND_PORT:-3000}"
echo "API 地址: http://localhost:${API_PORT:-8000}"
echo "============================================================"
