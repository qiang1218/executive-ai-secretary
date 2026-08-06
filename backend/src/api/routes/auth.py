from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from api.deps import AuthServiceDep
from configs.settings import Settings

from services.authz import (
    Principal,
    get_authenticated_principal,
    get_current_principal,
    get_executive_principal,
)
from schemas import (
    ChangePasswordRequest,
    ExecutivePersonalProfileOut,
    ExecutivePersonalProfileUpdate,
    LoginRequest,
    LoginResponse,
    MeResponse,
    OrganizationUnitOut,
    SessionOut,
    UserOut,
    UserPreferenceUpdate,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def set_auth_cookies(
    response: Response,
    settings: Settings,
    session_token: str,
    csrf_token: str,
) -> None:
    max_age = settings.session_ttl_seconds
    response.set_cookie(
        settings.session_cookie_name,
        session_token,
        max_age=max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    for name in (settings.session_cookie_name, settings.csrf_cookie_name):
        response.delete_cookie(
            name,
            httponly=name == settings.session_cookie_name,
            secure=settings.session_cookie_secure,
            samesite=settings.session_cookie_samesite,
            path="/",
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    auth_service: AuthServiceDep,
) -> LoginResponse:
    ctx = await auth_service.login(payload, request)
    set_auth_cookies(response, auth_service.settings, ctx.session_token, ctx.csrf_token)
    return LoginResponse(
        user=UserOut.model_validate(ctx.user),
        csrf_token=ctx.csrf_token,
        expires_at=ctx.expires_at,
        app_env=auth_service.settings.app_env,
        app_mode=auth_service.settings.app_mode,
    )


@router.get("/me", response_model=MeResponse)
async def me(
    request: Request,
    response: Response,
    principal: Annotated[Principal, Depends(get_authenticated_principal)],
    auth_service: AuthServiceDep,
) -> MeResponse:
    ctx = await auth_service.me(request, principal)
    if ctx.csrf_refreshed:
        response.set_cookie(
            auth_service.settings.csrf_cookie_name,
            ctx.csrf_token,
            max_age=auth_service.settings.session_ttl_seconds,
            httponly=False,
            secure=auth_service.settings.session_cookie_secure,
            samesite=auth_service.settings.session_cookie_samesite,
            path="/",
        )
    return MeResponse(
        user=UserOut.model_validate(ctx.user),
        enterprise=ctx.enterprise,
        scopes=[OrganizationUnitOut.model_validate(item) for item in ctx.scopes],
        csrf_token=ctx.csrf_token,
        app_env=auth_service.settings.app_env,
        app_mode=auth_service.settings.app_mode,
    )


@router.patch("/preferences", response_model=UserOut)
async def update_preferences(
    payload: UserPreferenceUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(get_current_principal)],
    auth_service: AuthServiceDep,
) -> UserOut:
    return await auth_service.update_preferences(payload, request, principal)


@router.get("/personal-profile", response_model=ExecutivePersonalProfileOut)
async def get_personal_profile(
    principal: Annotated[Principal, Depends(get_executive_principal)],
    auth_service: AuthServiceDep,
) -> ExecutivePersonalProfileOut:
    return await auth_service.get_personal_profile(principal)


@router.put("/personal-profile", response_model=ExecutivePersonalProfileOut)
async def update_personal_profile(
    payload: ExecutivePersonalProfileUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    auth_service: AuthServiceDep,
) -> ExecutivePersonalProfileOut:
    return await auth_service.update_personal_profile(payload, request, principal)


@router.post("/change-password", response_model=LoginResponse)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    principal: Annotated[Principal, Depends(get_authenticated_principal)],
    auth_service: AuthServiceDep,
) -> LoginResponse:
    ctx = await auth_service.change_password(payload, request, principal)
    response.set_cookie(
        auth_service.settings.csrf_cookie_name,
        ctx.csrf_token,
        max_age=auth_service.settings.session_ttl_seconds,
        httponly=False,
        secure=auth_service.settings.session_cookie_secure,
        samesite=auth_service.settings.session_cookie_samesite,
        path="/",
    )
    return LoginResponse(
        user=UserOut.model_validate(ctx.user),
        csrf_token=ctx.csrf_token,
        expires_at=ctx.expires_at,
        app_env=auth_service.settings.app_env,
        app_mode=auth_service.settings.app_mode,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    principal: Annotated[Principal, Depends(get_authenticated_principal)],
    auth_service: AuthServiceDep,
):
    await auth_service.logout(request, principal)
    clear_auth_cookies(response, auth_service.settings)


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    principal: Annotated[Principal, Depends(get_current_principal)],
    auth_service: AuthServiceDep,
) -> list[SessionOut]:
    return await auth_service.list_sessions(principal)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: uuid.UUID,
    request: Request,
    response: Response,
    principal: Annotated[Principal, Depends(get_current_principal)],
    auth_service: AuthServiceDep,
):
    result = await auth_service.revoke_session(session_id, request, principal)
    if result.cleared:
        clear_auth_cookies(response, auth_service.settings)
