"""merge_skills_and_legacy_mcp_drop

Revision ID: 27e9d8d36948
Revises: b8f4c8a2d5e7, d1f4a9b3c7e2
Create Date: 2026-08-10 15:36:28.761513
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '27e9d8d36948'
down_revision: Union[str, None] = ('b8f4c8a2d5e7', 'd1f4a9b3c7e2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
