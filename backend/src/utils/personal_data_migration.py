"""一次性运维脚本：迁移历史未加密的 Memory 行。"""
from __future__ import annotations

from sqlalchemy import select

from configs.settings import get_settings
from db.session import SessionLocal
from core.personal_data import set_memory_content
from models import Memory


def migrate_plaintext_memories() -> int:
    settings = get_settings()
    migrated = 0
    with SessionLocal.begin() as db:
        rows = db.scalars(
            select(Memory).where(
                Memory.content != "",
                Memory.content_ciphertext == "",
            )
        ).all()
        for row in rows:
            set_memory_content(row, row.content, settings)
            migrated += 1
    return migrated


def main() -> None:
    migrated = migrate_plaintext_memories()
    print(f"Encrypted {migrated} legacy memory rows.")


if __name__ == "__main__":
    main()
