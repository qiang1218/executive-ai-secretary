"""Job state service.

Follows the anspire service pattern: a class that receives the database
session in the constructor and exposes business methods. The ``/jobs`` router
instantiates ``JobStateService(db)`` and calls ``close_assistant_placeholder``.

A module-level ``close_assistant_placeholder`` function is kept as a thin
facade for backward compatibility with any code that still calls it directly.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from models import Job, Message

ASSISTANT_NOT_CONFIGURED_CONTENT = "未配置真实处理器"


class JobStateService:
    """Service for transitioning job state and closing placeholder messages.

    Mirrors the anspire ``Service`` convention: stateless business logic
    layered on top of a SQLAlchemy ``AsyncSession``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def close_assistant_placeholder(
        self,
        job: Job,
        *,
        status: str,
        content: str | None = None,
    ) -> Message | None:
        """Close a persisted assistant placeholder without inventing an answer."""
        raw_id = (job.payload_json or {}).get("assistant_message_id")
        try:
            message_id = uuid.UUID(str(raw_id))
        except (TypeError, ValueError):
            return None
        message = await self._session.get(Message, message_id)
        if message is None or message.role != "assistant":
            return None
        message.status = status
        if content is not None:
            message.content = content
        return message


# Backward-compatible facade: ``close_assistant_placeholder(db, job, ...)``.
# New code should prefer ``JobStateService(db).close_assistant_placeholder(job, ...)``.
async def close_assistant_placeholder(
    db: AsyncSession,
    job: Job,
    *,
    status: str,
    content: str | None = None,
) -> Message | None:
    """Module-level facade around :class:`JobStateService`."""
    return await JobStateService(db).close_assistant_placeholder(job, status=status, content=content)
