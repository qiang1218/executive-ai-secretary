"""Model provider config repository: 纯数据访问，模块级函数 + ``db: AsyncSession`` 第一参数。

遵循 ``repositories/audit.py`` 风格：不引入 Repository 类，仅提供按
``find_by_xxx`` / ``save`` 命名的查询函数。Service 层通过
``from repositories import model_provider_config as model_config_repo`` 后调用
``await model_config_repo.find_active(self._session, ...)``。

仅搬运查询语句，不包含业务逻辑（业务校验、审计、commit 仍由 service 负责）。
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ModelProviderConfig


async def find_active(
    db: AsyncSession,
    enterprise_id: uuid.UUID | str,
) -> ModelProviderConfig | None:
    """查询企业的模型配置（按 enterprise_id 过滤，返回单条或 None）。

    来源：model_admin_service._get_config、
    harness_admin_service.simulate_harness 中的
    ``select(ModelProviderConfig).where(enterprise_id == ...)`` 查询。
    """
    return await db.scalar(
        select(ModelProviderConfig).where(
            ModelProviderConfig.enterprise_id == enterprise_id
        )
    )


async def find_active_for_update(
    db: AsyncSession,
    enterprise_id: uuid.UUID | str,
) -> ModelProviderConfig | None:
    """同 find_active 但加行锁（``with_for_update``）。

    注意：与原 service 层 ``select(...).with_for_update()`` 行为完全一致
    （PostgreSQL 生效，SQLite 静默跳过 with_for_update）。
    """
    return await db.scalar(
        select(ModelProviderConfig)
        .where(ModelProviderConfig.enterprise_id == enterprise_id)
        .with_for_update()
    )


async def save(db: AsyncSession, config: ModelProviderConfig) -> ModelProviderConfig:
    """add + flush，返回已 flush 的实体（含主键）。"""
    db.add(config)
    await db.flush()
    return config
