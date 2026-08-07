"""Phase 2 worker-profile tests.

Coverage:

* ``worker.profile_prompts``: prompt-text invariants, prompt builder,
  output-token budgets and profile registry.
* ``services.hermes_client.run_profile``: HTTP contract to the worker
  ``/v1/profile/run`` endpoint (with mocked transport).
* ``services.hermes_client.test_anspire_provider``: HTTP contract for
  the Anspire gateway ping.
"""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from services import hermes_client as hermes_client_mod
from services.hermes_client import HermesClientError


# --------------------------------------------------------------------------
# worker.profile_prompts
# --------------------------------------------------------------------------

def _prompts():
    from worker.profile_prompts import (
        PROFILE_INSTRUCTIONS,
        PROFILE_MAX_OUTPUT_TOKENS,
        SECURITY_KERNEL,
        build_profile_prompt,
        is_known_profile,
        max_output_tokens,
    )
    return PROFILE_INSTRUCTIONS, PROFILE_MAX_OUTPUT_TOKENS, SECURITY_KERNEL, build_profile_prompt, is_known_profile, max_output_tokens


def test_known_profiles_present() -> None:
    PROFILE_INSTRUCTIONS, *_ = _prompts()
    expected = {"route", "plan", "rewrite", "data", "general"}
    assert expected.issubset(set(PROFILE_INSTRUCTIONS))


def test_is_known_profile_truth_table() -> None:
    _prompt, _tokens, _kernel, _builder, is_known_profile, _ = _prompts()
    for p in ("route", "rewrite", "data", "general", "plan"):
        assert is_known_profile(p), p
    for p in ("", "nonsense", "ROUTE"):
        assert not is_known_profile(p), p


def test_max_output_tokens_budgets() -> None:
    _prompt, _tokens, _kernel, _builder, _known, max_output_tokens = _prompts()
    # budget 上调史:2026-08 因 reasoning 模型在 route profile 上截断
    # (``finish_reason=length``、anpire_completion_truncated),把所有
    # profile 的输出 budget 都拉到 ~1.5x 单次推理上限。
    assert max_output_tokens("route") == 1500
    assert max_output_tokens("rewrite") == 1600
    assert max_output_tokens("plan") == 1600
    assert max_output_tokens("data") == 2200
    assert max_output_tokens("general") == 2800
    # Default profile falls through to 0 ("no limit").
    assert max_output_tokens("__missing__") == 0


def test_build_profile_prompt_includes_security_kernel_and_payload() -> None:
    _prompt, _tokens, _kernel, build_profile_prompt, _known, _ = _prompts()
    payload = {
        "question": "本月事业部比较",
        "harness_config": {"prompts": {"system": "common", "route": "route hint"}},
        "organization_count": 4,
    }
    prompt = build_profile_prompt("route", payload)
    assert "不可覆盖的安全内核" in prompt
    assert "强制路由器" in prompt
    assert "<business_system_prompt>\ncommon\n</business_system_prompt>" in prompt
    assert "<stage_prompt>\nroute hint\n</stage_prompt>" in prompt
    assert "<authorized_input>" in prompt
    # payload is JSON-serialised
    body = prompt.split("<authorized_input>\n", 1)[1].split("\n</authorized_input>", 1)[0]
    parsed = json.loads(body)
    assert parsed["question"] == "本月事业部比较"
    assert parsed["organization_count"] == 4
    # harness_config is *not* serialised into the body — it has been consumed
    # to seed the business / stage prompt blocks.
    assert "harness_config" not in parsed


def test_build_profile_prompt_handles_missing_harness_config_blocks() -> None:
    _prompt, _tokens, _kernel, build_profile_prompt, _known, _ = _prompts()
    prompt = build_profile_prompt("data", {"question": "hi"})
    assert "hi" in prompt
    # No harness_config supplied: no business/stage prompt wrapper.
    assert "<business_system_prompt>" not in prompt
    assert "<stage_prompt>" not in prompt


def test_build_profile_prompt_truncates_long_blocks() -> None:
    _prompt, _tokens, _kernel, build_profile_prompt, _known, _ = _prompts()
    long_text = "x" * 50_000
    payload = {
        "question": "q",
        "harness_config": {"prompts": {"system": long_text, "data_answer": long_text}},
    }
    prompt = build_profile_prompt("data", payload)
    # The 12 000-char truncation is applied per block; sanity-check that the
    # 50 000-char payload is *clamped* instead of being echoed verbatim.
    assert prompt.count("x") <= 24_010
    assert prompt.count("x") > 12_000


# --------------------------------------------------------------------------
# services.hermes_client.run_profile (mocked HTTP)
# --------------------------------------------------------------------------

