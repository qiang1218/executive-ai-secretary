"""服务层：业务逻辑入口。

每个领域模块对应一个 Service 概念，例如：
    * ``ingestion`` → :class:`IngestionService`（数据接入）
    * ``authz`` → :class:`AuthzService`（CSRF / Principal 解析）
    * ``daily_brief`` → :class:`DailyBriefService`（每日简报生成）

通过 ``__getattr__``（PEP 562）兜底，使 ``from services import Y`` 能找到
具体符号（类、函数、常量）。

本 ``__init__`` **不主动 import 子模块**，仅在通过 ``services.<X>`` 显式访问
时懒加载。子模块若存在则直接返回；若在 ``services/`` 下找不到，再回退查找
``worker/`` / ``utils/`` 子包以兼容历史包布局（``cli``、``job_state`` 等）。
"""

from __future__ import annotations

import importlib
from typing import Any

# 物理位置在 worker 或 utils 中的子模块（保留为兼容 shim）
_REMOTE_SUBMODULE_NAMES = (
    "file_key_rotation",
    # ``cli`` / ``job_state`` 物理在 ``utils`` 包
    "cli",
    "job_state",
)

# 本地包内子模块（按字典序以便审计）
_LOCAL_SUBMODULE_NAMES = (
    "admin_service",
    "anspire",
    "answer_contract",
    "auth_service",
    "authz",
    "authorized_model_service",
    "backup_evidence",
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
    "integration_key_rotation",
    "job_management_service",
    "mcp_schema_service",
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
)


def __getattr__(name: str) -> Any:
    """PEP 562：按需懒加载子模块或子模块中的符号。

    查找顺序：
        services → worker / utils（仅限 ``_REMOTE_SUBMODULE_NAMES`` 白名单）
    """
    if name in _LOCAL_SUBMODULE_NAMES or name in _REMOTE_SUBMODULE_NAMES:
        try:
            return importlib.import_module(f"services.{name}")
        except ImportError:
            for pkg in ("worker", "utils"):
                try:
                    return importlib.import_module(f"{pkg}.{name}")
                except ImportError:
                    continue
            raise AttributeError(f"module 'services' has no attribute {name!r}")

    # 在子模块中查找符号
    for sub_name in (*_LOCAL_SUBMODULE_NAMES, *_REMOTE_SUBMODULE_NAMES):
        for pkg in ("services", "worker", "utils"):
            try:
                sub = importlib.import_module(f"{pkg}.{sub_name}")
            except ImportError:
                continue
            if hasattr(sub, name):
                return getattr(sub, name)
    raise AttributeError(f"module 'services' has no attribute {name!r}")


__all__ = [*_LOCAL_SUBMODULE_NAMES, *_REMOTE_SUBMODULE_NAMES]  # noqa: PIE801
