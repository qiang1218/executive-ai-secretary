"""把 new/services/worker/src/executive_ai_worker/ 平移到 backend/src/worker/，
并把所有 from executive_ai_api.X 改为目标包路径。"""

import pathlib
import re
import shutil

SRC = pathlib.Path(r"D:\anchnet\executive-ai-secretary\new\services\worker\src\executive_ai_worker")
DST = pathlib.Path(r"D:\anchnet\executive-ai-secretary\backend\src\worker")

# 模块映射 (executive_ai_api.X -> 目标包)
MODULE_MAP = {
    "config": "configs.settings",
    "database": "db.session",
    "logging_config": "logs.config",
    "security": "core.security",
    "models": "models",
    "anspire": "services.anspire",
    "answer_contract": "services.answer_contract",
    "authz": "services.authz",
    "capabilities": "services.capabilities",
    "harness_config": "services.harness_config",
    "hermes_client": "worker.hermes_client",
    "mcp_registry": "worker.mcp_registry",
    "personal_data": "services.personal_data",
    "query_spec": "services.query_spec",
    "storage": "services.storage",
    "ingestion": "services.ingestion",
    "job_state": "services.job_state",
}

FILES = ["assistant_orchestrator.py", "file_extraction.py", "scheduler.py", "embedding_cache.py"]


def rewrite_imports(content: str) -> str:
    """把 from executive_ai_api.X import Y 改为 from <target> import Y"""
    for old, new in MODULE_MAP.items():
        # from executive_ai_api.X import Y
        pattern = rf"from executive_ai_api\.{re.escape(old)} import"
        replacement = f"from {new} import"
        content = re.sub(pattern, replacement, content)
        # import executive_ai_api.X as Y  (罕见, 但也处理)
        pattern2 = rf"import executive_ai_api\.{re.escape(old)} as"
        replacement2 = f"import {new} as"
        content = re.sub(pattern2, replacement2, content)
    return content


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    for fname in FILES:
        src_path = SRC / fname
        dst_path = DST / fname
        if not src_path.exists():
            print(f"  SKIP: {src_path} not found")
            continue
        content = src_path.read_text(encoding="utf-8")
        new_content = rewrite_imports(content)
        dst_path.write_text(new_content, encoding="utf-8")
        print(f"  COPIED: {fname} ({len(content)} -> {len(new_content)} bytes)")
    print(f"\nDone. Files in {DST}:")
    for f in sorted(DST.glob("*.py")):
        print(f"  {f.name}")


if __name__ == "__main__":
    main()
