from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
import uuid
from dataclasses import dataclass

import httpx
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from configs.settings import Settings
from models import ModelProviderConfig

logger = logging.getLogger(__name__)

ANSPIRE_PROVIDER = "anspire"
ANSPIRE_ENDPOINT_URL = "https://open-gateway.anspire.ai/v6"
DEFAULT_ANSPIRE_MODEL = "glm-5.2"

# This is deliberately a release-controlled allowlist. The management surface
# cannot redirect enterprise credentials to an arbitrary OpenAI-compatible URL.
ANSPIRE_CHAT_MODELS: tuple[dict[str, str], ...] = (
    {"id": "glm-5.2", "name": "GLM 5.2", "family": "GLM", "profile": "默认经营研究模型"},
    {"id": "gpt-5.6-sol", "name": "GPT 5.6 Sol", "family": "GPT", "profile": "旗舰复杂推理"},
    {"id": "gpt-5.6-terra", "name": "GPT 5.6 Terra", "family": "GPT", "profile": "平衡型知识工作"},
    {"id": "gpt-5.6-luna", "name": "GPT 5.6 Luna", "family": "GPT", "profile": "低延迟日常任务"},
    {"id": "gpt-5.5", "name": "GPT 5.5", "family": "GPT", "profile": "通用复杂推理"},
    {"id": "gpt-5.4", "name": "GPT 5.4", "family": "GPT", "profile": "高级经营研究"},
    {"id": "gpt-5.4-mini", "name": "GPT 5.4 Mini", "family": "GPT", "profile": "轻量快速分析"},
    {
        "id": "claude-opus-4-8",
        "name": "Claude Opus 4.8",
        "family": "Claude",
        "profile": "深度研究与推理",
    },
    {
        "id": "claude-opus-4-7",
        "name": "Claude Opus 4.7",
        "family": "Claude",
        "profile": "复杂长程分析",
    },
    {"id": "claude-opus-4-6", "name": "Claude Opus 4.6", "family": "Claude", "profile": "复杂推理"},
    {
        "id": "claude-sonnet-4-6",
        "name": "Claude Sonnet 4.6",
        "family": "Claude",
        "profile": "质量与速度平衡",
    },
    {
        "id": "claude-opus-5",
        "name": "Claude Opus 5",
        "family": "Claude",
        "profile": "下一代旗舰推理",
    },
    {
        "id": "claude-haiku-4-5-20251001",
        "name": "Claude Haiku 4.5",
        "family": "Claude",
        "profile": "快速日常问答",
    },
    {
        "id": "gemini-3.1-pro-preview",
        "name": "Gemini 3.1 Pro Preview",
        "family": "Gemini",
        "profile": "长上下文复杂分析",
    },
    {
        "id": "gemini-3-flash-preview",
        "name": "Gemini 3 Flash Preview",
        "family": "Gemini",
        "profile": "快速多模态分析",
    },
    {
        "id": "gemini-3.5-flash",
        "name": "Gemini 3.5 Flash",
        "family": "Gemini",
        "profile": "高吞吐问答",
    },
    {"id": "glm-5.1", "name": "GLM 5.1", "family": "GLM", "profile": "稳定通用"},
    {
        "id": "deepseek-v4-pro-max",
        "name": "DeepSeek V4 Pro Max",
        "family": "DeepSeek",
        "profile": "深度推理增强",
    },
    {
        "id": "deepseek-v4-flash",
        "name": "DeepSeek V4 Flash",
        "family": "DeepSeek",
        "profile": "快速推理",
    },
    {
        "id": "doubao-seed-2-1-pro",
        "name": "豆包 Seed 2.1 Pro",
        "family": "豆包",
        "profile": "复杂经营分析",
    },
    {
        "id": "doubao-seed-2-1-turbo",
        "name": "豆包 Seed 2.1 Turbo",
        "family": "豆包",
        "profile": "低延迟日常问数",
    },
    {
        "id": "doubao-seed-evolving",
        "name": "豆包 Seed Evolving",
        "family": "豆包",
        "profile": "自适应复杂任务",
    },
    {
        "id": "doubao-seed-character",
        "name": "豆包 Seed Character",
        "family": "豆包",
        "profile": "角色化交互",
    },
    {
        "id": "doubao-seed-2.0-pro",
        "name": "豆包 Seed 2.0 Pro",
        "family": "豆包",
        "profile": "稳定复杂分析",
    },
    {
        "id": "doubao-seed-2.0-lite",
        "name": "豆包 Seed 2.0 Lite",
        "family": "豆包",
        "profile": "轻量日常问答",
    },
    {
        "id": "doubao-seed-2.0-mini",
        "name": "豆包 Seed 2.0 Mini",
        "family": "豆包",
        "profile": "低成本高并发",
    },
    {
        "id": "doubao-seed-2.0-code",
        "name": "豆包 Seed 2.0 Code",
        "family": "豆包",
        "profile": "数据与代码分析",
    },
    {"id": "doubao-seed-1.8", "name": "豆包 Seed 1.8", "family": "豆包", "profile": "稳定通用"},
    {
        "id": "doubao-seed-1.6-flash",
        "name": "豆包 Seed 1.6 Flash",
        "family": "豆包",
        "profile": "极速问答",
    },
    {"id": "kimi-k2.5", "name": "Kimi K2.5", "family": "Kimi", "profile": "长文档分析"},
    {"id": "kimi-k3", "name": "Kimi K3", "family": "Kimi", "profile": "新一代长文档分析"},
    {"id": "minimax-m2.7", "name": "MiniMax M2.7", "family": "MiniMax", "profile": "复杂对话"},
    {"id": "minimax-m2.5", "name": "MiniMax M2.5", "family": "MiniMax", "profile": "稳定通用"},
    {"id": "qwen3.5-plus", "name": "Qwen 3.5 Plus", "family": "Qwen", "profile": "综合推理"},
    {"id": "qwen3.5-flash", "name": "Qwen 3.5 Flash", "family": "Qwen", "profile": "高并发低延迟"},
    {
        "id": "qwen3.5-397b-a17b",
        "name": "Qwen 3.5 397B A17B",
        "family": "Qwen",
        "profile": "大规模专家推理",
    },
    {
        "id": "qwen3.5-122b-a10b",
        "name": "Qwen 3.5 122B A10B",
        "family": "Qwen",
        "profile": "复杂通用分析",
    },
    {
        "id": "qwen3.5-35b-a3b",
        "name": "Qwen 3.5 35B A3B",
        "family": "Qwen",
        "profile": "平衡型推理",
    },
    {"id": "qwen3.5-27b", "name": "Qwen 3.5 27B", "family": "Qwen", "profile": "轻量推理"},
    {"id": "qwen3.7-max", "name": "Qwen 3.7 Max", "family": "Qwen", "profile": "旗舰综合推理"},
    {"id": "qwen3.8-max", "name": "Qwen 3.8 Max", "family": "Qwen", "profile": "新一代旗舰综合推理"},
)

