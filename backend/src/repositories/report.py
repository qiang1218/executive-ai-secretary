"""Report repository: 纯数据访问，模块级函数 + ``db: AsyncSession`` 第一参数。

遵循 ``repositories/audit.py`` 风格：不引入 Repository 类，仅提供按
``find_by_xxx`` / ``list_by_xxx`` / ``save`` 命名的查询函数。Service 层
通过 ``from repositories import report as report_repo`` 后调用
``await report_repo.find_xxx(self._session, ...)``。

仅搬运查询语句，不包含业务逻辑（org scope 校验、审计、commit 仍由 service 负责）。
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Report, ReportVersion
from core.principal import Principal


async def find_by_id(db: AsyncSession, report_id: uuid.UUID | str) -> Report | None:
    """按主键查询简报。"""
    return await db.scalar(select(Report).where(Report.id == report_id))


async def find_owned(
    db: AsyncSession,
    principal: Principal,
    report_id: uuid.UUID | str,
) -> Report | None:
    """按 id + enterprise_id + created_by_user_id 查询（所有权校验）。

    一期简报保持创建者私有，查询以 ``created_by_user_id`` 收口。
    注意：org scope 校验（``assert_org_scope``）仍由 service 层负责，
    本函数只搬运原始查询语句。

    返回 Report 或 None（不抛错，业务层负责抛 404 与 org scope）。

    来源：report_service.owned_report / get_report、
    job_management_service.create_job。
    """
    return await db.scalar(
        select(Report).where(
            Report.id == report_id,
            Report.enterprise_id == principal.enterprise_id,
            # Executive reports remain creator-private in phase one.
            Report.created_by_user_id == principal.user.id,
        )
    )


async def find_latest_version(db: AsyncSession, report_id: uuid.UUID | str) -> ReportVersion | None:
    """查询 report 的最新版本（按 version 倒序取首条）。"""
    return await db.scalar(
        select(ReportVersion)
        .where(ReportVersion.report_id == report_id)
        .order_by(ReportVersion.version.desc())
        .limit(1)
    )


async def list_by_owner(
    db: AsyncSession,
    principal: Principal,
    *,
    kind: str | None = None,
    limit: int = 100,
) -> list[Report]:
    """列出 owner 的 reports，可选 kind 过滤（按 period_end 倒序，默认 100 条）。

    注意：调用方仍需在 Python 层对返回结果做 ``assert_org_scope`` 过滤
    （见 report_service.list_reports）。
    """
    statement = select(Report).where(
        Report.enterprise_id == principal.enterprise_id,
        Report.created_by_user_id == principal.user.id,
    )
    if kind:
        statement = statement.where(Report.kind == kind)
    statement = statement.order_by(Report.period_end.desc()).limit(limit)
    result = await db.execute(statement)
    return list(result.scalars().all())


async def save(db: AsyncSession, report: Report) -> Report:
    """add + flush，返回已 flush 的实体（含主键）。"""
    db.add(report)
    await db.flush()
    return report
