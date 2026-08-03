"""Alembic 运行环境。

参考项目 ``anspire_atomic_power_backend/migrations/env.py`` 的模式：

- 自举 ``sys.path`` 把项目根加入路径（兼容 ``alembic`` CLI 不会自动读 ``pyproject.toml`` 的情况）
- 从 ``configs`` 注入同步数据库 URL，覆盖 ini 中任何占位值
- ``from models import Base`` 与 ``import models`` 双写法：前者让 ``target_metadata`` 指向完整 metadata，
  后者兜底触发 ``models/__init__.py`` 中所有 ORM 模块的 ``Base`` 注册（避免漏表）

差异点（相对参考项目）：

- ``prepend_sys_path = src`` 在 ini 中已经声明，这里再做一次 ``sys.path.append`` 是双保险
- ``compare_type=True`` 在 offline/online 都打开，让 autogenerate 能识别列类型变更
- offline 模式也走 ``target_metadata``，便于本地打印 SQL 时与在线保持一致
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---- 路径自举（参考项目做法）----
# alembic CLI 在某些环境下不会自动把 backend 根加入 sys.path；
# 这里显式补一次，让 ``from configs.xxx import ...``、``from models import ...`` 永远能找到。
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_SRC_DIR = os.path.join(_PROJECT_ROOT, "src")
for _entry in (_PROJECT_ROOT, _SRC_DIR):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from configs.settings import get_settings  # noqa: E402
from models import Base  # noqa: E402,E501 — alembic 通过 Base.metadata 找到全部 ORM
import models  # noqa: E402,F401 — 兜底触发 models 包下所有 ORM 模块的 Base 注册

# Alembic Config 对象，提供对 .ini 文件中值的访问。
config = context.config

# 解析 .ini 中的 Python logging 配置。
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---- 数据库 URL 注入 ----
# 不在 ini 中写死数据库 URL，避免多环境切换时修改 ini；统一从环境变量 / .env 派生。
# 密码中可能含有 ``%``，必须 ``%%`` 转义，否则 ConfigParser 解析会抛错。
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

# 目标 metadata：包含全部 ORM 模型，用于 ``alembic revision --autogenerate``。
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：只渲染 SQL，不连库。"""

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：直连数据库执行迁移。"""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
