"""Anspire 网关 embedding 客户端。

封装对 ``https://open-gateway.anspire.cn/v6/embeddings`` 接口的调用，
提供单条 / 批量 embedding 生成能力。

API key 与 chat completion 共用同一组 Anspire 凭证（``ModelProviderConfig``
``api_key_ciphertext`` / ``api_key_nonce`` AES-GCM 加密存储），通过
``decrypt_anspire_api_key`` 解密后传入本客户端。

接口契约（OpenAI 兼容）：

    POST /v6/embeddings
    Authorization: Bearer sk-xxx
    Content-Type: application/json

    {
      "model": "text-embedding-v4",
      "input": ["text1", "text2", ...]
    }

    200 OK
    {
      "data": [
        {"embedding": [0.1, 0.2, ...], "index": 0},
        {"embedding": [0.3, 0.4, ...], "index": 1}
      ],
      "model": "text-embedding-v4",
      "usage": {"prompt_tokens": 12, "total_tokens": 12}
    }

注：``qwen3-vl-embedding`` 是视觉语言模型，需要多模态 JSON 对象格式 input，
不能直接传纯文本数组；``text-embedding-v4`` 是纯文本 embedding 模型，
输出维度 1024，与 ``entity_embeddings`` 表固定维度一致。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx

from configs.settings import Settings
from services.anspire import (
    ANSPIRE_ENDPOINT_URL,
    ANSPIRE_PROVIDER,
    decrypt_anspire_api_key,
    runtime_provider_config,
)
from models import ModelProviderConfig
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ── 异常 ──────────────────────────────────────────────────


class EmbeddingError(RuntimeError):
    """Embedding 调用失败。``code`` 用于日志区分；``message`` 给上层显示。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


# ── 凭证解析 ──────────────────────────────────────────────


async def resolve_anspire_api_key(session: AsyncSession) -> str:
    """从 ``ModelProviderConfig`` 解密出 Anspire API key。

    要求企业已配置 Anspire 模型供应商且通过测试（``is_enabled=True`` +
    ``last_test_status='success'``），否则抛 ``EmbeddingError``。
    """
    result = await session.execute(
        select(ModelProviderConfig).where(
            ModelProviderConfig.provider == ANSPIRE_PROVIDER,
            ModelProviderConfig.endpoint_url == ANSPIRE_ENDPOINT_URL,
            ModelProviderConfig.is_enabled.is_(True),
            ModelProviderConfig.last_test_status == "success",
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise EmbeddingError(
            "anspire_not_configured",
            "Anspire 模型供应商未配置或未通过测试，无法调用 embedding 接口",
        )
    try:
        return decrypt_anspire_api_key(config, _get_settings_for_decrypt())
    except Exception as exc:  # noqa: BLE001
        logger.exception("anspire_api_key_decrypt_failed")
        raise EmbeddingError(
            "api_key_decrypt_failed",
            f"Anspire API key 解密失败：{exc}",
        ) from exc


def _get_settings_for_decrypt() -> Settings:
    """延迟加载 Settings，避免循环依赖。"""
    from configs.settings import get_settings
    return get_settings()


# ── 客户端 ────────────────────────────────────────────────


@dataclass(frozen=True)
class _EmbeddingConfig:
    endpoint: str
    model: str
    api_key: str
    timeout: float
    batch_size: int


async def _build_config(settings: Settings, api_key: str) -> _EmbeddingConfig:
    return _EmbeddingConfig(
        endpoint=settings.anspire_embedding_endpoint,
        model=settings.anspire_embedding_model,
        api_key=api_key,
        timeout=settings.embedding_request_timeout,
        batch_size=settings.embedding_batch_size,
    )


async def _call_embeddings_api(
    cfg: _EmbeddingConfig, inputs: list[str]
) -> list[list[float]]:
    """单次批量调用 embeddings 接口；返回与 ``inputs`` 等长、顺序一致的向量列表。"""
    if not inputs:
        return []
    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": cfg.model, "input": inputs}
    try:
        async with httpx.AsyncClient(timeout=cfg.timeout) as client:
            resp = await client.post(cfg.endpoint, headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise EmbeddingError(
            "embedding_request_failed",
            f"Embedding 接口请求失败：{exc}",
        ) from exc

    if resp.status_code != 200:
        raise EmbeddingError(
            "embedding_http_error",
            f"Embedding 接口返回 HTTP {resp.status_code}: {resp.text[:300]}",
        )
    try:
        body = resp.json()
        data_items = body["data"]
        # 按 index 排序确保顺序与 inputs 一致
        data_items.sort(key=lambda x: x.get("index", 0))
        return [list(map(float, item["embedding"])) for item in data_items]
    except (KeyError, ValueError, TypeError) as exc:
        raise EmbeddingError(
            "embedding_response_invalid",
            f"Embedding 接口返回格式异常：{exc}",
        ) from exc


async def embed_texts(
    texts: list[str],
    *,
    settings: Settings,
    api_key: str,
) -> list[list[float]]:
    """批量生成 embedding。

    内部按 ``settings.embedding_batch_size`` 分片调用 API；任一批次失败则
    整体抛 ``EmbeddingError``（调用方决定是否记录失败行继续后续批次）。

    返回顺序与 ``texts`` 一致；空列表返回空列表。
    """
    if not texts:
        return []
    cfg = await _build_config(settings, api_key)
    results: list[list[float]] = []
    # 切片顺序调用（避免并发触发网关限流；如需提速可改 asyncio.gather + 限流）
    for i in range(0, len(texts), cfg.batch_size):
        batch = texts[i : i + cfg.batch_size]
        vectors = await _call_embeddings_api(cfg, batch)
        if len(vectors) != len(batch):
            raise EmbeddingError(
                "embedding_count_mismatch",
                f"Embedding 接口返回向量数 {len(vectors)} 与输入 {len(batch)} 不一致",
            )
        results.extend(vectors)
    return results


async def embed_single(text: str, *, settings: Settings, api_key: str) -> list[float]:
    """单条 embedding；主要用于检索时把 query 转 vector。"""
    vectors = await embed_texts([text], settings=settings, api_key=api_key)
    return vectors[0]


__all__ = [
    "EmbeddingError",
    "resolve_anspire_api_key",
    "embed_texts",
    "embed_single",
]
