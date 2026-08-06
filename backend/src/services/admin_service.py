"""Admin service.

Follows the anspire service pattern: a class that receives the database
session (and ``Settings`` when needed) in the constructor and exposes
business methods. The ``/admin`` router instantiates ``AdminService(db)``
(or ``AdminService(db, settings)``) and delegates all DB / business logic
here.

The service is responsible for:
    * user management (create / update / reset-password / data-scopes /
      session revocation),
    * organization unit management (create / update with cycle detection),
    * audit event listing (with role-based filtering) and chain verification,
    * runtime status reporting.

All mutating methods record audit events via
:func:`repositories.audit.record_audit` and commit the transaction.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from configs.settings import Settings
from core.security import hash_password, utc_now, validate_new_password
from exceptions.errors import AppError
from models import (
    AuditEvent,
    DataScopeGrant,
    Enterprise,
    OrganizationUnit,
    User,
    UserCredential,
    UserSession,
)
from repositories.audit import record_audit
from repositories.audit_integrity import verify_audit_chain
from repositories import organization_unit as organization_unit_repo
from repositories import user as user_repo
from schemas import (
    AuditEventOut,
    AuditVerification,
    DataScopeUpdate,
    OrganizationUnitCreate,
    OrganizationUnitOut,
    OrganizationUnitUpdate,
    Page,
    RuntimeStatus,
    TemporaryPasswordRequest,
    UserCreate,
    UserOut,
    UserUpdate,
)
from services.authz import Principal


class AdminService:
    """Service for admin operations: users, org units, audit, runtime.

    Mirrors the anspire ``Service`` convention: stateless business logic
    layered on top of a SQLAlchemy ``AsyncSession``. Settings is optional and
    only required for password validation / runtime status.
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings

    # ------------------------------------------------------------------ utils

    async def _lock_enterprise_admin_updates(self, enterprise_id: uuid.UUID) -> None:
        """Serialize administrator mutations inside one enterprise.

        PostgreSQL's row lock is held until the request transaction commits or
        rolls back. That makes the subsequent "last active administrator" check
        and the mutation one critical section, while unrelated enterprises
        remain independent. SQLite deliberately skips the lock because it does
        not support ``SELECT .. FOR UPDATE``; this keeps the lightweight
        unit-test database compatible, while the concurrency guarantee is
        covered against PostgreSQL.
        """
        statement = select(Enterprise.id).where(Enterprise.id == enterprise_id)
        statement = statement.with_for_update()
        if await self._session.scalar(statement) is None:
            raise AppError(404, "enterprise_not_found", "企业不存在")

    async def _enterprise_user(
        self,
        principal: Principal,
        user_id: uuid.UUID,
    ) -> User:
        item = await user_repo.find_enterprise_user(self._session, principal, user_id)
        if item is None:
            raise AppError(404, "user_not_found", "用户不存在")
        return item

    def _require_settings(self) -> Settings:
        if self._settings is None:
            raise AppError(500, "missing_settings", "Settings 未注入")
        return self._settings

    # ------------------------------------------------------------------ users

    async def list_users(self, principal: Principal) -> Page:
        rows = await user_repo.list_by_enterprise(self._session, principal.enterprise_id)
        return Page(items=[UserOut.model_validate(item) for item in rows])

    async def create_user(
        self,
        payload: UserCreate,
        principal: Principal,
        request: Request,
    ) -> UserOut:
        settings = self._require_settings()
        validate_new_password(payload.temporary_password, settings)
        # Email is the login identifier, so it must remain unambiguous across tenants.
        if await user_repo.find_by_email(self._session, payload.email) is not None:
            raise AppError(409, "email_exists", "该邮箱已存在")
        valid_units = set(
            (
                await self._session.scalars(
                    select(OrganizationUnit.id).where(
                        OrganizationUnit.enterprise_id == principal.enterprise_id,
                        OrganizationUnit.id.in_(payload.organization_unit_ids),
                        OrganizationUnit.is_active.is_(True),
                    )
                )
            ).all()
        )
        if valid_units != set(payload.organization_unit_ids):
            raise AppError(422, "invalid_organization_unit", "一个或多个事业部无效")
        user = User(
            enterprise_id=principal.enterprise_id,
            email=payload.email,
            display_name=payload.display_name,
            preferred_name=payload.preferred_name,
            role=payload.role,
            password_change_required=True,
        )
        await user_repo.save(self._session, user)
        self._session.add(
            UserCredential(
                user_id=user.id,
                password_hash=hash_password(payload.temporary_password),
            )
        )
        if payload.enterprise_wide_scope:
            self._session.add(
                DataScopeGrant(user_id=user.id, scope_kind="enterprise", can_read=True)
            )
        else:
            for unit_id in valid_units:
                self._session.add(
                    DataScopeGrant(
                        user_id=user.id,
                        scope_kind="organization_unit",
                        organization_unit_id=unit_id,
                        can_read=True,
                    )
                )
        await record_audit(
            self._session,
            request,
            "admin.user_created",
            actor=principal.user,
            session=principal.session,
            target_type="user",
            target_id=user.id,
            metadata={
                "role": user.role,
                "scope_count": len(valid_units),
                "enterprise_wide": payload.enterprise_wide_scope,
            },
        )
        await self._session.commit()
        return UserOut.model_validate(user)

    async def update_user(
        self,
        user_id: uuid.UUID,
        payload: UserUpdate,
        principal: Principal,
        request: Request,
    ) -> UserOut:
        # The enterprise lock must be acquired before loading the target or
        # counting administrators. Under PostgreSQL READ COMMITTED, a waiter
        # then observes the preceding transaction's committed role/active-state
        # changes.
        await self._lock_enterprise_admin_updates(principal.enterprise_id)
        target = await self._enterprise_user(principal, user_id)
        changes = payload.model_dump(exclude_unset=True)
        if target.id == principal.user.id and changes.get("is_active") is False:
            raise AppError(409, "cannot_disable_self", "不能停用当前登录账号")
        if (
            target.id == principal.user.id
            and "role" in changes
            and changes["role"] != "enterprise_admin"
        ):
            raise AppError(409, "cannot_demote_self", "不能降低当前登录账号的管理员角色")
        removes_active_admin = (
            target.role == "enterprise_admin"
            and target.is_active
            and (
                changes.get("is_active") is False
                or ("role" in changes and changes["role"] != "enterprise_admin")
            )
        )
        if removes_active_admin:
            remaining_admins = await self._session.scalar(
                select(func.count())
                .select_from(User)
                .where(
                    User.enterprise_id == principal.enterprise_id,
                    User.role == "enterprise_admin",
                    User.is_active.is_(True),
                    User.id != target.id,
                )
            )
            if not remaining_admins:
                raise AppError(409, "last_admin_required", "企业必须保留至少一名有效管理员")
        for key, value in changes.items():
            setattr(target, key, value)
        if changes.get("is_active") is False:
            now = utc_now()
            for item in (
                await self._session.scalars(
                    select(UserSession).where(
                        UserSession.user_id == target.id,
                        UserSession.revoked_at.is_(None),
                    )
                )
            ).all():
                item.revoked_at = now
        await record_audit(
            self._session,
            request,
            "admin.user_updated",
            actor=principal.user,
            session=principal.session,
            target_type="user",
            target_id=target.id,
            metadata={"fields": sorted(changes)},
        )
        await self._session.commit()
        await self._session.refresh(target)
        return UserOut.model_validate(target)

    async def reset_password(
        self,
        user_id: uuid.UUID,
        payload: TemporaryPasswordRequest,
        principal: Principal,
        request: Request,
    ) -> UserOut:
        settings = self._require_settings()
        validate_new_password(payload.temporary_password, settings)
        target = await self._enterprise_user(principal, user_id)
        credential = await self._session.scalar(
            select(UserCredential).where(UserCredential.user_id == target.id)
        )
        if credential is None:
            credential = UserCredential(user_id=target.id, password_hash="")
            self._session.add(credential)
        credential.password_hash = hash_password(payload.temporary_password)
        credential.password_changed_at = utc_now()
        credential.failed_attempts = 0
        target.password_change_required = True
        target.locked_until = None
        now = utc_now()
        for item in (
            await self._session.scalars(
                select(UserSession).where(
                    UserSession.user_id == target.id,
                    UserSession.revoked_at.is_(None),
                )
            )
        ).all():
            item.revoked_at = now
        await record_audit(
            self._session,
            request,
            "admin.password_reset",
            actor=principal.user,
            session=principal.session,
            target_type="user",
            target_id=target.id,
        )
        await self._session.commit()
        return UserOut.model_validate(target)

    async def replace_data_scopes(
        self,
        user_id: uuid.UUID,
        payload: DataScopeUpdate,
        principal: Principal,
        request: Request,
    ) -> list[OrganizationUnitOut]:
        target = await self._enterprise_user(principal, user_id)
        units = (
            await self._session.scalars(
                select(OrganizationUnit).where(
                    OrganizationUnit.enterprise_id == principal.enterprise_id,
                    OrganizationUnit.id.in_(payload.organization_unit_ids),
                    OrganizationUnit.is_active.is_(True),
                )
            )
        ).all()
        if {item.id for item in units} != set(payload.organization_unit_ids):
            raise AppError(422, "invalid_organization_unit", "一个或多个事业部无效")
        await self._session.execute(
            delete(DataScopeGrant).where(DataScopeGrant.user_id == target.id)
        )
        if payload.enterprise_wide_scope:
            self._session.add(
                DataScopeGrant(
                    user_id=target.id, scope_kind="enterprise", can_read=True
                )
            )
        else:
            for item in units:
                self._session.add(
                    DataScopeGrant(
                        user_id=target.id,
                        scope_kind="organization_unit",
                        organization_unit_id=item.id,
                        can_read=True,
                    )
                )
        await record_audit(
            self._session,
            request,
            "admin.data_scopes_replaced",
            actor=principal.user,
            session=principal.session,
            target_type="user",
            target_id=target.id,
            metadata={
                "enterprise_wide": payload.enterprise_wide_scope,
                "unit_ids": [str(item.id) for item in units],
            },
        )
        await self._session.commit()
        return [OrganizationUnitOut.model_validate(item) for item in units]

    async def revoke_user_sessions(
        self,
        user_id: uuid.UUID,
        principal: Principal,
        request: Request,
    ) -> None:
        target = await self._enterprise_user(principal, user_id)
        now = utc_now()
        sessions = (
            await self._session.scalars(
                select(UserSession).where(
                    UserSession.user_id == target.id,
                    UserSession.revoked_at.is_(None),
                )
            )
        ).all()
        for item in sessions:
            item.revoked_at = now
        await record_audit(
            self._session,
            request,
            "admin.sessions_revoked",
            actor=principal.user,
            session=principal.session,
            target_type="user",
            target_id=target.id,
            metadata={"count": len(sessions)},
        )
        await self._session.commit()

    # ---------------------------------------------------- organization units

    async def list_organization_units(self, principal: Principal) -> Page:
        rows = await organization_unit_repo.list_by_enterprise(
            self._session, principal.enterprise_id
        )
        return Page(items=[OrganizationUnitOut.model_validate(item) for item in rows])

    async def create_organization_unit(
        self,
        payload: OrganizationUnitCreate,
        principal: Principal,
        request: Request,
    ) -> OrganizationUnitOut:
        if payload.parent_id:
            parent = await organization_unit_repo.find_by_id(self._session, payload.parent_id)
            if parent is None or parent.enterprise_id != principal.enterprise_id:
                raise AppError(422, "invalid_parent", "上级组织不存在")
        item = OrganizationUnit(
            enterprise_id=principal.enterprise_id, **payload.model_dump()
        )
        await organization_unit_repo.save(self._session, item)
        await record_audit(
            self._session,
            request,
            "admin.organization_unit_created",
            actor=principal.user,
            session=principal.session,
            target_type="organization_unit",
            target_id=item.id,
            metadata={"code": item.code},
        )
        await self._session.commit()
        return OrganizationUnitOut.model_validate(item)

    async def update_organization_unit(
        self,
        unit_id: uuid.UUID,
        payload: OrganizationUnitUpdate,
        principal: Principal,
        request: Request,
    ) -> OrganizationUnitOut:
        item = await organization_unit_repo.find_by_id(self._session, unit_id)
        if item is None or item.enterprise_id != principal.enterprise_id:
            raise AppError(404, "organization_unit_not_found", "事业部不存在")
        changes = payload.model_dump(exclude_unset=True)
        if changes.get("parent_id") == item.id:
            raise AppError(422, "invalid_parent", "事业部不能成为自己的上级")
        if "parent_id" in changes and changes["parent_id"] is not None:
            parent = await organization_unit_repo.find_by_id(
                self._session, changes["parent_id"]
            )
            if parent is None or parent.enterprise_id != principal.enterprise_id:
                raise AppError(422, "invalid_parent", "上级组织不存在")
            visited = {item.id}
            cursor: OrganizationUnit | None = parent
            while cursor is not None:
                if cursor.id in visited:
                    raise AppError(
                        422, "organization_cycle", "组织层级不能形成循环"
                    )
                visited.add(cursor.id)
                if cursor.parent_id is None:
                    break
                cursor = await organization_unit_repo.find_by_id(
                    self._session, cursor.parent_id
                )
                if cursor is None or cursor.enterprise_id != principal.enterprise_id:
                    raise AppError(
                        422, "invalid_parent", "组织层级包含无效的上级"
                    )
        for key, value in changes.items():
            setattr(item, key, value)
        await record_audit(
            self._session,
            request,
            "admin.organization_unit_updated",
            actor=principal.user,
            session=principal.session,
            target_type="organization_unit",
            target_id=item.id,
            metadata={"fields": sorted(changes)},
        )
        await self._session.commit()
        await self._session.refresh(item)
        return OrganizationUnitOut.model_validate(item)

    # --------------------------------------------------------- audit / runtime

    async def list_audit_events(
        self,
        principal: Principal,
        limit: int,
    ) -> Page:
        statement = select(AuditEvent).where(
            AuditEvent.enterprise_id == principal.enterprise_id
        )
        if principal.user.role == "fde":
            statement = statement.where(
                AuditEvent.action.in_(
                    [
                        "job.started",
                        "job.completed",
                        "job.failed",
                        "system.config_changed",
                        "auth.login",
                        "auth.logout",
                    ]
                )
            )
        rows = (
            await self._session.scalars(
                statement.order_by(AuditEvent.created_at.desc()).limit(limit)
            )
        ).all()
        return Page(items=[AuditEventOut.model_validate(item) for item in rows])

    async def runtime_status(self, principal: Principal) -> RuntimeStatus:
        settings = self._require_settings()
        await self._session.execute(text("SELECT 1"))
        return RuntimeStatus(
            app_env=settings.app_env,
            app_mode=settings.app_mode,
            version=settings.app_version,
            database="ready",
            storage="encrypted-local",
            demo_data_enabled=settings.seed_demo_data,
        )

    async def verify_audit_events(
        self,
        principal: Principal,
        request: Request,
    ) -> AuditVerification:
        # ``verify_audit_chain`` stays synchronous (it walks Connection / Session
        # internals); wrap it in a threadpool so we do not block the event loop.
        verification = await run_in_threadpool(
            verify_audit_chain, self._session, principal.enterprise_id
        )
        # Never mutate a chain that just failed verification. In particular, an
        # absent anchor must remain visible: appending here would create a fresh
        # head and make the next verification incorrectly look healthy. Successful
        # checks are still appended to the verified chain as normal audit events.
        if verification.valid:
            await record_audit(
                self._session,
                request,
                "admin.audit_integrity_verified",
                actor=principal.user,
                session=principal.session,
                target_type="enterprise",
                target_id=principal.enterprise_id,
                outcome="success",
                metadata={
                    "checked_count": verification.checked_count,
                    "invalid_count": 0,
                    "errors": [],
                },
            )
            await self._session.commit()
        return AuditVerification(
            valid=verification.valid,
            checked_count=verification.checked_count,
            invalid_event_ids=verification.invalid_event_ids,
            errors=verification.errors,
        )
