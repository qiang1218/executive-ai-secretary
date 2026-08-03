"""``services.mcp_registry`` 已迁移到 ``worker.mcp_registry``。"""

from __future__ import annotations

import sys

import worker.mcp_registry as _mod  # noqa: E402

sys.modules[__name__] = _mod
