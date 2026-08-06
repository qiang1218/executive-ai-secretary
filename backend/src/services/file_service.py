"""File service.

Follows the anspire service pattern: a class that receives the database
session in the constructor and exposes business methods. The ``/files`` router
delegates DB access and business logic to :class:`FileService`, keeping the
route layer focused on parameter validation, dependency injection and response
shaping.

``LocalEncryptedStorage`` is intentionally left as a route-level dependency
(``get_storage``); the service methods that need it accept ``storage`` as a
parameter so that the storage lifecycle stays tied to the request.
"""

from __future__ import annotations

import uuid

from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import utc_now
from exceptions.errors import AppError
from models import (
    FileAsset,
    FileChunk,
    FileEvent,
    FileExtraction,
)
from repositories import file_asset as file_asset_repo
from repositories.audit import record_audit
from schemas import FileExtractionOut, FileOut
from services.authz import Principal
from services.storage import LocalEncryptedStorage
from starlette.concurrency import run_in_threadpool


class FileService:
    """Service for file lifecycle operations.

    Mirrors the anspire ``Service`` convention: stateless business logic
    layered on top of a SQLAlchemy ``AsyncSession``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Ownership / lookup helpers
    # ------------------------------------------------------------------
    async def owned_file(self, principal: Principal, file_id: uuid.UUID) -> FileAsset:
        """Return the file owned by ``principal`` or raise 404.

        Admin/FDE principals cannot use their role to read an executive's
        files; the query is scoped to ``uploaded_by_user_id``.
        """
        item = await file_asset_repo.find_owned(self._session, principal, file_id)
        if item is None:
            raise AppError(404, "file_not_found", "文件不存在")
        return item

    # ------------------------------------------------------------------
    # Listing / detail
    # ------------------------------------------------------------------
    async def list_files(self, principal: Principal) -> list[FileOut]:
        """List up to 100 most recent non-deleted files for the principal."""
        rows = await file_asset_repo.list_by_owner(self._session, principal)
        return [FileOut.model_validate(item) for item in rows]

    async def get_file(self, principal: Principal, file_id: uuid.UUID) -> FileOut:
        """Return the serialized file for ``file_id``."""
        return FileOut.model_validate(await self.owned_file(principal, file_id))

    async def get_file_extraction(
        self, principal: Principal, file_id: uuid.UUID
    ) -> FileExtractionOut:
        """Return the extraction record for ``file_id`` if available."""
        await self.owned_file(principal, file_id)
        extraction = await self._session.scalar(
            select(FileExtraction).where(FileExtraction.file_id == file_id)
        )
        if extraction is None:
            raise AppError(
                404,
                "file_extraction_unavailable",
                "该文件类型不支持内容解析",
            )
        return FileExtractionOut.model_validate(extraction)

    # ------------------------------------------------------------------
    # Content download
    # ------------------------------------------------------------------
    async def download_file(
        self,
        principal: Principal,
        file_id: uuid.UUID,
        storage: LocalEncryptedStorage,
        request: Request,
    ) -> tuple[FileAsset, bytes]:
        """Read the decrypted file content, audit the download and record a FileEvent.

        Returns the ``FileAsset`` and the decrypted ``bytes`` so the route can
        shape the HTTP response (Content-Disposition, media type, ...).
        """
        item = await self.owned_file(principal, file_id)
        content = await run_in_threadpool(
            storage.open_decrypted, item.storage_key, item.encryption_key_version
        )
        if len(content) != item.size_bytes:
            raise AppError(500, "file_integrity_error", "文件大小校验失败")
        self._session.add(
            FileEvent(file_id=item.id, actor_user_id=principal.user.id, event_type="downloaded")
        )
        await record_audit(
            self._session,
            request,
            "file.downloaded",
            actor=principal.user,
            session=principal.session,
            target_type="file",
            target_id=item.id,
            metadata={"size_bytes": item.size_bytes, "media_type": item.media_type},
        )
        await self._session.commit()
        return item, content

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------
    async def delete_file(
        self,
        principal: Principal,
        file_id: uuid.UUID,
        storage: LocalEncryptedStorage,
        request: Request,
    ) -> None:
        """Soft-delete a file: tombstone + cascade-derived rows + storage.delete.

        The encrypted file asset is kept as an auditable tombstone, but every
        derived representation (FileChunk, FileExtraction) is removed.
        Deleting the extraction cascades to pgvector and keyword chunks
        through the database foreign keys.
        """
        item = await self.owned_file(principal, file_id)
        item.deleted_at = utc_now()
        item.status = "deleted"
        await self._session.execute(delete(FileChunk).where(FileChunk.file_id == item.id))
        await self._session.execute(delete(FileExtraction).where(FileExtraction.file_id == item.id))
        self._session.add(
            FileEvent(file_id=item.id, actor_user_id=principal.user.id, event_type="deleted")
        )
        await record_audit(
            self._session,
            request,
            "file.deleted",
            actor=principal.user,
            session=principal.session,
            target_type="file",
            target_id=item.id,
        )
        await self._session.commit()
        await run_in_threadpool(storage.delete, item.storage_key)

    # ------------------------------------------------------------------
    # Upload (disabled / 410 stub)
    # ------------------------------------------------------------------
    async def reject_upload(self, principal: Principal, request: Request) -> None:
        """Audit a rejected upload attempt and raise the 410 ``file_upload_disabled`` error."""
        await record_audit(
            self._session,
            request,
            "file.upload_rejected",
            actor=principal.user,
            session=principal.session,
            target_type="file",
            outcome="failure",
            failure_reason_code="file_upload_disabled",
        )
        await self._session.commit()
        raise AppError(
            410,
            "file_upload_disabled",
            "当前阶段已关闭文件上传，请直接使用智能问数与泛化问答",
        )
