"""``services.mcp_app`` 已迁移到 ``worker.mcp_app``。"""

from __future__ import annotations

import sys

import worker.mcp_app as _mod  # noqa: E402

sys.modules[__name__] = _mod
