"""认证主体对象，跨层共享的身份载体。"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from models import User, UserSession


@dataclass
class Principal:
    user: User
    session: UserSession

    @property
    def enterprise_id(self) -> uuid.UUID:
        return self.user.enterprise_id


__all__ = ["Principal"]
