"""把 models/<domain>.py 的重复头部替换为 ``from .base import *``。

每个领域文件原本都有 30+ 行的 sqlalchemy import 与 mixin 定义；
统一改为 ``from .base import *``，只保留该领域独有的 import（如
``sqlalchemy.dialects.postgresql.JSONB`` 这种特殊用法其实也已经在 base 里了）。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"D:\anchnet\executive-ai-secretary\backend\src\models")

# 旧的公共头部模式：从 ``from __future__ import annotations`` 到
# ``class UUIDMixin: ...`` 结束（含紧随其后的空行）
HEADER_RE = re.compile(
    r'^"""[^"]*"""\n\n'                     # 模块 docstring
    r'from __future__ import annotations\n\n'
    r'import uuid\n'
    r'from datetime import date, datetime\n'
    r'from typing import Any\n\n'
    r'from pgvector\.sqlalchemy import Vector\n'
    r'from sqlalchemy import \(\n'
    r'(?:    \w+,\n)+'
    r'\)\n'
    r'from sqlalchemy\.dialects\.postgresql import JSONB\n'
    r'from sqlalchemy\.orm import Mapped, mapped_column, relationship\n'
    r'from sqlalchemy\.types import JSON\n\n'
    r'from db\.session import Base\n\n'
    r'JSONType = JSON\(\)\.with_variant\(JSONB\(\), "postgresql"\)\n\n\n'
    r'def new_uuid\(\) -> uuid\.UUID:\n'
    r'    return uuid\.uuid4\(\)\n\n\n'
    r'class TimestampMixin:\n'
    r'    created_at: Mapped\[datetime\] = mapped_column\(\n'
    r'        DateTime\(timezone=True\), server_default=func\.now\(\), nullable=False\n'
    r'    \)\n'
    r'    updated_at: Mapped\[datetime\] = mapped_column\(\n'
    r'        DateTime\(timezone=True\),\n'
    r'        server_default=func\.now\(\),\n'
    r'        onupdate=func\.now\(\),\n'
    r'        nullable=False,\n'
    r'    \)\n\n\n'
    r'class UUIDMixin:\n'
    r'    id: Mapped\[uuid\.UUID\] = mapped_column\(Uuid, primary_key=True, default=new_uuid\)\n\n',
    re.MULTILINE,
)

REPLACEMENT = '''"""{docstring}"""

from __future__ import annotations

from .base import *  # noqa: F401,F403  Base / JSONType / new_uuid / mixins / sqlalchemy symbols

'''

fixed = 0
for p in sorted(ROOT.glob("*.py")):
    if p.name in ("__init__.py", "base.py"):
        continue
    text = p.read_text(encoding="utf-8")
    # 提取原 docstring
    dm = re.match(r'^("""[^"]*?""")', text, re.DOTALL)
    if not dm:
        print(f"  skip (no docstring): {p.name}")
        continue
    docstring = dm.group(1)
    new_text = HEADER_RE.sub(REPLACEMENT.format(docstring=docstring), text, count=1)
    if new_text != text:
        p.write_text(new_text, encoding="utf-8")
        fixed += 1
        print(f"  fixed: {p.name}")
    else:
        print(f"  skip (pattern not matched): {p.name}")

print(f"\nTotal: {fixed} files fixed")
