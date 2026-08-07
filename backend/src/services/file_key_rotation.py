"""``file_key_rotation`` 在新架构下物理位置是 ``worker_old.file_key_rotation``。

``repositories.rotate_file_keys`` 与 ``tests`` 都通过 ``services.<name>`` 访问——
之前这个 shim 指向 ``worker.file_key_rotation``（不存在），是预先存在的 broken
reference; 现在改为真实 alias。
"""
from __future__ import annotations

import worker_old.file_key_rotation as _impl  # noqa: E402

# Surface a stable, explicitly-curated list rather than relying on the
# implementation module's ``__all__`` (which is empty today).
__all__ = [
    "ROTATION_ADVISORY_LOCK",
    "RotationSummary",
    "rotate_file_keys",
    "verify_file_key_version",
]

for _name in __all__:
    globals()[_name] = getattr(_impl, _name)
