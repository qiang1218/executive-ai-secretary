"""把 schemas/__init__.py 按领域自动拆分（基于 class 名前缀）。

策略：
  1. 用正则提取所有 ``class X`` 块
  2. 按 class 名前缀（Model/Mcp/Harness/User/Enterprise/Login/Session/Org/Project/
     Conversation/Message/File/Memory/Report/Job/Audit/Runtime/Data/Daily/DataSource/
     Feishu/Opportunity/Scheduled/Manual/Clarification/Diagnostic）分组
  3. 写入对应领域文件
  4. ``__init__.py`` 改为 re-export
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"D:\anchnet\executive-ai-secretary\backend\src\schemas")
SRC = ROOT / "__init__.py"
text = SRC.read_text(encoding="utf-8")

# 先删除旧的领域文件
for p in ROOT.glob("*.py"):
    if p.name != "__init__.py":
        p.unlink()

HEADER = '''"""{title}."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from services.data_source_configuration import public_data_source_configuration


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel):
    items: list[Any]
    next_cursor: str | None = None

'''

# 提取所有 class 块
CLASS_RE = re.compile(r"^class (\w+)\b[^\n]*:\n", re.MULTILINE)

classes = []  # list of (name, block)
for m in CLASS_RE.finditer(text):
    name = m.group(1)
    start = m.start()
    rest = text[m.end():]
    nm = CLASS_RE.search(rest)
    if nm:
        end = m.end() + nm.start()
    else:
        end = len(text)
    block = text[start:end].rstrip() + "\n"
    classes.append((name, block))

print(f"Found {len(classes)} classes")

# 按前缀分组
def group_of(name: str) -> str:
    if name in ("ORMModel", "Page"):
        return "common"
    if name.startswith(("Model", "AdminModel", "AuthorizedModel", "DefaultModel")):
        return "model_provider"
    if name.startswith("Mcp"):
        return "mcp"
    if name.startswith("Harness"):
        return "harness"
    if name.startswith(("User", "Executive", "Temporary")):
        return "user"
    if name.startswith("Enterprise"):
        return "enterprise"
    if name.startswith(("Login", "ChangePassword", "Me", "Session")):
        return "auth"
    if name.startswith(("Organization", "DataScope")):
        return "organization"
    if name.startswith("Project"):
        return "project"
    if name.startswith(("Conversation", "Message", "OrganizationScope")):
        return "conversation"
    if name.startswith("File"):
        return "file"
    if name.startswith("Memory"):
        return "memory"
    if name.startswith("Report"):
        return "report"
    if name.startswith("Job"):
        return "job"
    if name.startswith("Audit"):
        return "audit"
    if name.startswith("Runtime"):
        return "runtime"
    if name.startswith(("DataDomain", "DataCapabilities", "DailyBrief", "DataOperations")):
        return "data"
    if name.startswith(("DataSource", "DataSync", "Feishu", "Experience", "Opportunity", "Scheduled", "Manual")):
        return "data_source"
    if name.startswith(("Clarification", "MessageEvidence", "Diagnostic")):
        return "conversation"
    return "misc"

groups: dict[str, list[tuple[str, str]]] = {}
for name, block in classes:
    g = group_of(name)
    groups.setdefault(g, []).append((name, block))

# 写 common.py（只有 header）
(ROOT / "common.py").write_text(HEADER.format(title="通用 schema (ORMModel / Page)"), encoding="utf-8")
print("  wrote common.py (header only)")

# 写其他领域文件
TITLES = {
    "model_provider": "模型供应商与授权 schema",
    "mcp": "MCP 工具 schema",
    "harness": "Harness 配置与仿真 schema",
    "user": "用户、偏好与高管画像 schema",
    "enterprise": "企业 schema",
    "auth": "认证 schema",
    "organization": "组织单元 schema",
    "project": "项目 schema",
    "conversation": "会话、消息、澄清与诊断 schema",
    "file": "文件 schema",
    "memory": "长期记忆 schema",
    "report": "报告 schema",
    "job": "异步任务 schema",
    "audit": "审计 schema",
    "runtime": "运行时状态 schema",
    "data": "数据域与每日简报 schema",
    "data_source": "数据源、同步与调度 schema",
    "misc": "其他 schema",
}

all_names = []
for g, items in sorted(groups.items()):
    if g == "common":
        continue
    body = HEADER.format(title=TITLES.get(g, g))
    for name, block in items:
        body += "\n\n" + block
    (ROOT / f"{g}.py").write_text(body, encoding="utf-8")
    print(f"  wrote {g}.py ({len(items)} classes)")
    for name, _ in items:
        all_names.append(name)

# 重写 __init__.py
init_lines = ['"""Pydantic schema 聚合包。', "", "按领域拆分为多个子模块；本 ``__init__`` 把全部符号 re-export 出来。", '"""', "", "from __future__ import annotations", ""]
for g in sorted(groups.keys() | {"common"}):
    init_lines.append(f"from .{g} import *  # noqa: F401,F403")
init_lines.append("")
init_lines.append("__all__ = [")
for n in all_names:
    init_lines.append(f'    "{n}",')
init_lines.append("]")
SRC.write_text("\n".join(init_lines), encoding="utf-8")
print(f"\n  rewrote __init__.py ({len(all_names)} names)")
print("\nDone.")
