"""修复 models 领域文件的 docstring（去掉多余引号）。"""

import re
from pathlib import Path

ROOT = Path(r"D:\anchnet\executive-ai-secretary\backend\src\models")

# 匹配 ``"""""..."""""`` 这种多余引号的形式
# 原本是 ``"""text"""``，被错误包成 ``"""""text"""``
PATTERN = re.compile(r'^""""+([^"]*?)""""+', re.MULTILINE)

fixed = 0
for p in sorted(ROOT.glob("*.py")):
    if p.name in ("__init__.py", "base.py"):
        continue
    text = p.read_text(encoding="utf-8")
    new = PATTERN.sub(lambda m: '"""' + m.group(1) + '"""', text, count=1)
    if new != text:
        p.write_text(new, encoding="utf-8")
        fixed += 1
        print(f"  fixed: {p.name}")

print(f"\nTotal: {fixed} files fixed")
