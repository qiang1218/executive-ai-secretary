"""File asset repository: 纯数据访问，模块级函数 + ``db: AsyncSession`` 第一参数。

遵循 ``repositories/audit.py`` 风格：不引入 Repository 类，仅提供按
``find_by_xxx`` / ``list_by_xxx`` / ``save`` 命名的查询函数。Service 层
通过 ``from repositories import file_asset as file_asset_repo`` 后调用
``await file_asset_repo.find_xxx(self._session, ...)``。

仅搬运查询语句，不包含业务逻辑（业务校验、审计、commit 仍由 service 负责）。
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import FileAsset
from services.authz import Principal


async def find_by_id(db: AsyncSession, file_id: uuid.UUID | str) -> FileAsset | None:
    """按主键查询文件。"""
    return await db.scalar(select(FileAsset).where(FileAsset.id == file_id))


async def find_owned(
    db: AsyncSession,
    principal: Principal,
    file_id: uuid.UUID | str,
) -> FileAsset | None:
    """按 id + enterprise_id + uploaded_by_user_id 查询（所有权校验）。

    Admin/FDE 不能借角色读取高管文件，查询以 ``uploaded_by_user_id`` 收口，
    同时过滤 ``deleted_at IS NULL``。

    返回 FileAsset 或 None（不抛错，业务层负责抛 404）。

    来源：file_service.owned_file / get_file_extraction / download_file /
    delete_file、job_management_service.create_job。
    """
    return await db.scalar(
        select(FileAsset).where(
            FileAsset.id == file_id,
            FileAsset.enterprise_id == principal.enterprise_id,
            # Admin/FDE cannot use their role to read an executive's files.
            FileAsset.uploaded_by_user_id == principal.user.id,
            FileAsset.deleted_at.is_(None),
        )
    )


async def list_by_owner(
    db: AsyncSession,
    principal: Principal,
    *,
    limit: int = 100,
) -> list[FileAsset]:
    """列出 owner 的未删除文件（按创建时间倒序，默认 100 条）。"""
    result = await db.scalars(
        select(FileAsset)
        .where(
            FileAsset.enterprise_id == principal.enterprise_id,
            FileAsset.uploaded_by_user_id == principal.user.id,
            FileAsset.deleted_at.is_(None),
        )
        .order_by(FileAsset.created_at.desc())
        .limit(limit)
    )
    return list(result.all())


async def save(db: AsyncSession, file_asset: FileAsset) -> FileAsset:
    """add + flush，返回已 flush 的实体（含主键）。"""
    db.add(file_asset)
    await db.flush()
    return file_asset
