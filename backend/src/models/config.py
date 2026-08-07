"""配置、模型授权、MCP 工具与 Harness 版本模型."""

from __future__ import annotations

from .base import *  # noqa: F401,F403  Base / JSONType / new_uuid / mixins / sqlalchemy symbols


class AppConfig(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "app_configs"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "key", name="uq_app_config_enterprise_key"),
    )

    enterprise_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    is_secret_reference: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SecretReference(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "secret_references"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "key", name="uq_secret_ref_enterprise_key"),
    )

    enterprise_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    reference: Mapped[str] = mapped_column(String(500), nullable=False)


class ModelProviderConfig(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "model_provider_configs"
    __table_args__ = (
        UniqueConstraint("enterprise_id", name="uq_model_provider_enterprise"),
        Index("ix_model_provider_enterprise_enabled", "enterprise_id", "is_enabled"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), default="anspire", nullable=False)
    endpoint_url: Mapped[str] = mapped_column(String(300), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key_ciphertext: Mapped[str | None] = mapped_column(Text)
    api_key_nonce: Mapped[str | None] = mapped_column(String(64))
    api_key_hint: Mapped[str | None] = mapped_column(String(16))
    encryption_key_version: Mapped[str] = mapped_column(String(64), default="v1", nullable=False)
    credential_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_status: Mapped[str | None] = mapped_column(String(32))
    last_test_latency_ms: Mapped[int | None] = mapped_column(Integer)
    last_test_error: Mapped[str | None] = mapped_column(Text)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class EnterpriseModelAuthorization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "enterprise_model_authorizations"
    __table_args__ = (
        UniqueConstraint(
            "enterprise_id", "model_id", name="uq_enterprise_model_authorization"
        ),
        Index(
            "ix_enterprise_model_authorization_state",
            "enterprise_id",
            "is_authorized",
            "is_default",
        ),
        Index(
            "uq_enterprise_default_model",
            "enterprise_id",
            unique=True,
            postgresql_where=text("is_default"),
            sqlite_where=text("is_default = 1"),
        ),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    test_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    tested_credential_version: Mapped[int | None] = mapped_column(Integer)
    is_authorized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_latency_ms: Mapped[int | None] = mapped_column(Integer)
    last_test_error: Mapped[str | None] = mapped_column(Text)
    authorized_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HarnessConfigVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "harness_config_versions"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "version", name="uq_harness_enterprise_version"),
        Index("ix_harness_enterprise_active", "enterprise_id", "is_active"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), default="3.0", nullable=False)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("harness_config_versions.id", ondelete="SET NULL")
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class McpSchemaRegistry(UUIDMixin, TimestampMixin, Base):
    """企业级数据表 schema 注册 — MCP v2 通用 3 步模式。

    替代旧 ``McpToolConfig`` / ``McpToolDefinition`` 的 case-by-case 方式。
    管理端控制哪些表对 Agent 可见，Worker 侧的 MCP server 从本表读取
    schema 元数据供 Agent 自动发现和查询。
    """

    __tablename__ = "mcp_schema_registry"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "table_name",
                         name="uq_mcp_schema_enterprise_table"),
        Index("ix_mcp_schema_enterprise_enabled", "enterprise_id", "is_enabled"),
        Index("ix_mcp_schema_enterprise_category", "enterprise_id", "category"),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    table_name: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    column_schema: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONType, default=list, nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_indexed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_rows: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    query_timeout_seconds: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    sample_rows: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONType)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OpportunityExperienceWeightPolicy(UUIDMixin, TimestampMixin, Base):
    """Versioned, auditable experience weights used for pipeline forecasting.

    These values are an operating convention rather than a claim about the
    statistical probability of winning an opportunity.  Only one policy may
    be active for an enterprise at a time.
    """

    __tablename__ = "opportunity_experience_weight_policies"
    __table_args__ = (
        UniqueConstraint(
            "enterprise_id",
            "version",
            name="uq_opportunity_weight_policy_enterprise_version",
        ),
        Index(
            "ix_opportunity_weight_policy_enterprise_active",
            "enterprise_id",
            "is_active",
        ),
        Index(
            "uq_opportunity_weight_policy_one_active",
            "enterprise_id",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active = 1"),
        ),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    weights_json: Mapped[dict[str, float]] = mapped_column(
        JSONType,
        default=lambda: {"high": 0.20, "medium": 0.10, "low": 0.05},
        nullable=False,
    )
    observation_windows_json: Mapped[list[int]] = mapped_column(
        JSONType, default=lambda: [30, 60, 90], nullable=False
    )
    observation_window_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(Text)
