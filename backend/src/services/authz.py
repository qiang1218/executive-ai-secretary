from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import Settings, get_settings
from core.principal import Principal
from core.security import as_utc, secure_equal, token_hash, utc_now
from db.session import get_db_async
from exceptions.errors import AppError
from models import DataScopeGrant, Enterprise, OrganizationUnit, User, UserSession


__all__ = ["Principal"]


async def _read_session(
    request: Request,
    db: AsyncSession,
    settings: Settings,
) -> Principal:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise AppError(401, "authentication_required", "请先登录")
    hashed = token_hash(raw_token, settings.session_secret.get_secret_value())
    result = await db.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(UserSession.token_hash == hashed)
    )
    row = result.one_or_none()
    if row is None:
        raise AppError(401, "invalid_session", "登录状态无效，请重新登录")
    user_session, user = row
    now = utc_now()
    if (
        user_session.revoked_at
        or as_utc(user_session.expires_at) <= now
        or as_utc(user_session.idle_expires_at) <= now
    ):
        raise AppError(401, "session_expired", "登录已过期，请重新登录")
    if not user.is_active:
        raise AppError(403, "user_disabled", "账号已停用")
    if user.locked_until and as_utc(user.locked_until) > now:
        raise AppError(423, "user_locked", "账号暂时锁定")
    enterprise = await db.get(Enterprise, user.enterprise_id)
    if enterprise is None or not enterprise.is_active:
        raise AppError(403, "enterprise_disabled", "企业账号不可用")
    if as_utc(user_session.last_seen_at) < now - timedelta(minutes=5):
        user_session.last_seen_at = now
        user_session.idle_expires_at = min(
            as_utc(user_session.expires_at),
            now + timedelta(seconds=settings.session_idle_seconds),
        )
        await db.commit()
    return Principal(user=user, session=user_session)


async def get_authenticated_principal(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_async)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Principal:
    cached = getattr(request.state, "principal", None)
    if isinstance(cached, Principal):
        return cached
    principal = await _read_session(request, db, settings)
    request.state.principal = principal
    return principal


async def get_current_principal(
    principal: Annotated[Principal, Depends(get_authenticated_principal)],
) -> Principal:
    if principal.user.password_change_required:
        raise AppError(
            403,
            "password_change_required",
            "首次登录需要先修改密码",
        )
    return principal


