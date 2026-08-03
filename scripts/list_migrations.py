"""列出 backend alembic/versions/ 下所有迁移文件及其 revision/down_revision。

支持 new 风格 ("Revision ID:") 和 backend 风格 (revision: str = "...")
"""
import re
from pathlib import Path

d = Path('backend/alembic/versions')
migrations = []
for f in sorted(d.glob('*.py')):
    text = f.read_text(encoding='utf-8')
    rev_m = re.search(r'Revision ID:\s*([a-f0-9]+)', text)
    if not rev_m:
        rev_m = re.search(r'revision:\s*[\'"]?([a-f0-9]+)', text)
    down_m = re.search(r'Revises:\s*([a-f0-9]+)', text)
    if not down_m:
        down_m = re.search(
            r"down_revision:\s*(?:Union\[str,\s*None\],\s*)?=\s*['\"]?([a-f0-9]+)?",
            text,
        )
    rev = rev_m.group(1) if rev_m else '?'
    down = down_m.group(1) if down_m and down_m.group(1) else 'ROOT'
    migrations.append((rev, down, f.name))

for rev, down, name in sorted(migrations):
    print(f'  {rev} <- {down}  {name}')