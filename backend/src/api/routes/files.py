from __future__ import annotations

import uuid
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import Response

from api.deps import FileServiceDep
from services.authz import Principal, get_executive_principal
from configs.settings import Settings, get_settings
from schemas import FileExtractionOut, FileOut, Page
from services.storage import LocalEncryptedStorage

router = APIRouter(prefix="/files", tags=["files"])


@lru_cache
def storage_for(
    root: str,
    current_key_version: str,
    key_ring: tuple[tuple[str, bytes], ...],
) -> LocalEncryptedStorage:
    return LocalEncryptedStorage(
        Path(root),
        current_key_version=current_key_version,
        key_ring=dict(key_ring),
    )


def get_storage(settings: Annotated[Settings, Depends(get_settings)]) -> LocalEncryptedStorage:
    keys = settings.file_encryption_keys()
    return storage_for(
        str(settings.file_storage_root),
        settings.file_encryption_key_version,
        tuple(sorted(keys.items())),
    )


@router.get("", response_model=Page)
async def list_files(
    principal: Annotated[Principal, Depends(get_executive_principal)],
    file_service: FileServiceDep,
) -> Page:
    return Page(items=await file_service.list_files(principal))


@router.post("", response_model=FileOut, status_code=status.HTTP_410_GONE)
async def upload_file(
    request: Request,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    file_service: FileServiceDep,
) -> FileOut:
    await file_service.reject_upload(principal, request)


@router.get("/{file_id}/extraction", response_model=FileExtractionOut)
async def get_file_extraction(
    file_id: uuid.UUID,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    file_service: FileServiceDep,
) -> FileExtractionOut:
    return await file_service.get_file_extraction(principal, file_id)


@router.get("/{file_id}", response_model=FileOut)
async def get_file(
    file_id: uuid.UUID,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    file_service: FileServiceDep,
) -> FileOut:
    return await file_service.get_file(principal, file_id)


@router.get("/{file_id}/content")
async def download_file(
    file_id: uuid.UUID,
    request: Request,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    storage: Annotated[LocalEncryptedStorage, Depends(get_storage)],
    file_service: FileServiceDep,
) -> Response:
    item, content = await file_service.download_file(principal, file_id, storage, request)
    encoded = quote(item.original_name)
    return Response(
        content=content,
        media_type=item.media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: uuid.UUID,
    request: Request,
    principal: Annotated[Principal, Depends(get_executive_principal)],
    storage: Annotated[LocalEncryptedStorage, Depends(get_storage)],
    file_service: FileServiceDep,
):
    await file_service.delete_file(principal, file_id, storage, request)
