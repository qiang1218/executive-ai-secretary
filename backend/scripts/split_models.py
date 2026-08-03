"""把 models/__init__.py 按领域拆分为多个文件。

策略：
  1. 把每个 class 的源代码片段抽到对应领域文件
  2. 各领域文件用 ``from db.session import Base`` 等基础导入
  3. ``models/__init__.py`` 改为从各领域文件 re-export 全部符号
  4. 保持向后兼容：``from models import User`` 等仍工作
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"D:\anchnet\executive-ai-secretary\backend\src\models")
SRC = ROOT / "__init__.py"
text = SRC.read_text(encoding="utf-8")

# 共享的 import 头部（每个领域文件都会用）
HEADER = '''"""{title}."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from db.session import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
'''

# 领域 → 该领域的 class 名列表
DOMAINS = {
    "audit": {
        "title": "审计链与事件模型",
        "classes": ["AuditChainHead", "AuditEvent", "IdempotencyRecord"],
        "extra": '''
@event.listens_for(AuditEvent, "before_insert")
def sign_audit_event(_mapper, connection, target: "AuditEvent") -> None:
    # Imported lazily to keep the model module free of settings initialization cycles.
    from repositories.audit_integrity import prepare_audit_event

    prepare_audit_event(connection, target)
''',
    },
    "enterprise": {
        "title": "企业与组织单元模型",
        "classes": ["Enterprise", "OrganizationUnit", "DataScopeGrant"],
    },
    "user": {
        "title": "用户与凭证模型",
        "classes": ["User", "UserCredential", "UserSession", "ExecutivePersonalProfile"],
    },
    "project": {
        "title": "项目模型",
        "classes": ["Project"],
    },
    "conversation": {
        "title": "会话、消息、Harness 运行模型",
        "classes": [
            "Conversation", "ConversationOrganizationScope", "ProjectConversation",
            "Message", "MessageRun", "MessageRoute", "HarnessStageRun",
            "HarnessDiagnosticGrant", "Clarification", "MessageEvidence",
        ],
    },
    "file": {
        "title": "文件资产与抽取模型",
        "classes": ["FileAsset", "ConversationFile", "FileEvent", "FileExtraction", "FileChunk"],
    },
    "memory": {
        "title": "长期记忆模型",
        "classes": ["Memory", "MemoryEvent"],
    },
    "report": {
        "title": "报告与版本模型",
        "classes": ["Report", "ReportVersion"],
    },
    "job": {
        "title": "异步任务模型",
        "classes": ["Job", "JobAttempt"],
    },
    "config": {
        "title": "配置、模型授权、MCP 工具与 Harness 版本模型",
        "classes": [
            "AppConfig", "SecretReference", "ModelProviderConfig",
            "EnterpriseModelAuthorization", "McpToolConfig", "McpToolDefinition",
            "HarnessConfigVersion", "OpportunityExperienceWeightPolicy",
        ],
    },
    "data_source": {
        "title": "数据源、调度、同步与领域状态模型",
        "classes": [
            "DataSource", "ScheduledTask", "ScheduleRun", "DataSyncRun",
            "DataDomainStatus", "SourceCheckpoint",
        ],
    },
    "data_warehouse": {
        "title": "数仓维度表与事实表模型",
        "classes": [
            "DimPerson", "DimCustomer", "FactOpportunity",
            "FactOpportunityParticipant", "FactOpportunityProduct",
            "FactDelivery", "FactFinanceCollection", "FactTarget", "DailySnapshot",
        ],
    },
}


def extract_class_block(name: str) -> str:
    """从源文件中抽出 ``class <name>(...): ...`` 整段代码（到下一个顶格 ``class`` 或文件末尾）。"""
    # 匹配 class 定义开始
    pattern = rf"^(class {re.escape(name)}\b[^\n]*:\n)"
    m = re.search(pattern, text, re.MULTILINE)
    if not m:
        raise ValueError(f"class {name} not found")
    start = m.start()
    # 找下一个顶格 ``class `` 或 ``@`` 或文件末尾
    rest = text[m.end():]
    next_pattern = re.compile(r"^(class \w|@event\.)", re.MULTILINE)
    nm = next_pattern.search(rest)
    if nm:
        end = m.end() + nm.start()
    else:
        end = len(text)
    return text[start:end].rstrip() + "\n"


# 写各领域文件
for fname, info in DOMAINS.items():
    body = HEADER.format(title=info["title"])
    for cls in info["classes"]:
        body += "\n\n" + extract_class_block(cls)
    if "extra" in info:
        body += "\n\n" + info["extra"].strip() + "\n"
    (ROOT / f"{fname}.py").write_text(body, encoding="utf-8")
    print(f"  wrote {fname}.py ({len(info['classes'])} classes)")

# 重写 __init__.py 为 re-export
init_lines = ['"""ORM 模型聚合包。', "", "按领域拆分为多个子模块；本 ``__init__`` 把全部符号 re-export 出来，", "保持 ``from models import User`` 的向后兼容。", '"""', "", "from __future__ import annotations", ""]
for fname in DOMAINS:
    init_lines.append(f"from .{fname} import *  # noqa: F401,F403")
init_lines.append("")
init_lines.append("# 显式列出主要符号，便于 IDE 自动补全")
all_names = []
for info in DOMAINS.values():
    all_names.extend(info["classes"])
init_lines.append("__all__ = [")
for n in all_names:
    init_lines.append(f'    "{n}",')
init_lines.append("]")
SRC.write_text("\n".join(init_lines), encoding="utf-8")
print(f"\n  rewrote __init__.py ({len(all_names)} names in __all__)")

print("\nDone. Run tests to verify.")
