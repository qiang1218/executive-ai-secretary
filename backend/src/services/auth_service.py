"""Auth service.

Follows the anspire service pattern: a class that receives the database
session (and ``Settings``) in the constructor and exposes business methods.
The ``/auth`` router instantiates ``AuthService(db, settings)`` and delegates
all DB / business logic here, keeping the route layer focused on parameter
validation, cookie operations and response shaping.

Cookie helpers (``set_auth_cookies`` / ``clear_auth_cookies``) remain in the
route file because they operate directly on the HTTP ``Response`` object.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from configs.settings import Settings
from core.security import (
    as_utc,
    hash_password,
    new_session_tokens,
    password_needs_rehash,
    rate_limiter,
    session_expirations,
    token_hash,
    utc_now,
    validate_new_password,
    verify_password,
)
from exceptions.errors import AppError
from models import (
    Enterprise,
    ExecutivePersonalProfile,
    OrganizationUnit,
    User,
    UserCredential,
    UserSession,
    new_uuid,
)
from repositories.audit import client_ip, record_audit
from schemas import (
    ChangePasswordRequest,
    ExecutivePersonalProfileOut,
    ExecutivePersonalProfileUpdate,
    LoginRequest,
    SessionOut,
    UserOut,
    UserPreferenceUpdate,
)
from services.authz import (
    Principal,
    accessible_organization_unit_ids,
)
from services.personal_data import decrypt_profile_payload, encrypt_profile_payload


@dataclass
class LoginContext:
    """Tokens + user returned by :meth:`AuthService.login`.

    The route layer is responsible for writing the session / CSRF cookies onto
    the ``Response`` and assembling the final ``LoginResponse``.
    """

    user: User
    session_token: str
    csrf_token: str
    expires_at: object


@dataclass
class MeContext:
    """Data returned by :meth:`AuthService.me`.

    The route layer is responsible for writing the CSRF cookie (when refreshed)
    onto the ``Response`` and assembling the final ``MeResponse``.
    """

    user: User
    enterprise: Enterprise
    scopes: list[OrganizationUnit]
    csrf_token: str
    csrf_refreshed: bool


@dataclass
class ChangePasswordContext:
    """Tokens + user returned by :meth:`AuthService.change_password`.

    The route layer is responsible for writing the CSRF cookie onto the
    ``Response`` and assembling the final ``LoginResponse``.
    """

    user: User
    csrf_token: str
    expires_at: object


@dataclass
class RevokeSessionResult:
    """Result of :meth:`AuthService.revoke_session`.

    ``cleared`` indicates whether the current session was the one revoked (so
    the route layer should clear auth cookies).
    """

    cleared: bool


class AuthService:
    """Service for authentication, sessions and personal profile.

    Mirrors the anspire ``Service`` convention: stateless business logic
    layered on top of a SQLAlchemy ``AsyncSession``.
    """

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    @property
    def settings(self) -> Settings:
        """Expose settings for route-layer cookie operations."""
        return self._settings

    # ------------------------------------------------------------------ utils

    def _default_personal_profile(self, user: User) -> dict[str, object]:
        return {
            "salutation": user.preferred_name or user.display_name or "董事长",
            "amount_unit": "wan",
            "response_style": "balanced",
            "locale": user.locale if user.locale in {"zh-CN", "zh-TW", "en-US"} else "zh-CN",
            "memory_enabled": user.memory_enabled,
        }

    def _personal_profile_out(
        self,
        row: ExecutivePersonalProfile | None,
        user: User,
    ) -> ExecutivePersonalProfileOut:
        payload = (
            decrypt_profile_payload(row, self._settings)
            if row
            else self._default_personal_profile(user)
        )
        return ExecutivePersonalProfileOut(
            **payload,
            version=row.version if row else 0,
            updated_at=row.updated_at if row else None,
        )

    # --------------------------------------------------------------- mutations

    async def login(self, payload: LoginRequest, request: Request) -> LoginContext:
        """Authenticate the user and create a new session.

        Returns a :class:`LoginContext` holding the user and tokens; the route
        layer writes cookies and assembles the ``LoginResponse``.
        """
        ip = client_ip(request) or "unknown"
        allowed, retry_after = rate_limiter.check(
            f"login:{ip}:{payload.email}",
            self._settings.login_max_attempts,
            self._settings.login_window_seconds,
        )
        if not allowed:
            raise AppError(
                429, "rate_limited", "登录尝试过于频繁，请稍后重试", {"retry_after": retry_after}
            )

        matches = (
            await self._session.scalars(
                select(User)
                .options(selectinload(User.credential))
                .where(User.email == payload.email)
                .limit(2)
            )
        ).all()
        user = matches[0] if len(matches) == 1 else None
        valid = bool(
            user
            and user.credential
            and verify_password(user.credential.password_hash, payload.password)
        )
        now = utc_now()
        if not valid or not user:
            if user and user.credential:
                user.credential.failed_attempts += 1
                if user.credential.failed_attempts >= self._settings.login_max_attempts:
                    user.locked_until = now + timedelta(
                        seconds=self._settings.login_window_seconds
                    )
                await record_audit(
                    self._session,
                    request,
                    "auth.login_failed",
                    actor=user,
                    target_type="user",
                    target_id=user.id,
                    outcome="failure",
                )
                await self._session.commit()
            raise AppError(401, "invalid_credentials", "邮箱或密码不正确")
        if not user.is_active:
            raise AppError(403, "user_disabled", "账号已停用")
        if user.locked_until and as_utc(user.locked_until) > now:
            raise AppError(423, "user_locked", "账号暂时锁定，请稍后重试")

        credential = user.credential
        assert credential is not None
        if password_needs_rehash(credential.password_hash):
            credential.password_hash = hash_password(payload.password)
        credential.failed_attempts = 0
        user.locked_until = None
        user.last_login_at = now
        tokens = new_session_tokens()
        expires_at, idle_expires_at = session_expirations(self._settings)
        session = UserSession(
            user_id=user.id,
            token_hash=token_hash(
                tokens.session_token, self._settings.session_secret.get_secret_value()
            ),
            csrf_hash=token_hash(tokens.csrf_token, self._settings.csrf_secret.get_secret_value()),
            expires_at=expires_at,
            idle_expires_at=idle_expires_at,
            last_seen_at=now,
            ip_address=ip,
            user_agent=request.headers.get("user-agent", "")[:500] or None,
        )
        self._session.add(session)
        await self._session.flush()
        await record_audit(
            self._session,
            request,
            "auth.login",
            actor=user,
            session=session,
            target_type="session",
            target_id=session.id,
        )
        await self._session.commit()
        return LoginContext(
            user=user,
            session_token=tokens.session_token,
            csrf_token=tokens.csrf_token,
            expires_at=expires_at,
        )

    async def me(self, request: Request, principal: Principal) -> MeContext:
        """Assemble the current user's profile, scope and CSRF state.

        Returns a :class:`MeContext`; the route layer writes the CSRF cookie
        (when refreshed) and assembles the ``MeResponse``.
        """
        enterprise = await self._session.get(Enterprise, principal.enterprise_id)
        if enterprise is None or not enterprise.is_active:
            raise AppError(403, "enterprise_disabled", "企业账号不可用")
        ids = await accessible_organization_unit_ids(self._session, principal)
        scopes = (
            await self._session.scalars(
                select(OrganizationUnit)
                .where(OrganizationUnit.id.in_(ids), OrganizationUnit.is_active.is_(True))
                .order_by(OrganizationUnit.sort_order, OrganizationUnit.name)
            )
        ).all()
        csrf_token = request.cookies.get(self._settings.csrf_cookie_name)
        if (
            not csrf_token
            or token_hash(csrf_token, self._settings.csrf_secret.get_secret_value())
            != principal.session.csrf_hash
        ):
            csrf_token = new_session_tokens().csrf_token
            principal.session.csrf_hash = token_hash(
                csrf_token, self._settings.csrf_secret.get_secret_value()
            )
            await self._session.commit()
            return MeContext(
                user=principal.user,
                enterprise=enterprise,
                scopes=list(scopes),
                csrf_token=csrf_token,
                csrf_refreshed=True,
            )
        return MeContext(
            user=principal.user,
            enterprise=enterprise,
            scopes=list(scopes),
            csrf_token=csrf_token,
            csrf_refreshed=False,
        )

    async def update_preferences(
        self,
        payload: UserPreferenceUpdate,
        request: Request,
        principal: Principal,
    ) -> UserOut:
        principal.user.memory_enabled = payload.memory_enabled
        await record_audit(
            self._session,
            request,
            "auth.preferences_updated",
            actor=principal.user,
            session=principal.session,
            target_type="user",
            target_id=principal.user.id,
            metadata={"memory_enabled": payload.memory_enabled},
        )
        await self._session.commit()
        await self._session.refresh(principal.user)
        return UserOut.model_validate(principal.user)

    async def get_personal_profile(self, principal: Principal) -> ExecutivePersonalProfileOut:
        row = await self._session.scalar(
            select(ExecutivePersonalProfile).where(
                ExecutivePersonalProfile.user_id == principal.user.id,
                ExecutivePersonalProfile.enterprise_id == principal.enterprise_id,
            )
        )
        return self._personal_profile_out(row, principal.user)

    async def update_personal_profile(
        self,
        payload: ExecutivePersonalProfileUpdate,
        request: Request,
        principal: Principal,
    ) -> ExecutivePersonalProfileOut:
        row = await self._session.scalar(
            select(ExecutivePersonalProfile)
            .where(
                ExecutivePersonalProfile.user_id == principal.user.id,
                ExecutivePersonalProfile.enterprise_id == principal.enterprise_id,
            )
            .with_for_update()
        )
        if row is None:
            row = ExecutivePersonalProfile(
                id=new_uuid(),
                enterprise_id=principal.enterprise_id,
                user_id=principal.user.id,
                profile_ciphertext="",
                profile_nonce="",
                encryption_key_version=self._settings.integration_encryption_key_version,
                version=1,
            )
            self._session.add(row)
        else:
            row.version += 1
        values = payload.model_dump()
        encrypt_profile_payload(values, profile=row, settings=self._settings)
        principal.user.memory_enabled = payload.memory_enabled
        principal.user.locale = payload.locale
        await record_audit(
            self._session,
            request,
            "auth.personal_profile_updated",
            actor=principal.user,
            session=principal.session,
            target_type="executive_personal_profile",
            target_id=row.id,
            metadata={
                "version": row.version,
                "locale": payload.locale,
                "memory_enabled": payload.memory_enabled,
            },
        )
        await self._session.commit()
        await self._session.refresh(row)
        return self._personal_profile_out(row, principal.user)

    async def change_password(
        self,
        payload: ChangePasswordRequest,
        request: Request,
        principal: Principal,
    ) -> ChangePasswordContext:
        """Change the user's password and rotate the CSRF token.

        Returns a :class:`ChangePasswordContext`; the route layer writes the
        CSRF cookie and assembles the ``LoginResponse``.
        """
        credential = await self._session.scalar(
            select(UserCredential).where(UserCredential.user_id == principal.user.id)
        )
        if credential is None or not verify_password(
            credential.password_hash, payload.current_password
        ):
            await record_audit(
                self._session,
                request,
                "auth.password_change_failed",
                actor=principal.user,
                session=principal.session,
                target_type="user",
                target_id=principal.user.id,
                outcome="failure",
            )
            await self._session.commit()
            raise AppError(400, "current_password_incorrect", "当前密码不正确")
        if verify_password(credential.password_hash, payload.new_password):
            raise AppError(422, "password_reused", "新密码不能与当前密码相同")
        validate_new_password(payload.new_password, self._settings)
        now = utc_now()
        credential.password_hash = hash_password(payload.new_password)
        credential.password_changed_at = now
        credential.failed_attempts = 0
        principal.user.password_change_required = False
        # End every other browser session after a credential change.
        other_sessions = (
            await self._session.scalars(
                select(UserSession).where(
                    UserSession.user_id == principal.user.id,
                    UserSession.id != principal.session.id,
                    UserSession.revoked_at.is_(None),
                )
            )
        ).all()
        for item in other_sessions:
            item.revoked_at = now
        csrf_token = new_session_tokens().csrf_token
        principal.session.csrf_hash = token_hash(
            csrf_token, self._settings.csrf_secret.get_secret_value()
        )
        await record_audit(
            self._session,
            request,
            "auth.password_changed",
            actor=principal.user,
            session=principal.session,
            target_type="user",
            target_id=principal.user.id,
            metadata={"other_sessions_revoked": len(other_sessions)},
        )
        await self._session.commit()
        return ChangePasswordContext(
            user=principal.user,
            csrf_token=csrf_token,
            expires_at=principal.session.expires_at,
        )

    async def logout(self, request: Request, principal: Principal) -> None:
        principal.session.revoked_at = utc_now()
        await record_audit(
            self._session,
            request,
            "auth.logout",
            actor=principal.user,
            session=principal.session,
            target_type="session",
            target_id=principal.session.id,
        )
        await self._session.commit()

    async def list_sessions(self, principal: Principal) -> list[SessionOut]:
        sessions = (
            await self._session.scalars(
                select(UserSession)
                .where(UserSession.user_id == principal.user.id, UserSession.revoked_at.is_(None))
                .order_by(UserSession.last_seen_at.desc())
            )
        ).all()
        return [
            SessionOut.model_validate(item).model_copy(
                update={"is_current": item.id == principal.session.id}
            )
            for item in sessions
        ]

    async def revoke_session(
        self,
        session_id: uuid.UUID,
        request: Request,
        principal: Principal,
    ) -> RevokeSessionResult:
        target = await self._session.scalar(
            select(UserSession).where(
                UserSession.id == session_id,
                UserSession.user_id == principal.user.id,
                UserSession.revoked_at.is_(None),
            )
        )
        if target is None:
            raise AppError(404, "session_not_found", "登录会话不存在")
        target.revoked_at = utc_now()
        await record_audit(
            self._session,
            request,
            "auth.session_revoked",
            actor=principal.user,
            session=principal.session,
            target_type="session",
            target_id=target.id,
        )
        await self._session.commit()
        return RevokeSessionResult(cleared=target.id == principal.session.id)
