"""服务层：业务逻辑入口。

每个领域模块对应一个 Service 概念，例如：
    * ``ingestion`` → :class:`IngestionService`（数据接入）
    * ``business_tools`` → :class:`BusinessToolsService`（执行业务工具）
    * ``authz`` → :class:`AuthzService`（CSRF / Principal 解析）
    * ``daily_brief`` → :class:`DailyBriefService`（每日简报生成）

通过 ``__getattr__``（PEP 562）兜底，使 ``from services import Y`` 能找到
具体符号（类、函数、常量）。为避免与 ``worker`` / ``repositories`` 等包
形成循环导入，本 ``__init__`` **不主动 import 子模块**，仅在通过
``services.<X>`` 显式访问时懒加载。
"""

from __future__ import annotations

import importlib
from typing import Any

_SUBMODULE_NAMES = (
    "admin_service",
    "anspire",
    "answer_contract",
    "auth_service",
    "authz",
    "authorized_model_service",
    "backup_evidence",
    "business_tools",
    "capabilities",
    "conversation_scope",
    "conversation_service",
    "daily_brief",
    "data_capability_service",
    "data_freshness",
    "data_source_configuration",
    "data_source_service",
    "demo_dataset",
    "demo_source",
    "feishu",
    "feishu_live",
    "file_service",
    "harness_admin_service",
    "harness_config",
    "health_service",
    "idempotency",
    "ingestion",
    "job_management_service",
    "mcp_tool_service",
    "memory_service",
    "metric_policy",
    "model_admin_service",
    "model_authorization",
    "operating_data_v3",
    "organization_service",
    "personal_data",
    "project_service",
    "query_spec",
    "report_service",
    "source_contract",
    "source_contract_v3",
    "storage",
    # 下列模块物理在 ``worker`` 包，但仍可通过 ``services.<name>`` 访问
    "file_key_rotation",
    "hermes_client",
    "integration_key_rotation",
    "mcp_app",
    "mcp_registry",
    # ``cli`` / ``job_state`` 物理在 ``utils`` 包
    "cli",
    "job_state",
)


def __getattr__(name: str) -> Any:
    """PEP 562：按需懒加载子模块或子模块中的符号。"""
    if name in _SUBMODULE_NAMES:
        # 优先 services 本地，再 fallback 到 worker / utils
        for pkg in ("services", "worker", "utils"):
            try:
                return importlib.import_module(f"{pkg}.{name}")
            except ImportError:
                continue
        raise AttributeError(f"module 'services' has no attribute {name!r}")

    # 在子模块中查找符号
    for sub_name in _SUBMODULE_NAMES:
        for pkg in ("services", "worker", "utils"):
            try:
                sub = importlib.import_module(f"{pkg}.{sub_name}")
            except ImportError:
                continue
            if hasattr(sub, name):
                return getattr(sub, name)
    raise AttributeError(f"module 'services' has no attribute {name!r}")


__all__ = list(_SUBMODULE_NAMES)
