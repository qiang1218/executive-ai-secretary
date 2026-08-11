"""邮件账户管理路由。"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from api.deps import EmailAccountServiceDep
from schemas import (
    EmailAccountCreate,
    EmailAccountOut,
    EmailAccountTestOut,
    EmailAccountUpdate,
    EmailSyncEnqueueOut,
)
from services.authz import Principal, get_executive_principal

router = APIRouter(prefix="/email-accounts", tags=["email-accounts"])


@router.get("", response_model=list[EmailAccountOut])
async def list_email_accounts(
    principal: Annotated[Principal, Depends(get_executive_principal)],
    email_account_service: EmailAccountServiceDep,
    include_disabled: bool = False,
) -> list[EmailAccountOut]:
    return await email_account_service.list_accounts(
        principal, include_disabled=include_disabled
    )


@router.post(
    "",
    response_model=EmailAccountOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_email_account(
    payload: EmailAccountCreate,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    email_account_service: EmailAccountServiceDep,
) -> EmailAccountOut:
    return await email_account_service.create_account(payload, principal)


@router.get("/{account_id}", response_model=EmailAccountOut)
async def get_email_account(
    account_id: uuid.UUID,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    email_account_service: EmailAccountServiceDep,
) -> EmailAccountOut:
    return await email_account_service.get_account(principal, account_id)


@router.patch("/{account_id}", response_model=EmailAccountOut)
async def update_email_account(
    account_id: uuid.UUID,
    payload: EmailAccountUpdate,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    email_account_service: EmailAccountServiceDep,
) -> EmailAccountOut:
    return await email_account_service.update_account(account_id, payload, principal)


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_email_account(
    account_id: uuid.UUID,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    email_account_service: EmailAccountServiceDep,
) -> None:
    await email_account_service.delete_account(principal, account_id)


@router.post("/{account_id}/test", response_model=EmailAccountTestOut)
async def test_email_account(
    account_id: uuid.UUID,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    email_account_service: EmailAccountServiceDep,
) -> EmailAccountTestOut:
    return await email_account_service.test_account(principal, account_id)


@router.post("/{account_id}/sync", response_model=EmailSyncEnqueueOut)
async def sync_email_account(
    account_id: uuid.UUID,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    email_account_service: EmailAccountServiceDep,
) -> EmailSyncEnqueueOut:
    return await email_account_service.enqueue_sync(principal, account_id)
