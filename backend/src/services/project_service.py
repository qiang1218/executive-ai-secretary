"""Project service.

Follows the anspire service pattern: a class that receives the database
session in the constructor and exposes business methods. The ``/projects``
router instantiates ``ProjectService(db)`` and delegates all DB / business
logic here.
"""

from __future__ import annotations

import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.pagination import decode_cursor, encode_cursor
from core.security import utc_now
from exceptions.errors import AppError
from models import Conversation, Project, ProjectConversation
from repositories import project as project_repo
from repositories.audit import record_audit
from schemas import Page, ProjectCreate, ProjectOut, ProjectUpdate
from services.authz import Principal, assert_org_scope
from services.idempotency import replay, save_response


class ProjectService:
    """Service for project CRUD, archive, and pin lifecycle.

    Mirrors the anspire ``Service`` convention: stateless business logic
    layered on top of a SQLAlchemy ``AsyncSession``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------ utils

    async def _owned_project(self, principal: Principal, project_id: uuid.UUID) -> Project:
        # Admin/FDE privacy rule: project content remains owner-only unless explicitly delegated later.
        item = await project_repo.find_owned(self._session, principal, project_id)
        if item is None:
            raise AppError(404, "project_not_found", "项目不存在")
        await assert_org_scope(self._session, principal, item.organization_unit_id)
        return item

    # ---------------------------------------------------------------- queries

    async def list_projects(
        self,
        principal: Principal,
        *,
        cursor: str | None = None,
        limit: int = 50,
        include_archived: bool = False,
    ) -> Page:
        cursor_id = decode_cursor(cursor)
        rows = await project_repo.list_by_owner(
            self._session,
            principal,
            cursor_id=cursor_id,
            limit=limit,
            include_archived=include_archived,
        )
        next_cursor = encode_cursor(rows[limit - 1].id) if len(rows) > limit else None
        rows = rows[:limit]
        visible = []
        for item in rows:
            try:
                await assert_org_scope(self._session, principal, item.organization_unit_id)
            except AppError:
                continue
            visible.append(ProjectOut.model_validate(item))
        return Page(items=visible, next_cursor=next_cursor)

    # --------------------------------------------------------------- mutations

    async def create_project(
        self,
        payload: ProjectCreate,
        request: Request,
        principal: Principal,
    ):
        previous = await replay(self._session, request, principal, payload)
        if previous:
            return JSONResponse(status_code=previous[0], content=previous[1])
        await assert_org_scope(self._session, principal, payload.organization_unit_id)
        item = Project(
            enterprise_id=principal.enterprise_id,
            owner_user_id=principal.user.id,
            organization_unit_id=payload.organization_unit_id,
            name=payload.name,
            description=payload.description,
        )
        await project_repo.save(self._session, item)
        output = ProjectOut.model_validate(item)
        await record_audit(
            self._session,
            request,
            "project.created",
            actor=principal.user,
            session=principal.session,
            target_type="project",
            target_id=item.id,
        )
        await save_response(self._session, request, principal, payload, 201, output)
        await self._session.commit()
        return output

    async def get_project(self, principal: Principal, project_id: uuid.UUID) -> ProjectOut:
        return ProjectOut.model_validate(await self._owned_project(principal, project_id))

    async def update_project(
        self,
        project_id: uuid.UUID,
        payload: ProjectUpdate,
        request: Request,
        principal: Principal,
    ) -> ProjectOut:
        item = await self._owned_project(principal, project_id)
        changes = payload.model_dump(exclude_unset=True)
        if "organization_unit_id" in changes:
            await assert_org_scope(self._session, principal, changes["organization_unit_id"])
        for key, value in changes.items():
            setattr(item, key, value)
        await record_audit(
            self._session,
            request,
            "project.updated",
            actor=principal.user,
            session=principal.session,
            target_type="project",
            target_id=item.id,
            metadata={"fields": sorted(changes)},
        )
        await self._session.commit()
        await self._session.refresh(item)
        return ProjectOut.model_validate(item)

    async def archive_project(
        self,
        project_id: uuid.UUID,
        request: Request,
        principal: Principal,
    ) -> None:
        item = await self._owned_project(principal, project_id)
        item.archived_at = utc_now()
        detached_conversation_ids: list[str] = []
        result = await self._session.execute(
            select(ProjectConversation)
            .join(Conversation, Conversation.id == ProjectConversation.conversation_id)
            .where(
                ProjectConversation.project_id == item.id,
                Conversation.archived_at.is_(None),
            )
        )
        memberships = result.scalars().all()
        for membership in memberships:
            detached_conversation_ids.append(str(membership.conversation_id))
            await self._session.delete(membership)
        await record_audit(
            self._session,
            request,
            "project.archived",
            actor=principal.user,
            session=principal.session,
            target_type="project",
            target_id=item.id,
            metadata={"detached_conversation_ids": detached_conversation_ids},
        )
        await self._session.commit()

    async def pin_project(
        self,
        project_id: uuid.UUID,
        request: Request,
        principal: Principal,
    ) -> ProjectOut:
        item = await self._owned_project(principal, project_id)
        item.pinned_at = utc_now()
        await record_audit(
            self._session,
            request,
            "project.pinned",
            actor=principal.user,
            session=principal.session,
            target_type="project",
            target_id=item.id,
        )
        await self._session.commit()
        await self._session.refresh(item)
        return ProjectOut.model_validate(item)

    async def unpin_project(
        self,
        project_id: uuid.UUID,
        request: Request,
        principal: Principal,
    ) -> ProjectOut:
        item = await self._owned_project(principal, project_id)
        item.pinned_at = None
        await record_audit(
            self._session,
            request,
            "project.unpinned",
            actor=principal.user,
            session=principal.session,
            target_type="project",
            target_id=item.id,
        )
        await self._session.commit()
        await self._session.refresh(item)
        return ProjectOut.model_validate(item)
