"""``services.integration_key_rotation`` 已迁移到 ``worker.integration_key_rotation``。"""

from __future__ import annotations

import sys

import worker.integration_key_rotation as _mod  # noqa: E402

sys.modules[__name__] = _mod
