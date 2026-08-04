-- =====================================================================
-- Executive AI Secretary — backend/scripts/creat.sql
-- =====================================================================
-- 创建企业 + 组织单元 + 5 个账号（admin / executive / sub-admin / fde）。
-- 用法（从 backend/ 目录执行）：
--
--     psql "$DATABASE_URL" -f scripts/creat.sql
--
-- 前置：alembic upgrade head 已跑过（26 张业务表存在）。
-- 环境：backend/.env 中 DATABASE_URL / SESSION_SECRET / AUDIT_HMAC_KEY /
--      FILE_ENCRYPTION_KEY 已配置。
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

BEGIN;

INSERT INTO enterprises (id, name, slug, is_active, settings_json, created_at, updated_at)
VALUES (gen_random_uuid(), '示例集团', 'acme', true, '{"fixture": "manual-bootstrap"}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (slug) DO NOTHING;

INSERT INTO organization_units (id, enterprise_id, parent_id, name, code, unit_type, enabled_for_analysis, data_connected, sort_order, is_active, config_json, created_at, updated_at)
SELECT gen_random_uuid(), e.id, NULL, u.name, u.code, 'business_unit', true, true, u.sort_order, true, '{"fixture": "manual-bootstrap"}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM enterprises e, (VALUES ('华东事业部', 'east-china', 10), ('华南事业部', 'south-china', 20)) AS u(name, code, sort_order)
WHERE e.slug = 'acme'
ON CONFLICT (enterprise_id, code) DO NOTHING;

COMMIT;

\! echo 'AdminP@ss123!' | python -m utils.cli create-admin --email admin@acme.com --display-name "示例管理员" --enterprise-name "示例集团" --enterprise-slug acme --password-stdin --force-password-change

\! echo 'CeoP@ss123!!!' | python -m utils.cli create-user --enterprise-slug acme --email ceo@acme.com --display-name "示例高管" --role executive --enterprise-wide-scope --password-stdin --force-password-change

\! echo 'EastBossP@ss123!' | python -m utils.cli create-user --enterprise-slug acme --email east-boss@acme.com --display-name "华东负责人" --role executive --organization-unit-code east-china --password-stdin --force-password-change

\! echo 'Admin2P@ss123!!' | python -m utils.cli create-user --enterprise-slug acme --email admin2@acme.com --display-name "示例副管理员" --role enterprise_admin --enterprise-wide-scope --password-stdin --force-password-change

\! echo 'FdeP@ss123!!!' | python -m utils.cli create-user --enterprise-slug acme --email fde@acme.com --display-name "示例 FDE" --role fde --organization-unit-code east-china --password-stdin --force-password-change
