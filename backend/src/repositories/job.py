"""Job repository: 纯数据访问，模块级函数 + ``db: AsyncSession`` 第一参数。

遵循 ``repositories/audit.py`` 风格：不引入 Repository 类，仅提供按
``find_by_xxx`` / ``list_by_xxx`` / ``save`` 命名的查询函数。Service 层
通过 ``from repositories import job as job_repo`` 后调用
``await job_repo.find_xxx(self._session, ...)``。

仅搬运查询语句，不包含业务逻辑（业务校验、审计、commit 仍由 service 负责）。
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Job
from core.principal import Principal


async def find_by_id(db: AsyncSession, job_id: uuid.UUID | str) -> Job | None:
    """按主键查询任务。"""
    return await db.scalar(select(Job).where(Job.id == job_id))


async def find_by_id_for_update(db: AsyncSession, job_id: uuid.UUID | str) -> Job | None:
    """按主键查询任务并加行锁。

    注意：与 ``user_repo.find_by_id_for_update`` 不同，这里不加方言判断，
    以保持与原 service 层 ``select(...).with_for_update()`` 行为完全一致
    （PostgreSQL 生效，SQLite 静默跳过 with_for_update）。
    """
    return await db.scalar(select(Job).where(Job.id == job_id).with_for_update())


async def find_owned(
    db: AsyncSession,
    principal: Principal,
    job_id: uuid.UUID,
    *,
    lock: bool = False,
) -> Job | None:
    """按 id + enterprise_id + created_by_user_id 查询（所有权校验）。

    ``lock=True`` 时加行锁。返回 Job 或 None（不抛错，业务层负责抛 404 与
    scope_snapshot 校验）。

    来源：job_management_service.visible_job。注意 Job 模型用
    ``created_by_user_id`` 而非 ``owner_user_id``（与 Project 模型不同）。
    """
    statement = select(Job).where(
        Job.id == job_id,
        Job.enterprise_id == principal.enterprise_id,
        Job.created_by_user_id == principal.user.id,
    )
    if lock:
        statement = statement.with_for_update()
    return await db.scalar(statement)


async def list_by_conversation(
    db: AsyncSession,
    enterprise_id: uuid.UUID,
    *,
    job_type: str = "assistant_response",
    limit: int = 100,
) -> list[Job]:
    """按 enterprise_id + job_type 查询任务（用于 resolve_clarification 的源任务查找）。

    注意：当前 ``conversation_service.resolve_clarification`` 是先按
    enterprise_id + job_type='assistant_response' 查最近 100 条任务，再在
    Python 层按 ``payload_json.message_id`` 过滤出源任务；该方法的 message_id
    匹配未在数据库层完成，调用方仍需自行做 payload 过滤。

    参数命名 ``list_by_conversation`` 沿用任务约定，实际过滤维度为
    ``enterprise_id`` + ``job_type``（与原 service 查询一致）。
    """
    result = await db.scalars(
        select(Job)
        .where(
            Job.enterprise_id == enterprise_id,
            Job.job_type == job_type,
        )
        .order_by(Job.created_at.desc())
        .limit(limit)
    )
    return list(result.all())


async def list_by_owner(
    db: AsyncSession,
    principal: Principal,
    *,
    limit: int = 100,
) -> list[Job]:
    """按 owner 列出任务。

    来源：job_management_service.list_jobs。注意原方法固定 ``limit(100)``，
    无游标分页；为保持行为一致，这里默认 limit=100，且不做游标分页。
    调用方仍需在 Python 层做 ``scope_snapshot_is_current_for_user`` 过滤。

    任务描述中的 ``external_only`` / ``cursor_id`` 参数在原 ``list_jobs`` 中
    并未实现，这里保持与原行为一致，不引入未实现的过滤逻辑。
    """
    result = await db.scalars(
        select(Job)
        .where(
            Job.enterprise_id == principal.enterprise_id,
            Job.created_by_user_id == principal.user.id,
        )
        .order_by(Job.created_at.desc())
        .limit(limit)
    )
    return list(result.all())


async def save(db: AsyncSession, job: Job) -> Job:
    """add + flush，返回已 flush 的实体（含主键）。"""
    db.add(job)
    await db.flush()
    return job
