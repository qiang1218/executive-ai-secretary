"""FastAPI 依赖注入层。

将 ``db.session.get_db``、``services.authz.get_current_principal``
等作为 :class:`typing.Annotated` 别名导出，便于 router 层以 ``db: SessionDep``
风格注入数据库会话与当前主体。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from services.authz import (
    Principal,
    get_current_principal,
    get_executive_principal,
)
from configs.settings import Settings, get_settings
from db.session import get_db

SessionDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]
ExecutivePrincipalDep = Annotated[Principal, Depends(get_executive_principal)]

__all__ = [
    "SessionDep",
    "SettingsDep",
    "PrincipalDep",
    "ExecutivePrincipalDep",
    "Principal",
    "get_current_principal",
    "get_executive_principal",
    "get_db",
    "get_settings",
    "Settings",
]
