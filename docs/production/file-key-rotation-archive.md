# 文件加密密钥轮换（CLI 实现归档）

> **状态**：CLI 入口已删除（曾位于 `backend/src/api/rotate_file_keys.py`）。本文档为归档记录，仅供将来重建时参考。
>
> 核心实现在 `backend/src/core/file/key_rotation.py`，由 `core.file.key_rotation.rotate_file_keys()` 提供。
> 运维 runbook 见 `docs/production/key-rotation.md`。

## CLI 原接口

| 参数 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `--from-version` | ✅ | — | 源密钥版本 |
| `--to-version` | ✅ | — | 目标密钥版本（必须等于 `FILE_ENCRYPTION_KEY_VERSION`） |
| `--backup-dir` | 非 dry-run | — | 备份证据目录 |
| `--backup-public-key` | 非 dry-run | — | Ed25519 备份签名公钥 |
| `--max-backup-age-hours` | ❌ | 24 | 备份时效上限 |
| `--batch-size` | ❌ | 25 | 每批重写文件数 |
| `--max-files` | ❌ | 不限 | 总量上限（分批维护） |
| `--dry-run` | ❌ | false | 预检：仅解密核对，不写文件/数据库 |
| `--verify-only` | ❌ | false | 验证：仅校验目标版本可解密 |
| `--confirm` | 非 dry-run | — | 安全确认串 `ROTATE FILE KEYS <from> TO <to>` |

## 安全约束

1. `--to-version` 必须等于 `FILE_ENCRYPTION_KEY_VERSION`
2. `--from-version` 和 `--to-version` 必须在 `FILE_ENCRYPTION_KEY_RING` 中
3. 非 dry-run 必须：
   - 传 `--confirm "ROTATE FILE KEYS <from> TO <to>"`
   - 传 `--backup-dir` 和 `--backup-public-key`
   - 备份必须 < `--max-backup-age-hours` 时效
   - 备份 Ed25519 签名必须通过
   - 备份环境必须等于 `APP_ENV`
4. PG advisory lock 拒绝并行轮换
5. 每个文件：解密旧 → 写新 → fsync → 原子替换 → 复验 → 更新 DB → 写审计 → 单文件提交

## 命令模板（已废弃，保留备查）

```bash
# 预检
python -m api.rotate_file_keys --from-version v1 --to-version v2 --dry-run

# 执行
python -m api.rotate_file_keys \
    --from-version v1 --to-version v2 \
    --backup-dir /backup \
    --backup-public-key /run/rotation/backup-signing-public-key \
    --batch-size 25 \
    --confirm 'ROTATE FILE KEYS v1 TO v2'

# 验证
python -m api.rotate_file_keys --from-version v1 --to-version v2 --verify-only
```

## 等价 Python 调用（当前可用）

```python
from datetime import timedelta
from core.file.backup_evidence import verify_backup_evidence
from core.file.key_rotation import rotate_file_keys, verify_file_key_version
from core.file.storage import LocalEncryptedStorage
from configs.settings import get_settings
from core.db import SessionLocal

settings = get_settings()
keys = settings.file_encryption_keys()
storage = LocalEncryptedStorage(
    settings.file_storage_root,
    current_key_version=settings.file_encryption_key_version,
    key_ring=keys,
)

# 预检：验证备份证据
evidence = verify_backup_evidence(
    backup_dir,
    backup_public_key,
    expected_environment=settings.app_env,
    max_age=timedelta(hours=24),
)

# 轮换
with SessionLocal() as db:
    summary = rotate_file_keys(
        db, storage,
        source_key_version="v1",
        target_key_version="v2",
        backup_reference=evidence.reference,
        batch_size=25,
    )

# 验证
with SessionLocal() as db:
    verified = verify_file_key_version(db, storage, key_version="v2")
```

## 何时重新启用 CLI

如需恢复 CLI 入口：

1. 重新创建 `backend/src/api/rotate_file_keys.py`
2. 复用上面的 argparse + 校验逻辑
3. 在 `docs/production/key-rotation.md` 中恢复 `python -m api.rotate_file_keys ...` 命令模板

不重建 CLI 也无影响：所有功能都通过 `core.file.key_rotation` 提供，pytest 用例已覆盖核心路径。