# The backend exposes the complete provider catalog returned by Anspire's
# global gateway. Only chat/reasoning models are selectable by the Hermes
# answer channel; keeping the other modalities visible in the controlled
# catalog avoids silently presenting a partial provider integration.
ANSPIRE_NON_CHAT_MODELS: tuple[dict[str, str], ...] = (
    {
        "id": "cinema-generate-2.0",
        "name": "Cinema Generate 2.0",
        "family": "视频",
        "profile": "视频生成",
    },
    {
        "id": "doubao-seedance-1.5-pro",
        "name": "豆包 Seedance 1.5 Pro",
        "family": "视频",
        "profile": "视频生成",
    },
    {
        "id": "doubao-seedance-2.0-fast",
        "name": "豆包 Seedance 2.0 Fast",
        "family": "视频",
        "profile": "快速视频生成",
    },
    {
        "id": "doubao-seedance-2.0-mini",
        "name": "豆包 Seedance 2.0 Mini",
        "family": "视频",
        "profile": "轻量视频生成",
    },
    {
        "id": "doubao-seedream-4.5",
        "name": "豆包 Seedream 4.5",
        "family": "图像",
        "profile": "图像生成",
    },
    {
        "id": "doubao-seedream-5.0-lite",
        "name": "豆包 Seedream 5.0 Lite",
        "family": "图像",
        "profile": "轻量图像生成",
    },
    {
        "id": "doubao-seedream-5.0-pro",
        "name": "豆包 Seedream 5.0 Pro",
        "family": "图像",
        "profile": "高质量图像生成",
    },
    {"id": "gpt-image-2", "name": "GPT Image 2", "family": "图像", "profile": "图像生成"},
    {"id": "nano-banana-2", "name": "Nano Banana 2", "family": "图像", "profile": "图像生成与编辑"},
    {
        "id": "nano-banana-pro",
        "name": "Nano Banana Pro",
        "family": "图像",
        "profile": "专业图像生成与编辑",
    },
    {"id": "qwen3-rerank", "name": "Qwen 3 Rerank", "family": "检索", "profile": "文本重排序"},
    {
        "id": "qwen3-vl-embedding",
        "name": "Qwen 3 VL Embedding",
        "family": "向量",
        "profile": "多模态向量化",
    },
    {
        "id": "qwen3-vl-rerank",
        "name": "Qwen 3 VL Rerank",
        "family": "检索",
        "profile": "多模态重排序",
    },
    {
        "id": "text-embedding-v4",
        "name": "Text Embedding V4",
        "family": "向量",
        "profile": "文本向量化",
    },
)

