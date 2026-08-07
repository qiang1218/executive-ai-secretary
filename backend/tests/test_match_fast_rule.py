"""``match_fast_rule`` 的纯函数行为测试。

这些断言代替 service 层调用前的隐性约定,任何把 ``fast_rules`` 引入回归
都会首先在这里暴露。
"""

from __future__ import annotations

import pytest

from services.harness_config import (
    explain_match,
    match_fast_rule,
    validate_harness_config,
)


def _cfg(rules: list[dict], prompts: dict | None = None) -> dict:
    return {
        "prompts": prompts
        or {key: "你" * 14 for key in ("system", "route", "rewrite", "plan", "data_answer", "general_answer")},
        "glossary": [],
        "fast_rules": rules,
    }


def test_priority_higher_wins_when_array_unsorted() -> None:
    """match_fast_rule 自身按 priority 倒序匹配,不依赖 validate 路径。"""

    cfg = _cfg(
        [
            {
                "id": "low",
                "name": "low",
                "enabled": True,
                "priority": 30,
                "match_mode": "any",
                "terms": ["事业"],
                "exclusions": [],
                "route": "data",
                "candidate_tools": [],
            },
            {
                "id": "high",
                "name": "high",
                "enabled": True,
                "priority": 80,
                "match_mode": "any",
                "terms": ["事业部"],
                "exclusions": [],
                "route": "data",
                "candidate_tools": [],
            },
        ]
    )
    hit = match_fast_rule("本月事业部收入如何", cfg)
    assert hit is not None and hit["id"] == "high"


def test_same_priority_breaks_tie_by_lexicographic_id() -> None:
    cfg = _cfg(
        [
            {
                "id": "z-high",
                "name": "z",
                "enabled": True,
                "priority": 50,
                "match_mode": "any",
                "terms": ["事业部"],
                "exclusions": [],
                "route": "data",
                "candidate_tools": [],
            },
            {
                "id": "a-high",
                "name": "a",
                "enabled": True,
                "priority": 50,
                "match_mode": "any",
                "terms": ["事业部"],
                "exclusions": [],
                "route": "general",
                "candidate_tools": [],
            },
        ]
    )
    hit = match_fast_rule("本月事业部收入如何", cfg)
    assert hit is not None and hit["id"] == "a-high"


def test_exclusion_skips_rule_but_other_rules_still_try() -> None:
    cfg = _cfg(
        [
            {
                "id": "guarded",
                "name": "guarded",
                "enabled": True,
                "priority": 90,
                "match_mode": "any",
                "terms": ["怎么"],
                "exclusions": ["怎么写"],
                "route": "general",
                "candidate_tools": [],
            },
            {
                "id": "fallback",
                "name": "fallback",
                "enabled": True,
                "priority": 30,
                "match_mode": "any",
                "terms": ["怎么"],
                "exclusions": [],
                "route": "data",
                "candidate_tools": [],
            },
        ]
    )
    assert match_fast_rule("这个怎么写文档", cfg)["id"] == "fallback"
    assert match_fast_rule("这个怎么完成", cfg)["id"] == "guarded"


def test_match_mode_all_requires_every_term() -> None:
    cfg = _cfg(
        [
            {
                "id": "all",
                "name": "all",
                "enabled": True,
                "priority": 50,
                "match_mode": "all",
                "terms": ["本月", "利润"],
                "exclusions": [],
                "route": "data",
                "candidate_tools": [],
            }
        ]
    )
    assert match_fast_rule("本月利润情况", cfg) is not None
    assert match_fast_rule("本月收入情况", cfg) is None


def test_disabled_rule_is_ignored_even_at_highest_priority() -> None:
    cfg = _cfg(
        [
            {
                "id": "off",
                "name": "off",
                "enabled": False,
                "priority": 999,
                "match_mode": "any",
                "terms": ["事业部"],
                "exclusions": [],
                "route": "data",
                "candidate_tools": [],
            },
            {
                "id": "on",
                "name": "on",
                "enabled": True,
                "priority": 0,
                "match_mode": "any",
                "terms": ["事业部"],
                "exclusions": [],
                "route": "general",
                "candidate_tools": [],
            },
        ]
    )
    hit = match_fast_rule("本月事业部收入如何", cfg)
    assert hit is not None and hit["id"] == "on"


def test_case_folded_substring_matching() -> None:
    cfg = _cfg(
        [
            {
                "id": "en",
                "name": "en",
                "enabled": True,
                "priority": 10,
                "match_mode": "any",
                "terms": ["ROI"],
                "exclusions": [],
                "route": "data",
                "candidate_tools": [],
            }
        ]
    )
    assert match_fast_rule("please show me the roi analysis", cfg) is not None
    assert match_fast_rule("ROItotal by region", cfg) is not None


def test_explain_match_records_skipped_reasons_when_nothing_matches() -> None:
    cfg = _cfg(
        [
            {
                "id": "r1",
                "name": "r1",
                "enabled": True,
                "priority": 50,
                "match_mode": "any",
                "terms": ["事业部"],
                "exclusions": ["事业部长"],
                "route": "data",
                "candidate_tools": [],
            },
            {
                "id": "r2",
                "name": "r2",
                "enabled": True,
                "priority": 80,
                "match_mode": "any",
                "terms": ["子公司"],
                "exclusions": [],
                "route": "general",
                "candidate_tools": [],
            },
            {
                "id": "off",
                "name": "off",
                "enabled": False,
                "priority": 10,
                "match_mode": "any",
                "terms": ["事业部"],
                "exclusions": [],
                "route": "data",
                "candidate_tools": [],
            },
        ]
    )
    result = explain_match("今天天气不错", cfg)
    assert result["matched_rule_id"] is None
    reasons = {item["id"]: item["reason"] for item in result["skipped_rule_ids"]}
    assert reasons["r2"] == "terms_missed"
    assert reasons["r1"] == "terms_missed"
    assert reasons["off"] == "disabled"


def test_explain_match_records_exclusion_hit() -> None:
    cfg = _cfg(
        [
            {
                "id": "r1",
                "name": "r1",
                "enabled": True,
                "priority": 50,
                "match_mode": "any",
                "terms": ["事业"],
                "exclusions": ["事业部长"],
                "route": "data",
                "candidate_tools": [],
            }
        ]
    )
    result = explain_match("事业部长调研", cfg)
    assert result["matched_rule_id"] is None
    assert result["skipped_rule_ids"] == [{"id": "r1", "reason": "exclusion_hit"}]


def test_validate_then_match_is_idempotent() -> None:
    """validate 路径已 sort;match 路径再 sort 一次结果应一致 — 不会跳到不该选的规则。"""

    cfg = _cfg(
        [
            {
                "id": "low",
                "name": "low",
                "enabled": True,
                "priority": 30,
                "match_mode": "any",
                "terms": ["事业"],
                "exclusions": [],
                "route": "data",
                "candidate_tools": [],
            },
            {
                "id": "high",
                "name": "high",
                "enabled": True,
                "priority": 80,
                "match_mode": "any",
                "terms": ["事业部"],
                "exclusions": [],
                "route": "data",
                "candidate_tools": [],
            },
        ]
    )
    cleaned = validate_harness_config(cfg)
    hit = match_fast_rule("本月事业部收入如何", cleaned)
    assert hit is not None and hit["id"] == "high"


def test_explain_match_skipped_when_no_rules() -> None:
    result = explain_match("随便聊聊", _cfg([]))
    assert result["matched_rule_id"] is None
    assert result["matched_rule"] is None
    assert result["skipped_rule_ids"] == []
