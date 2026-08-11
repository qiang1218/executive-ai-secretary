"""邮件账户管理服务。

负责邮件账户的 CRUD、密码加解密、测试连接、手动触发同步入队。
IMAP 拉取的实际逻辑在 :mod:`services.email_sync_service`。

同时为每个账户自动维护一条 ``ScheduledTask(task_type="email.sync")``，
cron 表达式取自 ``Settings.email_sync_cron``（默认每天 08:00）。
账户删除/停用时一并停用对应 ScheduledTask。
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import Settings
from exceptions.errors import AppError
from models import EmailAccount, Job, new_uuid
from models.data_source import ScheduledTask
from repositories import email as email_repo
from services.authz import Principal
from services.email_credential import (
    EmailCredentialError,
    decrypt_email_password,
    encrypt_email_password,
)
from schemas import (
    EmailAccountCreate,
    EmailAccountOut,
    EmailAccountTestOut,
    EmailAccountUpdate,
    EmailSyncEnqueueOut,
)
from core.security import utc_now


async def _upsert_sync_task(
    session: AsyncSession,
    account: EmailAccount,
    settings: Settings,
) -> None:
    """为账户创建或更新 email.sync ScheduledTask。"""
    task_key = f"email_sync:{account.id}"
    task = await session.scalar(
        select(ScheduledTask).where(
            ScheduledTask.enterprise_id == account.enterprise_id,
            ScheduledTask.key == task_key,
        )
    )
    cron_expr = settings.email_sync_cron
    now = utc_now()
    if task is None:
        task = ScheduledTask(
            id=new_uuid(),
            enterprise_id=account.enterprise_id,
            data_source_id=None,
            key=task_key,
            task_type="email.sync",
            cron_expression=cron_expr,
            timezone=settings.daily_digest_timezone,
            is_enabled=account.is_enabled,
            next_run_at=now,
            configuration_json={"email_account_id": str(account.id)},
        )
        session.add(task)
    else:
        task.cron_expression = cron_expr
        task.timezone = settings.daily_digest_timezone
        task.is_enabled = account.is_enabled
        task.configuration_json = {"email_account_id": str(account.id)}
        if task.next_run_at is None:
            task.next_run_at = now


async def _upsert_digest_task(
    session: AsyncSession,
    account: EmailAccount,
    settings: Settings,
) -> None:
    """为用户创建或更新 daily_digest ScheduledTask。

    每个用户只维护一条 ``task_type="daily_digest"`` 任务，cron 取自
    ``settings.daily_digest_cron``。多个邮箱账户共享同一条 digest 任务，
    摘要会聚合该用户全部 ``is_notified=False`` 的邮件。
    """
    task_key = f"daily_digest:{account.user_id}"
    task = await session.scalar(
        select(ScheduledTask).where(
            ScheduledTask.enterprise_id == account.enterprise_id,
            ScheduledTask.key == task_key,
        )
    )
    now = utc_now()
    # 默认从下一个整点 cron 周期开始，避免账户刚建就立刻触发
    next_run_at = now
    if task is None:
        task = ScheduledTask(
            id=new_uuid(),
            enterprise_id=account.enterprise_id,
            data_source_id=None,
            key=task_key,
            task_type="daily_digest",
            cron_expression=settings.daily_digest_cron,
            timezone=settings.daily_digest_timezone,
            is_enabled=account.is_enabled,
            next_run_at=next_run_at,
            configuration_json={"user_id": str(account.user_id)},
        )
        session.add(task)
    else:
        task.cron_expression = settings.daily_digest_cron
        task.timezone = settings.daily_digest_timezone
        task.is_enabled = account.is_enabled
        task.configuration_json = {"user_id": str(account.user_id)}
        if task.next_run_at is None:
            task.next_run_at = next_run_at


async def _remove_digest_task_if_unused(
    session: AsyncSession,
    account: EmailAccount,
) -> None:
    """删除账户后清理 daily_digest 任务：用户已无任何邮箱账户时才删。"""
    remaining = await session.scalar(
        select(EmailAccount.id)
        .where(
            EmailAccount.user_id == account.user_id,
            EmailAccount.id != account.id,
        )
        .limit(1)
    )
    if remaining is not None:
        return
    task = await session.scalar(
        select(ScheduledTask).where(
            ScheduledTask.enterprise_id == account.enterprise_id,
            ScheduledTask.key == f"daily_digest:{account.user_id}",
        )
    )
    if task is not None:
        await session.delete(task)


class EmailAccountService:
    """邮件账户管理。

    Mirrors the anspire ``Service`` convention: stateless business logic
    layered on top of a SQLAlchemy ``AsyncSession``.
    """

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    # ------------------------------------------------------------------ utils

    def _account_out(self, item: EmailAccount) -> EmailAccountOut:
        return EmailAccountOut(
            id=str(item.id),
            address=item.address,
            display_name=item.display_name,
            protocol=item.protocol,
            server_host=item.server_host,
            server_port=item.server_port,
            use_tls=item.use_tls,
            is_enabled=item.is_enabled,
            last_synced_at=item.last_synced_at,
            last_uid=item.last_uid,
            last_error_code=item.last_error_code,
            last_error_message=item.last_error_message,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    async def _owned_account(
        self, principal: Principal, account_id: uuid.UUID
    ) -> EmailAccount:
        item = await email_repo.find_account_owned(
            self._session, principal.user.id, account_id
        )
        if item is None:
            raise AppError(404, "email_account_not_found", "邮件账户不存在")
        return item

    def _decrypt_password(self, account: EmailAccount) -> str:
        try:
            return decrypt_email_password(
                ciphertext=account.password_ciphertext,
                nonce=account.password_nonce,
                enterprise_id=account.enterprise_id,
                key_version=account.encryption_key_version,
                settings=self._settings,
            )
        except EmailCredentialError as exc:
            raise AppError(500, exc.code, str(exc)) from exc

    # ---------------------------------------------------------------- queries

    async def list_accounts(
        self, principal: Principal, *, include_disabled: bool = False
    ) -> list[EmailAccountOut]:
        rows = await email_repo.list_accounts(
            self._session, principal.user.id, include_disabled=include_disabled
        )
        return [self._account_out(item) for item in rows]

    async def get_account(
        self, principal: Principal, account_id: uuid.UUID
    ) -> EmailAccountOut:
        item = await self._owned_account(principal, account_id)
        return self._account_out(item)

    # --------------------------------------------------------------- mutations

    async def create_account(
        self, payload: EmailAccountCreate, principal: Principal
    ) -> EmailAccountOut:
        # 唯一性校验（user_id + address）
        existing = await self._session.scalar(
            select(EmailAccount).where(
                EmailAccount.user_id == principal.user.id,
                EmailAccount.address == payload.address,
            )
        )
        if existing is not None:
            raise AppError(
                409, "email_account_duplicate", "该邮箱地址已存在"
            )
        encrypted = encrypt_email_password(
            payload.password.get_secret_value(),
            enterprise_id=principal.enterprise_id,
            settings=self._settings,
        )
        item = EmailAccount(
            id=new_uuid(),
            user_id=principal.user.id,
            enterprise_id=principal.enterprise_id,
            address=payload.address,
            display_name=payload.display_name,
            protocol=payload.protocol,
            server_host=payload.server_host,
            server_port=payload.server_port,
            use_tls=payload.use_tls,
            password_ciphertext=encrypted.ciphertext,
            password_nonce=encrypted.nonce,
            password_hint=encrypted.hint,
            encryption_key_version=encrypted.key_version,
            is_enabled=payload.is_enabled,
        )
        self._session.add(item)
        await self._session.flush()
        await _upsert_sync_task(self._session, item, self._settings)
        await _upsert_digest_task(self._session, item, self._settings)
        await self._session.commit()
        await self._session.refresh(item)
        return self._account_out(item)

    async def update_account(
        self,
        account_id: uuid.UUID,
        payload: EmailAccountUpdate,
        principal: Principal,
    ) -> EmailAccountOut:
        item = await self._owned_account(principal, account_id)
        if payload.display_name is not None:
            item.display_name = payload.display_name
        if payload.protocol is not None:
            item.protocol = payload.protocol
        if payload.server_host is not None:
            item.server_host = payload.server_host
        if payload.server_port is not None:
            item.server_port = payload.server_port
        if payload.use_tls is not None:
            item.use_tls = payload.use_tls
        if payload.is_enabled is not None:
            item.is_enabled = payload.is_enabled
        if payload.password is not None and payload.password.get_secret_value():
            encrypted = encrypt_email_password(
                payload.password.get_secret_value(),
                enterprise_id=item.enterprise_id,
                settings=self._settings,
            )
            item.password_ciphertext = encrypted.ciphertext
            item.password_nonce = encrypted.nonce
            item.password_hint = encrypted.hint
            item.encryption_key_version = encrypted.key_version
        await _upsert_sync_task(self._session, item, self._settings)
        await _upsert_digest_task(self._session, item, self._settings)
        await self._session.commit()
        await self._session.refresh(item)
        return self._account_out(item)

    async def delete_account(
        self, principal: Principal, account_id: uuid.UUID
    ) -> None:
        item = await self._owned_account(principal, account_id)
        # 同步停用 ScheduledTask（data_source_id 为 NULL，删账户不会级联）
        task = await self._session.scalar(
            select(ScheduledTask).where(
                ScheduledTask.enterprise_id == principal.enterprise_id,
                ScheduledTask.key == f"email_sync:{item.id}",
            )
        )
        if task is not None:
            await self._session.delete(task)
        await _remove_digest_task_if_unused(self._session, item)
        await self._session.delete(item)
        await self._session.commit()

    # ------------------------------------------------------------------ test

    async def test_account(
        self, principal: Principal, account_id: uuid.UUID
    ) -> EmailAccountTestOut:
        item = await self._owned_account(principal, account_id)
        password = self._decrypt_password(item)
        from services.email_sync_service import test_imap_connection

        ok, code, message = await test_imap_connection(
            host=item.server_host,
            port=item.server_port,
            use_tls=item.use_tls,
            address=item.address,
            password=password,
        )
        return EmailAccountTestOut(ok=ok, error_code=code, error_message=message)

    # ------------------------------------------------------------------- sync

    async def enqueue_sync(
        self, principal: Principal, account_id: uuid.UUID
    ) -> EmailSyncEnqueueOut:
        """手动触发邮件同步 job。"""
        item = await self._owned_account(principal, account_id)
        if not item.is_enabled:
            raise AppError(409, "email_account_disabled", "邮件账户已停用")
        job = Job(
            enterprise_id=principal.enterprise_id,
            created_by_user_id=principal.user.id,
            job_type="email.sync",
            status="queued",
            max_attempts=self._settings.worker_job_max_attempts,
            payload_json={
                "email_account_id": str(item.id),
                "user_id": str(principal.user.id),
                "trigger_type": "manual",
            },
            scope_snapshot_json={
                "enterprise_id": str(principal.enterprise_id),
            },
            scheduled_at=utc_now(),
        )
        self._session.add(job)
        await self._session.commit()
        await self._session.refresh(job)
        return EmailSyncEnqueueOut(job_id=str(job.id), status=job.status)