ANSPIRE_MODELS: tuple[dict[str, object], ...] = tuple(
    {**item, "capability": "chat", "selectable": True} for item in ANSPIRE_CHAT_MODELS
) + tuple(
    {
        **item,
        "capability": (
            "video"
            if item["family"] == "视频"
            else "image"
            if item["family"] == "图像"
            else "embedding"
            if item["family"] == "向量"
            else "rerank"
        ),
        "selectable": False,
    }
    for item in ANSPIRE_NON_CHAT_MODELS
)
ANSPIRE_MODEL_IDS = frozenset(item["id"] for item in ANSPIRE_CHAT_MODELS)


class AnspireConfigurationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class EncryptedCredential:
    ciphertext: str
    nonce: str
    hint: str
    key_version: str


def validate_anspire_model(model_id: str) -> str:
    normalized = model_id.strip().lower()
    if normalized not in ANSPIRE_MODEL_IDS:
        raise AnspireConfigurationError(
            "anspire_model_not_allowed",
            "所选模型不在当前 Anspire 生产白名单中",
        )
    return normalized


def validate_anspire_api_key(api_key: str) -> str:
    normalized = api_key.strip()
    if len(normalized) < 16 or len(normalized) > 512 or any(char.isspace() for char in normalized):
        raise AnspireConfigurationError("anspire_api_key_invalid", "Anspire API Key 格式无效")
    return normalized


def _aad(enterprise_id: uuid.UUID, key_version: str) -> bytes:
    return f"executive-ai\x00{enterprise_id}\x00{ANSPIRE_PROVIDER}\x00{key_version}".encode()


def encrypt_anspire_api_key(
    api_key: str,
    *,
    enterprise_id: uuid.UUID,
    settings: Settings,
) -> EncryptedCredential:
    normalized = validate_anspire_api_key(api_key)
    version = settings.integration_encryption_key_version
    nonce = os.urandom(12)
    ciphertext = AESGCM(settings.integration_encryption_keys()[version]).encrypt(
        nonce,
        normalized.encode(),
        _aad(enterprise_id, version),
    )
    return EncryptedCredential(
        ciphertext=base64.urlsafe_b64encode(ciphertext).decode("ascii"),
        nonce=base64.urlsafe_b64encode(nonce).decode("ascii"),
        hint=normalized[-4:],
        key_version=version,
    )