async def get_executive_principal(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Principal:
    if principal.user.role != "executive":
        raise AppError(403, "role_forbidden", "当前角色无权使用经营业务工作台")
    return principal


async def csrf_protect(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_async)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if request.url.path == f"{settings.api_prefix}/auth/login":
        return
    principal = await _read_session(request, db, settings)
    header = request.headers.get("X-CSRF-Token", "")
    cookie = request.cookies.get(settings.csrf_cookie_name, "")
    if not header or not cookie or not secure_equal(header, cookie):
        raise AppError(403, "csrf_failed", "安全校验失败，请刷新页面后重试")
    expected = token_hash(header, settings.csrf_secret.get_secret_value())
    if not secure_equal(expected, principal.session.csrf_hash):
        raise AppError(403, "csrf_failed", "安全校验失败，请刷新页面后重试")


def require_roles(*roles: str):
    async def dependency(
        principal: Annotated[Principal, Depends(get_current_principal)],
    ) -> Principal:
        if principal.user.role not in roles:
            raise AppError(403, "role_forbidden", "当前角色无权执行此操作")
        return principal

    return dependency


async def accessible_organization_unit_ids(
    db: AsyncSession, principal: Principal
) -> set[uuid.UUID]:
    return await accessible_organization_unit_ids_for_user(db, principal.user)


async def accessible_organization_unit_ids_for_user(
    db: AsyncSession, user: User
) -> set[uuid.UUID]:
    analyzable_unit = (
        OrganizationUnit.enterprise_id == user.enterprise_id,
        OrganizationUnit.is_active.is_(True),
        OrganizationUnit.enabled_for_analysis.is_(True),
        OrganizationUnit.data_connected.is_(True),
    )
    result = await db.execute(
        select(DataScopeGrant).where(
            DataScopeGrant.user_id == user.id,
            DataScopeGrant.can_read.is_(True),
        )
    )
    grants = result.scalars().all()
    if any(grant.scope_kind == "enterprise" for grant in grants):
        result = await db.execute(
            select(OrganizationUnit.id).where(*analyzable_unit)
        )
        return set(result.scalars().all())
    granted_root_ids = {
        grant.organization_unit_id for grant in grants if grant.organization_unit_id is not None
    }
    result = await db.execute(
        select(OrganizationUnit.id).where(
            OrganizationUnit.id.in_(granted_root_ids),
            *analyzable_unit,
        )
    )
    roots = set(result.scalars().all())
    if not roots:
        return set()
    # The hierarchy is intentionally only one level deep; include configured descendants later.
    accessible = set(roots)
    while True:
        result = await db.execute(
            select(OrganizationUnit.id).where(
                OrganizationUnit.parent_id.in_(accessible),
                *analyzable_unit,
            )
        )
        children = set(result.scalars().all())
        expanded = accessible | children
        if expanded == accessible:
            return accessible
        accessible = expanded


async def assert_org_scope(
    db: AsyncSession,
    principal: Principal,
    organization_unit_id: uuid.UUID | None,
    *,
    allowed: set[uuid.UUID] | None = None,
) -> None:
    """断言 principal 可访问指定事业部。

    传入 ``allowed`` 可跳过 ``accessible_organization_unit_ids`` 查询，
    用于列表场景下避免 N+1（同一 principal 多次调用时结果不变）。
    """
    if allowed is None:
        allowed = await accessible_organization_unit_ids(db, principal)
    if not allowed:
        raise AppError(403, "data_scope_forbidden", "当前账号没有有效的事业部查询范围")
    if organization_unit_id is not None and organization_unit_id not in allowed:
        raise AppError(403, "data_scope_forbidden", "该事业部不在您的可查询范围内")


async def build_scope_snapshot(
    db: AsyncSession,
    principal: Principal,
    organization_unit_id: uuid.UUID | None = None,
) -> dict[str, object]:
    await assert_org_scope(db, principal, organization_unit_id)
    result = await db.execute(
        select(DataScopeGrant).where(
            DataScopeGrant.user_id == principal.user.id,
            DataScopeGrant.can_read.is_(True),
        )
    )
    grants = result.scalars().all()
    enterprise_wide = organization_unit_id is None and any(
        item.scope_kind == "enterprise" for item in grants
    )
    if organization_unit_id is not None:
        unit_ids = [organization_unit_id]
    else:
        allowed = await accessible_organization_unit_ids(db, principal)
        unit_ids = sorted(allowed, key=str)
    return {
        "enterprise_wide": enterprise_wide,
        "organization_unit_ids": [str(item) for item in unit_ids],
    }


async def build_assistant_scope_snapshot(
    db: AsyncSession,
    principal: Principal,
    organization_unit_id: uuid.UUID | None = None,
) -> dict[str, object]:
    """Snapshot assistant authority without making general Q&A depend on data grants.

    A user without an analyzable organization may still use the assistant for general
    reasoning.  Such a job is permanently marked ``general_only`` so a later routing
    decision cannot turn it into a business-data query without a new authorization
    snapshot.
    """

    allowed = await accessible_organization_unit_ids(db, principal)
    if organization_unit_id is not None or allowed:
        return await build_scope_snapshot(db, principal, organization_unit_id)
    return {
        "enterprise_wide": False,
        "organization_unit_ids": [],
        "general_only": True,
    }


async def scope_snapshot_is_current_for_user(
    db: AsyncSession,
    user: User,
    snapshot: dict[str, object] | None,
    *,
    current: set[uuid.UUID] | None = None,
) -> bool:
    """Fail closed unless every snapshotted unit remains usable and granted.

    传入 ``current`` 可跳过 ``accessible_organization_unit_ids_for_user`` 查询，
    用于列表场景下避免 N+1（同一 user 多次调用时结果不变）。
    """
    if not snapshot:
        return False
    try:
        required = {uuid.UUID(str(value)) for value in snapshot.get("organization_unit_ids", [])}
    except (TypeError, ValueError):
        return False
    if not required:
        return snapshot.get("general_only") is True
    if current is None:
        current = await accessible_organization_unit_ids_for_user(db, user)
    if not required.issubset(current):
        return False
    if snapshot.get("enterprise_wide"):
        result = await db.scalar(
            select(DataScopeGrant.id).where(
                DataScopeGrant.user_id == user.id,
                DataScopeGrant.scope_kind == "enterprise",
                DataScopeGrant.can_read.is_(True),
            )
        )
        return result is not None
    return True


async def organization_scope_predicate(
    db: AsyncSession, principal: Principal, column
):
    allowed = await accessible_organization_unit_ids(db, principal)
    # Enterprise-neutral records remain visible only when explicitly unscoped.
    return or_(column.is_(None), column.in_(allowed))