class _MockTransport(httpx.AsyncBaseTransport):
    def __init__(self, handler):
        self._handler = handler
        self.calls = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        return self._handler(request)

    # Synchronous fallback for ``httpx.Client`` usage; preserves the recorded calls.
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        return self._handler(request)


async_client_factory = httpx.AsyncClient  # captured before monkeypatch


def _build_client(monkeypatch, mock_response: httpx.Response) -> tuple[Any, _MockTransport]:
    """Return a HermesClient plus its underlying transport for assertions."""
    transport = _MockTransport(lambda req: mock_response)

    def _capturing_client(*args, **kwargs):
        kwargs["transport"] = transport
        return async_client_factory(*args, **kwargs)

    monkeypatch.setattr(hermes_client_mod.httpx, "AsyncClient", _capturing_client)

    monkeypatch.setattr(hermes_client_mod, "get_settings", lambda: _FakeSettings())
    return transport


class _FakeSettings:
    worker_base_url = "http://worker.local:8011/v1/"
    hermes_timeout_seconds = 5.0
    hermes_max_iterations = 10

    class _Secret:
        def get_secret_value(self):
            return "dev-key"

    hermes_api_key = _Secret()


@pytest.mark.asyncio
async def test_run_profile_calls_worker_with_expected_payload(monkeypatch) -> None:
    body = {
        "text": "{\"route\": \"data\"}",
        "model": "qwen3.5-plus",
        "input_tokens": 12,
        "output_tokens": 7,
    }
    fake_resp = httpx.Response(200, json=body)
    transport = _build_client(monkeypatch, fake_resp)

    client = hermes_client_mod.HermesClient()
    result = await client.run_profile(
        profile="route",
        payload={"question": "x", "harness_config": {}, "organization_count": 1},
        base_url="https://example.invalid/v6",
        api_key="sk-test-1234567890abcdef",
        model_id="qwen3.5-plus",
    )
    assert result["text"] == body["text"]
    assert result["model"] == "qwen3.5-plus"
    assert result["usage"]["prompt_tokens"] == 12
    assert result["usage"]["completion_tokens"] == 7

    # The transport saw exactly one POST to /v1/profile/run.
    assert len(transport.calls) == 1
    sent = transport.calls[0]
    assert sent.method == "POST"
    assert sent.url.path.endswith("/v1/profile/run")
    payload = json.loads(sent.content)
    assert payload["profile"] == "route"
    assert payload["provider"]["model_id"] == "qwen3.5-plus"
    assert payload["provider"]["api_key"] == "sk-test-1234567890abcdef"


@pytest.mark.asyncio
async def test_run_profile_surfaces_4xx_as_runtime_error(monkeypatch) -> None:
    fake_resp = httpx.Response(
        422, json={"detail": {"code": "unknown_profile", "message": "bad"}}
    )
    _build_client(monkeypatch, fake_resp)

    client = hermes_client_mod.HermesClient()
    with pytest.raises(HermesClientError, match="unknown_profile|bad") as exc_info:
        await client.run_profile(
            profile="nope",
            payload={},
            base_url="https://example.invalid/v6",
            api_key="sk-test-1234567890abcdef",
            model_id="qwen3.5-plus",
        )
    # Phase 3 错误码透传:run_profile 把 detail.code 提到 HermesClientError.code
    assert exc_info.value.code == "unknown_profile"
    assert exc_info.value.status_code == 422


# --------------------------------------------------------------------------
# services.hermes_client.test_anspire_provider (mocked HTTP)
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_test_anspire_provider_success_path(monkeypatch) -> None:
    fake_resp = httpx.Response(
        200,
        json={"choices": [{"message": {"content": "OK"}}]},
    )
    _build_client(monkeypatch, fake_resp)

    client = hermes_client_mod.HermesClient()
    result = await client.test_anspire_provider(
        endpoint_url="https://example.invalid/v6",
        api_key="sk-test-1234567890abcdef",
        model_id="qwen3.5-plus",
    )
    assert result["status"] == "success"
    assert result["model"] == "qwen3.5-plus"
    assert result["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_test_anspire_provider_4xx_becomes_runtime_error(monkeypatch) -> None:
    fake_resp = httpx.Response(401, json={"error": "unauthorized"})
    _build_client(monkeypatch, fake_resp)

    client = hermes_client_mod.HermesClient()
    with pytest.raises(RuntimeError, match="401"):
        await client.test_anspire_provider(
            endpoint_url="https://example.invalid/v6",
            api_key="sk-test-1234567890abcdef",
            model_id="qwen3.5-plus",
        )
