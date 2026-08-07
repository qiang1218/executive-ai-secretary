"""``simulate_harness`` 错误码透传/分流测试。

worker 端 ``HermesRunError.code`` 与 ``simulate_harness`` 的最终 HTTP code 必须
可枚举,不依赖运行时。按 worker 给出的 code 查表,每条都对应一个明确最终
``(status_code, code)`` —— 不允许全部坍缩到 422。
"""

from __future__ import annotations

from services.hermes_client import HermesClientError
from services.harness_admin_service import _HARNESS_SIMULATION_ERROR_MAP


def test_routing_table_covers_all_known_worker_codes() -> None:
    expected_keys = {
        "anspire_invalid_key",
        "anspire_forbidden",
        "anspire_model_unavailable",
        "anspire_rate_limited",
        "anspire_timeout",
        "anspire_request_too_large",
        "anspire_upstream_error",
        "anspire_invalid_response",
        "anspire_no_choices",
        "anspire_empty_completion",
        "anspire_completion_truncated",
        "anspire_completion_refused",
        "harness_worker_invalid_response",
        "harness_unauthorized",
        "harness_simulation_failed",
    }
    missing = expected_keys - set(_HARNESS_SIMULATION_ERROR_MAP)
    assert not missing, f"未在映射表中: {sorted(missing)}"


def test_rate_limited_maps_to_503() -> None:
    routing = _HARNESS_SIMULATION_ERROR_MAP["anspire_rate_limited"]
    assert routing.status_code == 503
    assert routing.code == "harness_route_anspire_rate_limited"


def test_timeout_maps_to_504() -> None:
    routing = _HARNESS_SIMULATION_ERROR_MAP["anspire_timeout"]
    assert routing.status_code == 504
    assert routing.code == "harness_route_anspire_timeout"


def test_empty_completion_uses_dedicated_code() -> None:
    routing = _HARNESS_SIMULATION_ERROR_MAP["anspire_empty_completion"]
    assert routing.status_code == 502
    assert routing.code == "harness_route_anspire_empty_completion"


def test_request_too_large_maps_to_413() -> None:
    routing = _HARNESS_SIMULATION_ERROR_MAP["anspire_request_too_large"]
    assert routing.status_code == 413


def test_hermes_client_error_carries_code() -> None:
    exc = HermesClientError("anspire_empty_completion", 502, "boom")
    assert exc.code == "anspire_empty_completion"
    assert exc.status_code == 502
    assert "boom" in str(exc)
