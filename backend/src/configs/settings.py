from __future__ import annotations

import base64
import json
import re
import stat
import sys
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

KEY_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",
    )

    app_name: str = "董事长人工智能研究员"
    app_version: str = "0.1.0"
    app_env: Literal["development", "test", "local-demo", "customer-template", "production"] = (
        "development"
    )
    app_mode: Literal["demo", "production"] = "production"
    service_role: Literal[
        "api",
        "worker",
        "assistant_worker",
        "ingestion_worker",
        "file_worker",
        "scheduler",
        "mcp",
        "migration",
        "bootstrap",
        "seed",
    ] = "api"
    debug: bool = False
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://executive_ai:executive_ai@localhost:5432/executive_ai"
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=20, ge=0, le=100)
    source_database_url: SecretStr | None = None
    source_writer_database_url: SecretStr | None = None
    source_schema: str = "executive_source_v3"
    source_schema_version: str = "3.0"
    source_connection_mode: Literal["internal", "external"] = "external"
    source_query_page_size: int = Field(default=1000, ge=100, le=10_000)

    capability_hmac_key: SecretStr = SecretStr("development-only-capability-key-change-me")
    capability_token_ttl_seconds: int = Field(default=90, ge=15, le=600)
    hermes_timeout_seconds: float = Field(default=120, ge=5, le=600)
    integration_encryption_key: SecretStr = SecretStr("")
    integration_encryption_key_version: str = "v1"
    integration_encryption_key_ring: SecretStr = SecretStr("")
    integration_encryption_key_ring_file: Path | None = None
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_dimension: int = Field(default=512, ge=64, le=4096)
    embedding_cache_dir: Path = Path("/opt/models")

    sync_cron: str = "0 2 * * *"
    sync_timezone: str = "Asia/Shanghai"
    data_stale_after_hours: int = Field(default=30, ge=1, le=24 * 30)
    scheduler_poll_seconds: float = Field(default=15, ge=1, le=300)
    demo_reference_date: str = "2026-07-26"
    demo_dataset_version: str = "phase2-demo-v1"
    feishu_app_id: str | None = None
    feishu_app_secret: SecretStr | None = None
    feishu_runtime_secret: SecretStr | None = None
    feishu_bitable_app_token: str | None = None
    feishu_bitable_table_id: str | None = None
    feishu_source_folder_token: str | None = None
    feishu_opportunity_app_token: str | None = None
    feishu_opportunity_table_id: str | None = None
    feishu_delivery_app_token: str | None = None
    feishu_delivery_table_id: str | None = None
    feishu_collection_app_token: str | None = None
    feishu_collection_table_id: str | None = None

    session_secret: SecretStr = Field(
        default=SecretStr("development-only-change-me-32-characters"),
        validation_alias="SESSION_SECRET",
    )
    csrf_secret: SecretStr = Field(
        default=SecretStr("development-only-csrf-secret-change-me"),
        validation_alias="CSRF_SECRET",
    )
    audit_hmac_key: SecretStr = SecretStr("development-only-audit-hmac-key-change-me")
    audit_hmac_key_version: str = "v1"
    audit_hmac_legacy_key_version: str = "v1"
    audit_hmac_key_ring: SecretStr = SecretStr("")
    audit_hmac_key_ring_file: Path | None = None
    file_encryption_key: SecretStr = SecretStr("")
    file_encryption_key_version: str = "v1"
    file_encryption_key_ring: SecretStr = SecretStr("")
    file_encryption_key_ring_file: Path | None = None
    file_storage_root: Path = Field(
        default=Path("./runtime/files"),
        validation_alias=AliasChoices("FILE_STORAGE_ROOT", "STORAGE_ROOT"),
    )
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, ge=1)

    # 启用的 skill 文件释放目录（API 与 worker 共享同一文件系统路径）
    # 该目录即 HERMES_HOME，skill 文件释放到 <HERMES_HOME>/skills/<slug>/
    # 优先读 HERMES_HOME 环境变量（与 hermes-agent 对齐），其次 SKILLS_ACTIVE_DIR
    skills_active_dir: Path = Field(
        default=Path("./runtime/skills_active"),
        validation_alias=AliasChoices("HERMES_HOME", "SKILLS_ACTIVE_DIR"),
    )

    session_cookie_name: str = "exec_session"
    csrf_cookie_name: str = "exec_csrf"
    session_cookie_secure: bool = Field(
        default=False,
        validation_alias=AliasChoices("SESSION_COOKIE_SECURE", "COOKIE_SECURE"),
    )
    session_cookie_samesite: Literal["lax", "strict", "none"] = Field(
        default="lax",
        validation_alias=AliasChoices("SESSION_COOKIE_SAMESITE", "COOKIE_SAMESITE"),
    )
    session_ttl_seconds: int = Field(default=8 * 60 * 60, ge=300, le=30 * 24 * 60 * 60)
    session_idle_seconds: int = Field(default=2 * 60 * 60, ge=300)
    password_min_length: int = Field(default=12, ge=10, le=128)
    login_max_attempts: int = Field(default=8, ge=1, le=100)
    login_window_seconds: int = Field(default=15 * 60, ge=60)

    # ── 邮件拉取 / 站内通知 ────────────────────────────────────────────────
    # 邮件账户定时同步 cron（默认每天 06:00）
    # daily_digest_cron 默认 08:00，email.sync 提前 2 小时跑，确保
    # daily_digest 生成摘要时当天邮件已落库。
    email_sync_cron: str = Field(
        default="0 6 * * *", validation_alias="EMAIL_SYNC_CRON"
    )
    # 每次 IMAP 拉取的批量上限
    email_sync_batch_size: int = Field(
        default=50, ge=1, le=500, validation_alias="EMAIL_SYNC_BATCH_SIZE"
    )
    # 每日邮件摘要生成 cron（默认每天 08:00）
    daily_digest_cron: str = Field(
        default="0 8 * * *", validation_alias="DAILY_DIGEST_CRON"
    )
    daily_digest_timezone: str = Field(
        default="Asia/Shanghai", validation_alias="DAILY_DIGEST_TZ"
    )
    # 通知保留天数（已读 + 过期自动清理）
    notification_retention_days: int = Field(
        default=30, ge=1, le=365, validation_alias="NOTIFICATION_RETENTION_DAYS"
    )

    # ── 实体向量索引（MCP semantic_search） ───────────────
    # Anspire 网关 embedding 接口配置；API key 从 ModelProviderConfig 解密获取
    # （与 chat completion 复用同一组凭证），此处只配置 endpoint / model / batch。
    anspire_embedding_endpoint: str = Field(
        default="https://open-gateway.anspire.cn/v6/embeddings",
        validation_alias="ANSPIRE_EMBEDDING_ENDPOINT",
    )
    anspire_embedding_model: str = Field(
        default="text-embedding-v4",
        validation_alias="ANSPIRE_EMBEDDING_MODEL",
    )
    # 单次批量调用 embedding API 的最大条数；Anspire 网关 text-embedding-v4
    # 限制批量不超过 10 条，超过会返回 400 InvalidParameter。
    embedding_batch_size: int = Field(
        default=10, ge=1, le=10, validation_alias="EMBEDDING_BATCH_SIZE"
    )
    # embedding API 调用超时（秒）。
    embedding_request_timeout: float = Field(
        default=30.0, ge=5.0, le=120.0, validation_alias="EMBEDDING_REQUEST_TIMEOUT"
    )
    # 单条 content_text 最大字符数（超过截断，避免 embedding API 报错）。
    embedding_max_content_chars: int = Field(
        default=1500, ge=100, le=8000, validation_alias="EMBEDDING_MAX_CONTENT_CHARS"
    )
    # semantic_search 默认返回数量。
    semantic_search_top_k: int = Field(
        default=10, ge=1, le=100, validation_alias="SEMANTIC_SEARCH_TOP_K"
    )
    # 单表索引构建并发锁超时（秒）；超过此时间未更新 locked_at 视为僵尸。
    embedding_lock_timeout_seconds: int = Field(
        default=1800, ge=60, le=7200, validation_alias="EMBEDDING_LOCK_TIMEOUT"
    )

    allowed_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    trusted_hosts: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1", "testserver"]
    seed_demo_data: bool = False
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: SecretStr | None = None
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_reload: bool = False
    api_workers: int = Field(default=1, ge=1, le=16)
    worker_poll_seconds: float = Field(default=2.0, ge=0.1, le=60)
    worker_lease_seconds: int = Field(default=60, ge=5, le=3600)
    worker_heartbeat_seconds: int = Field(default=15, ge=1, le=1800)
    worker_job_max_attempts: int = Field(default=3, ge=1, le=20)
    worker_retry_base_seconds: float = Field(default=2.0, ge=0.1, le=3600)
    worker_retry_max_seconds: float = Field(default=60.0, ge=0.1, le=86_400)
    worker_job_types: Annotated[list[str], NoDecode] = ["*"]
    # 进程内并发执行的 job 数。claim_one 拿到 job 后丢进线程池异步执行，
    # 主循环立即下一轮 claim。建议与 hermes_max_concurrent_runs 对齐，
    # 否则 worker claim 了 job 会被 runtime 侧 Semaphore 挡住。
    worker_concurrency: int = Field(default=2, ge=1, le=32)

    # ── Hermes Worker（新架构）──
    worker_host: str = "0.0.0.0"
    worker_port: int = Field(default=8001, ge=1, le=65535)
    worker_base_url: str = "http://127.0.0.1:8001"  # API 侧连接 worker 的地址
    hermes_api_key: SecretStr | None = None  # worker 鉴权用
    hermes_max_concurrent_runs: int = Field(default=2, ge=1, le=32)
    hermes_max_iterations: int = Field(default=10, ge=1, le=50)
    hermes_max_tokens: int | None = None
    # 同一会话多轮对话时，传给 hermes 的历史消息最大条数（不含本轮 user）。
    # hermes ``run_conversation`` 会把它作为 messages 起点 + 本轮 user 一起发给 LLM。
    # 调大可让 LLM 看到更长上下文，但会增加 token 消耗；调小则可能丢失早期信息。
    # 默认 5 条（约 2-3 轮历史对话），可通过环境变量 CONVERSATION_HISTORY_MAX_MESSAGES 配置。
    conversation_history_max_messages: int = Field(
        default=5, ge=0, le=200, validation_alias="CONVERSATION_HISTORY_MAX_MESSAGES"
    )

    @field_validator("hermes_max_tokens", mode="before")
    @classmethod
    def _empty_str_to_none(cls, v):
        if v in ("", None):
            return None
        return v

    # run_agent 包安装路径（AIAgent 来源）
    # 无需配置，import run_agent 即可

    @field_validator("allowed_origins", "trusted_hosts", "worker_job_types", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator(
        "audit_hmac_key_version",
        "audit_hmac_legacy_key_version",
        "file_encryption_key_version",
        "integration_encryption_key_version",
    )
    @classmethod
    def validate_key_version(cls, value: str) -> str:
        if not KEY_VERSION_PATTERN.fullmatch(value):
            raise ValueError(
                "key version must use 1-64 letters, numbers, dot, underscore or dash characters"
            )
        return value

    @model_validator(mode="after")
    def validate_environment_guards(self) -> Settings:
        protected = (
            self.app_env in {"customer-template", "production"} or self.app_mode == "production"
        )
        if protected and self.seed_demo_data:
            raise ValueError(
                "Demo seed is forbidden in production and customer-template environments"
            )
        if protected and self.debug:
            raise ValueError("Debug mode is forbidden in protected environments")
        if protected and self.source_connection_mode == "external" and self.source_database_url:
            source_url = self.source_database_url.get_secret_value()
            ssl_mode = parse_qs(urlsplit(source_url).query).get("sslmode", [])
            if ssl_mode != ["verify-full"]:
                raise ValueError("External SOURCE_DATABASE_URL must use sslmode=verify-full")
        if self.worker_heartbeat_seconds >= self.worker_lease_seconds:
            raise ValueError("WORKER_HEARTBEAT_SECONDS must be shorter than WORKER_LEASE_SECONDS")
        if self.worker_retry_base_seconds > self.worker_retry_max_seconds:
            raise ValueError("WORKER_RETRY_BASE_SECONDS must not exceed WORKER_RETRY_MAX_SECONDS")
        if (
            self.service_role == "api"
            and self.session_cookie_samesite == "none"
            and not self.session_cookie_secure
        ):
            raise ValueError("SameSite=None requires a secure session cookie")
        if protected:
            insecure_values = {
                "development-only-change-me-32-characters",
                "development-only-csrf-secret-change-me",
                "development-only-audit-hmac-key-change-me",
                "change-me",
                "password",
                "demo",
            }
            if self.service_role == "api":
                if (
                    len(self.session_secret.get_secret_value()) < 32
                    or self.session_secret.get_secret_value().lower() in insecure_values
                ):
                    raise ValueError(
                        "SESSION_SECRET must be a non-default value of at least 32 characters"
                    )
                if (
                    len(self.csrf_secret.get_secret_value()) < 32
                    or self.csrf_secret.get_secret_value().lower() in insecure_values
                ):
                    raise ValueError(
                        "CSRF_SECRET must be a non-default value of at least 32 characters"
                    )
            if self.bootstrap_admin_password:
                password = self.bootstrap_admin_password.get_secret_value().lower()
                if password in insecure_values or "demo" in password:
                    raise ValueError("Demo or unsafe bootstrap passwords are forbidden")
            if self.service_role in {
                "api",
                "worker",
                "assistant_worker",
                "ingestion_worker",
                "file_worker",
                "bootstrap",
                "seed",
            }:
                if (
                    len(self.audit_hmac_key.get_secret_value()) < 32
                    or self.audit_hmac_key.get_secret_value().lower() in insecure_values
                ):
                    raise ValueError(
                        "AUDIT_HMAC_KEY must be a non-default value of at least 32 characters"
                    )
                try:
                    self.audit_hmac_keys()
                except RuntimeError as exc:
                    raise ValueError(str(exc)) from exc
            if self.service_role == "api":
                if (
                    len(
                        {
                            self.session_secret.get_secret_value(),
                            self.csrf_secret.get_secret_value(),
                            self.audit_hmac_key.get_secret_value(),
                        }
                    )
                    != 3
                ):
                    raise ValueError(
                        "SESSION_SECRET, CSRF_SECRET and AUDIT_HMAC_KEY must be distinct"
                    )
            if self.service_role in {"api", "worker", "file_worker"}:
                try:
                    self.file_encryption_keys()
                except RuntimeError as exc:
                    raise ValueError(str(exc)) from exc
            if self.service_role in {"worker", "assistant_worker", "mcp"}:
                capability_key = self.capability_hmac_key.get_secret_value()
                if len(capability_key) < 32 or capability_key.lower() in insecure_values:
                    raise ValueError(
                        "CAPABILITY_HMAC_KEY must be a non-default value of at least 32 characters"
                    )
        return self

    def _load_key_ring(
        self,
        inline: SecretStr,
        file_path: Path | None,
        variable_name: str,
    ) -> dict[str, str]:
        raw_inline = inline.get_secret_value().strip()
        if raw_inline and file_path is not None:
            raise RuntimeError(
                f"{variable_name} and {variable_name}_FILE cannot both be configured"
            )
        if file_path is not None:
            path = file_path.expanduser().resolve()
            if not path.is_file():
                raise RuntimeError(f"{variable_name}_FILE must reference a readable regular file")
            if stat.S_IMODE(path.stat().st_mode) & 0o077:
                # 在 POSIX 平台上文件必须是 mode 0o600。Windows 不暴露 group/other
                # 权限位，跳过此检查；测试用临时文件会在 Windows 上由 ACL 隔离。
                if sys.platform != "win32":
                    raise RuntimeError(
                        f"{variable_name}_FILE must not be readable by group or others"
                    )
            raw = path.read_text(encoding="utf-8").strip()
        else:
            raw = raw_inline
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{variable_name} must be a JSON object") from exc
        if not isinstance(parsed, dict) or len(parsed) > 32:
            raise RuntimeError(f"{variable_name} must be a JSON object with at most 32 keys")
        ring: dict[str, str] = {}
        for version, key in parsed.items():
            if not isinstance(version, str) or not KEY_VERSION_PATTERN.fullmatch(version):
                raise RuntimeError(f"{variable_name} contains an invalid key version")
            if not isinstance(key, str) or not key:
                raise RuntimeError(f"{variable_name} contains an invalid key value")
            ring[version] = key
        return ring

    def decoded_file_encryption_key(self) -> bytes:
        raw = self.file_encryption_key.get_secret_value()
        if not raw:
            if self.app_env == "test":
                return b"T" * 32
            raise RuntimeError("FILE_ENCRYPTION_KEY is required")
        try:
            value = base64.urlsafe_b64decode(raw.encode("ascii"))
        except (ValueError, UnicodeError) as exc:
            raise RuntimeError("FILE_ENCRYPTION_KEY must be URL-safe base64") from exc
        if len(value) != 32:
            raise RuntimeError("FILE_ENCRYPTION_KEY must decode to exactly 32 bytes")
        return value

    def decoded_integration_encryption_key(self) -> bytes:
        raw = self.integration_encryption_key.get_secret_value()
        if not raw:
            if self.app_env == "test":
                return b"I" * 32
            raise RuntimeError("INTEGRATION_ENCRYPTION_KEY is required")
        try:
            value = base64.urlsafe_b64decode(raw.encode("ascii"))
        except (ValueError, UnicodeError) as exc:
            raise RuntimeError("INTEGRATION_ENCRYPTION_KEY must be URL-safe base64") from exc
        if len(value) != 32:
            raise RuntimeError("INTEGRATION_ENCRYPTION_KEY must decode to exactly 32 bytes")
        return value

    def file_encryption_keys(self) -> dict[str, bytes]:
        encoded_ring = self._load_key_ring(
            self.file_encryption_key_ring,
            self.file_encryption_key_ring_file,
            "FILE_ENCRYPTION_KEY_RING",
        )
        decoded: dict[str, bytes] = {}
        for version, encoded in encoded_ring.items():
            try:
                value = base64.urlsafe_b64decode(encoded.encode("ascii"))
            except (ValueError, UnicodeError) as exc:
                raise RuntimeError(
                    f"FILE_ENCRYPTION_KEY_RING key {version!r} must be URL-safe base64"
                ) from exc
            if len(value) != 32:
                raise RuntimeError(
                    f"FILE_ENCRYPTION_KEY_RING key {version!r} must decode to exactly 32 bytes"
                )
            decoded[version] = value
        current = self.decoded_file_encryption_key()
        existing = decoded.get(self.file_encryption_key_version)
        if existing is not None and existing != current:
            raise RuntimeError("current file key conflicts with the same version in the key ring")
        decoded[self.file_encryption_key_version] = current
        return decoded

    def integration_encryption_keys(self) -> dict[str, bytes]:
        encoded_ring = self._load_key_ring(
            self.integration_encryption_key_ring,
            self.integration_encryption_key_ring_file,
            "INTEGRATION_ENCRYPTION_KEY_RING",
        )
        decoded: dict[str, bytes] = {}
        for version, encoded in encoded_ring.items():
            try:
                value = base64.urlsafe_b64decode(encoded.encode("ascii"))
            except (ValueError, UnicodeError) as exc:
                raise RuntimeError(
                    f"INTEGRATION_ENCRYPTION_KEY_RING key {version!r} must be URL-safe base64"
                ) from exc
            if len(value) != 32:
                raise RuntimeError(
                    f"INTEGRATION_ENCRYPTION_KEY_RING key {version!r} "
                    "must decode to exactly 32 bytes"
                )
            decoded[version] = value
        current = self.decoded_integration_encryption_key()
        existing = decoded.get(self.integration_encryption_key_version)
        if existing is not None and existing != current:
            raise RuntimeError(
                "current integration key conflicts with the same version in the key ring"
            )
        decoded[self.integration_encryption_key_version] = current
        return decoded

    def audit_hmac_keys(self) -> dict[str, str]:
        ring = self._load_key_ring(
            self.audit_hmac_key_ring,
            self.audit_hmac_key_ring_file,
            "AUDIT_HMAC_KEY_RING",
        )
        for version, key in ring.items():
            if len(key) < 32:
                raise RuntimeError(
                    f"AUDIT_HMAC_KEY_RING key {version!r} is shorter than 32 characters"
                )
        current = self.audit_hmac_key.get_secret_value()
        existing = ring.get(self.audit_hmac_key_version)
        if existing is not None and existing != current:
            raise RuntimeError("current audit key conflicts with the same version in the key ring")
        ring[self.audit_hmac_key_version] = current
        if self.audit_hmac_legacy_key_version not in ring:
            raise RuntimeError(
                "AUDIT_HMAC_LEGACY_KEY_VERSION is missing from the configured audit key ring"
            )
        return ring


@lru_cache
def get_settings() -> Settings:
    return Settings()
