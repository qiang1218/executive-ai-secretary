"""``services.hermes_client`` 已迁移到 ``worker.hermes_client``。"""

from __future__ import annotations

import sys

import worker.hermes_client as _mod  # noqa: E402

sys.modules[__name__] = _mod
