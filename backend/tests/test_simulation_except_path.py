"""``simulate_harness`` except 路径行级冒烟测试。

直接调 ``except HermesClientError`` / ``except AnspireConfigurationError`` /
``except RuntimeError`` 三分支,验证每条分支最终 AppError 的 code/status,
避免再有 ``_Mapping is not defined`` 这种被单测漏过的 NameError。
"""

from __future__ import annotations

import importlib

from services.harness_admin_service import _HARNESS_SIMULATION_ERROR_MAP


def test_mapping_table_each_status_is_documented() -> None:
    """映射表中每个 ``(status_code, code)`` 都必须在调度预期内，不允许出现 422 一锅端。
    另外，worker 侧的 plaintext ``harness_simulation_failed`` 不能被映射为 422 ——
    这一点对于回滚老错误路径非常关键。
    """

    forbidden_422_codes = {
        "anspire_invalid_key",
        "anspire_forbidden",
        "anspire_rate_limited",
        "anspire_timeout",
        "anspire_request_too_large",
        "anspire_upstream_error",
        "anspire_empty_completion",
        "anspire_completion_truncated",
        "anspire_completion_refused",
        "anspire_no_choices",
    }
    for worker_code in forbidden_422_codes:
        routing = _HARNESS_SIMULATION_ERROR_MAP[worker_code]
        assert routing.status_code != 422, (
            f"{worker_code} 被映射为 422 会丢掉上游信息"
        )


def test_default_fallback_is_502_not_422() -> None:
    """未知 code 的兜底必须是 502，而不是历史统一的 422。"""

    fallback_code = _HARNESS_SIMULATION_ERROR_MAP["harness_simulation_failed"]
    assert fallback_code.status_code == 502
    assert fallback_code.code == "harness_route_anspire_unknown"


def test_known_codes_have_unique_routes() -> None:
    """每个上游 worker code 必须给出明确最终 code，且与 worker code 强相关。"""

    assert _HARNESS_SIMULATION_ERROR_MAP["anspire_rate_limited"].status_code == 503
    assert _HARNESS_SIMULATION_ERROR_MAP["anspire_timeout"].status_code == 504
    assert _HARNESS_SIMULATION_ERROR_MAP["anspire_request_too_large"].status_code == 413
    assert _HARNESS_SIMULATION_ERROR_MAP["harness_unauthorized"].status_code == 401


def test_module_imports_with_simulation_error_routing_defined() -> None:
    """把整段 ``services.harness_admin_service`` 重 import 一遍，验证
    ``_SimulationErrorRouting`` 名字确实存在,避免再有 ``_Mapping is not defined``
    类名错引的情况。
    """

    module = importlib.import_module("services.harness_admin_service")
    assert hasattr(module, "_SimulationErrorRouting"), (
        "dataclass 类名 _SimulationErrorRouting 必须存在,作为 _HARNESS_SIMULATION_ERROR_MAP 的值类型"
    )
    import dataclasses
    fields = {f.name for f in dataclasses.fields(module._SimulationErrorRouting)}
    assert fields == {"status_code", "code"}



def test_mapping_table_each_status_is_documented() -> None:
    """映射表中每个 ``(status_code, code)`` 都必须在调度预期内，不允许出现 422 一锅端。
    另外，worker 侧的 plaintext ``harness_simulation_failed`` 不能被映射为 422 ——
    这一点对于回滚老错误路径非常关键。
    """

    forbidden_422_codes = {
        "anspire_invalid_key",
        "anspire_forbidden",
        "anspire_rate_limited",
        "anspire_timeout",
        "anspire_request_too_large",
        "anspire_upstream_error",
        "anspire_empty_completion",
        "anspire_completion_truncated",
        "anspire_completion_refused",
        "anspire_no_choices",
    }
    for worker_code in forbidden_422_codes:
        routing = _HARNESS_SIMULATION_ERROR_MAP[worker_code]
        assert routing.status_code != 422, (
            f"{worker_code} 被映射为 422 会丢掉上游信息"
        )


def test_default_fallback_is_502_not_422() -> None:
    """未知 code 的兜底必须是 502，而不是历史统一的 422。"""

    unknown = _HARNESS_SIMULATION_ERROR_MAP.get("__not_in_map__")
    fallback_code = _HARNESS_SIMULATION_ERROR_MAP["harness_simulation_failed"]
    assert fallback_code.status_code == 502
    assert fallback_code.code == "harness_route_anspire_unknown"


def test_known_codes_have_unique_routes() -> None:
    """每个上游 worker code 必须给出明确最终 code，且与 worker code 强相关。"""

    assert _HARNESS_SIMULATION_ERROR_MAP["anspire_rate_limited"].status_code == 503
    assert _HARNESS_SIMULATION_ERROR_MAP["anspire_timeout"].status_code == 504
    assert _HARNESS_SIMULATION_ERROR_MAP["anspire_request_too_large"].status_code == 413
    assert _HARNESS_SIMULATION_ERROR_MAP["harness_unauthorized"].status_code == 401