def decrypt_anspire_api_key(config: ModelProviderConfig, settings: Settings) -> str:
    if not config.api_key_ciphertext or not config.api_key_nonce:
        raise AnspireConfigurationError(
            "anspire_not_configured",
            "尚未配置 Anspire API Key",
        )
    encryption_key = settings.integration_encryption_keys().get(config.encryption_key_version)
    if encryption_key is None:
        raise AnspireConfigurationError(
            "anspire_key_version_unavailable",
            "Anspire 凭证所需的历史加密密钥未加载",
        )
    try:
        plaintext = AESGCM(encryption_key).decrypt(
            base64.urlsafe_b64decode(config.api_key_nonce.encode("ascii")),
            base64.urlsafe_b64decode(config.api_key_ciphertext.encode("ascii")),
            _aad(config.enterprise_id, config.encryption_key_version),
        )
    except (InvalidTag, ValueError, UnicodeError) as exc:
        raise AnspireConfigurationError(
            "anspire_credential_integrity_error",
            "Anspire 凭证完整性校验失败",
        ) from exc
    try:
        return validate_anspire_api_key(plaintext.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise AnspireConfigurationError(
            "anspire_credential_integrity_error",
            "Anspire 凭证无法解密",
        ) from exc


def masked_api_key(config: ModelProviderConfig | None) -> str | None:
    if config is None or not config.api_key_hint:
        return None
    return f"sk-••••••••{config.api_key_hint}"


def runtime_provider_config(
    config: ModelProviderConfig,
    settings: Settings,
    *,
    model_id: str | None = None,
) -> dict[str, str]:
    if config.provider != ANSPIRE_PROVIDER or config.endpoint_url != ANSPIRE_ENDPOINT_URL:
        raise AnspireConfigurationError(
            "anspire_provider_invalid",
            "模型配置不是受控的 Anspire 接入",
        )
    if not config.is_enabled or config.last_test_status != "success":
        raise AnspireConfigurationError(
            "anspire_not_enabled",
            "Anspire 模型尚未通过测试并启用",
        )
    return {
        "provider": ANSPIRE_PROVIDER,
        "endpoint_url": ANSPIRE_ENDPOINT_URL,
        "model_id": validate_anspire_model(model_id or config.model_id),
        "api_key": decrypt_anspire_api_key(config, settings),
    }


# --------------------------------------------------------------------------
# 网关动态拉取（叠加白名单过滤）
# --------------------------------------------------------------------------
# 进程内缓存：(endpoint_url, api_key_hint) -> (fetch_timestamp, gateway_model_ids)
# 同一企业同一 endpoint 在 TTL 内复用，避免每次请求都打网关。
_GATEWAY_MODELS_CACHE: dict[tuple[str, str], tuple[float, frozenset[str]]] = {}
_GATEWAY_MODELS_TTL = 3600.0  # 秒
# 网关拉取并发去重锁：同一 cache_key 的并发请求只打一次网关，其他等结果。
_GATEWAY_MODELS_LOCKS: dict[tuple[str, str], asyncio.Lock] = {}


async def fetch_anspire_chat_model_ids(
    api_key: str,
    endpoint_url: str = ANSPIRE_ENDPOINT_URL,
    *,
    timeout: float = 2.0,
) -> frozenset[str]:
    """从 Anspire 网关 ``GET /models`` 拉取当前可用的模型 ID 集合。

    返回网关报告的模型 ID（已小写化）。网关返回 4xx/5xx 或格式异常时抛
    :class:`AnspireConfigurationError`，由调用方决定是否回退到静态白名单。
    """
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    url = f"{endpoint_url.rstrip('/')}/models"
    # 打印调用的接口和鉴权信息（仅 key 后 4 位，避免泄露完整密钥）
    print(
        f"[anspire] GET {url}  api_key=sk-***{api_key[-4:] if api_key else 'unknown'}",
        flush=True,
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, headers=headers)
    print(
        f"[anspire] <- status={resp.status_code} content_length={len(resp.content)}",
        flush=True,
    )
    if resp.status_code != 200:
        print(
            f"[anspire] !! failed url={url} status={resp.status_code} body={resp.text[:500]}",
            flush=True,
        )
        raise AnspireConfigurationError(
            "anspire_gateway_unavailable",
            f"Anspire 网关 /models 返回 HTTP {resp.status_code}",
        )
    payload = resp.json()
    items = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        print(
            f"[anspire] !! invalid_format url={url} payload_keys="
            f"{list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__}",
            flush=True,
        )
        raise AnspireConfigurationError(
            "anspire_gateway_response_invalid",
            "Anspire 网关 /models 返回格式异常",
        )
    model_ids = frozenset(
        str(item["id"]).strip().lower()
        for item in items
        if isinstance(item, dict) and item.get("id")
    )
    print(
        f"[anspire] parsed count={len(model_ids)} sample={sorted(list(model_ids))[:5]}",
        flush=True,
    )
    return model_ids


async def list_anspire_models_for_admin(
    config: ModelProviderConfig | None,
    settings: Settings,
) -> list[dict[str, object]]:
    """返回给管理后台的模型目录。

    优先从 Anspire 网关拉取当前可用模型，叠加静态白名单过滤：

    - 网关有 + 白名单有 → 展示（已审核且可用）
    - 网关无 + 白名单有 → 不展示（已下线）
    - 网关有 + 白名单无 → 不展示（未审核，需先更新白名单发版）
    - 网关不可用或企业未配 API Key → 回退到静态白名单全量

    non-chat 模型（图像/视频/向量/rerank）始终用静态白名单，因为网关
    ``/models`` 主要返回 chat 模型，且这些模型不参与聊天路由。
    """
    static_models = list(ANSPIRE_MODELS)
    if config is None or not config.api_key_ciphertext or not config.api_key_nonce:
        return static_models

    try:
        api_key = decrypt_anspire_api_key(config, settings)
    except AnspireConfigurationError:
        return static_models

    endpoint = config.endpoint_url or ANSPIRE_ENDPOINT_URL
    cache_key = (endpoint, api_key[-4:])
    now = time.time()
    cached = _GATEWAY_MODELS_CACHE.get(cache_key)
    if cached and now - cached[0] < _GATEWAY_MODELS_TTL:
        gateway_ids = cached[1]
    else:
        # 加锁去重：同一 cache_key 的并发请求只打一次网关
        lock = _GATEWAY_MODELS_LOCKS.setdefault(cache_key, asyncio.Lock())
        async with lock:
            # 双检：拿到锁后再看一次缓存（可能前一个持锁者已写入）
            cached = _GATEWAY_MODELS_CACHE.get(cache_key)
            now = time.time()
            if cached and now - cached[0] < _GATEWAY_MODELS_TTL:
                gateway_ids = cached[1]
            else:
                try:
                    gateway_ids = await fetch_anspire_chat_model_ids(api_key, endpoint)
                    _GATEWAY_MODELS_CACHE[cache_key] = (now, gateway_ids)
                except (AnspireConfigurationError, httpx.HTTPError, ValueError) as exc:
                    logger.warning("anspire_gateway_models_fetch_failed error=%s", exc)
                    return static_models

    result: list[dict[str, object]] = []
    for model in static_models:
        if str(model.get("capability", "")) == "chat":
            if str(model["id"]) in gateway_ids:
                result.append(model)
        else:
            # non-chat 模型不依赖网关
            result.append(model)
    return result
