"""Anspire 网关 /models 拉取对照脚本。

用法：
    python scripts/test_anspire_models.py sk-你的真实key

输出：
    1. 网关返回的模型总数
    2. 在静态白名单中的（会展示）
    3. 网关有但白名单没有的（未审核，不展示）
    4. 白名单有但网关没有的（已下线，不展示）
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 把 src 加入 path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from services.anspire import (  # noqa: E402
    ANSPIRE_MODELS,
    ANSPIRE_MODEL_IDS,
    fetch_anspire_chat_model_ids,
)


async def main(api_key: str) -> None:
    # 1. 拉取网关模型
    print("=" * 70)
    print("1. 拉取网关 /models ...")
    try:
        gateway_ids = await fetch_anspire_chat_model_ids(api_key)
    except Exception as exc:
        print(f"   拉取失败: {exc}")
        return

    print(f"   网关返回 {len(gateway_ids)} 个模型")
    print(f"   样例: {sorted(list(gateway_ids))[:10]}")
    print()

    # 2. 静态白名单
    chat_static = {str(m["id"]) for m in ANSPIRE_MODELS if m.get("capability") == "chat"}
    non_chat_static = {str(m["id"]) for m in ANSPIRE_MODELS if m.get("capability") != "chat"}
    print("=" * 70)
    print(f"2. 静态白名单: {len(chat_static)} 个 chat + {len(non_chat_static)} 个 non-chat = {len(ANSPIRE_MODELS)} 个")
    print()

    # 3. 交集（会展示的 chat 模型）
    in_both = gateway_ids & ANSPIRE_MODEL_IDS
    print("=" * 70)
    print(f"3. 网关有 + 白名单有（会展示的 chat 模型）: {len(in_both)} 个")
    for mid in sorted(in_both):
        print(f"   - {mid}")
    print()

    # 4. 网关有但白名单没有（未审核）
    gateway_only = gateway_ids - ANSPIRE_MODEL_IDS
    print("=" * 70)
    print(f"4. 网关有 + 白名单没有（未审核，不展示）: {len(gateway_only)} 个")
    for mid in sorted(gateway_only):
        print(f"   - {mid}")
    print()

    # 5. 白名单有但网关没有（已下线）
    whitelist_only = ANSPIRE_MODEL_IDS - gateway_ids
    print("=" * 70)
    print(f"5. 白名单有 + 网关没有（已下线，不展示）: {len(whitelist_only)} 个")
    for mid in sorted(whitelist_only):
        print(f"   - {mid}")
    print()

    # 6. 最终展示结果
    print("=" * 70)
    print(f"6. 最终展示给管理后台: {len(in_both)} chat + {len(non_chat_static)} non-chat = {len(in_both) + len(non_chat_static)} 个")
    print()

    # 7. 建议
    if gateway_only:
        print("=" * 70)
        print("7. 建议补充到静态白名单的模型（网关有但白名单没有）:")
        for mid in sorted(gateway_only):
            print(f'    {{"id": "{mid}", "name": "{mid}", "family": "未知", "profile": ""}},')
        print()
        print("   把上面的条目加到 src/services/anspire.py 的 ANSPIRE_CHAT_MODELS 里")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scripts/test_anspire_models.py sk-你的真实key")
        sys.exit(1)
    asyncio.run(main(sys.argv[1].strip()))
