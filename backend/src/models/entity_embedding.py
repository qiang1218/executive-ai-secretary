"""实体向量索引 ORM。

通用向量索引表：把多张业务表（``ods_opportunity`` / ``ods_delivery`` /
``ods_collection`` …）的行拼接成 ``content_text`` 后调用 Anspire 网关生成
embedding，集中存到 ``entity_embeddings`` 表里供 MCP ``semantic_search``
工具做最近邻检索。

设计要点：
- **单表多实体**：用 ``source_table`` 列区分业务表，避免每张业务表都建一张
  向量表。HNSW 索引在百万级数据下查询仍 < 10ms。
- **增量索引**：``content_hash`` 记录 ``content_text`` 的 SHA256，重建时跳过
  未变更行，节省 embedding 调用成本。
- **维度固定**：``EMBEDDING_DIMENSION`` = 1024，与 Anspire 网关的
  ``text-embedding-v4`` 模型一致。如需更换模型必须重建索引。
- **状态字段**：``index_status`` / ``error_message`` 记录单行的索引状态，
  便于失败重试和结果展示。
- **冗余字段**：``metadata_json`` 存高频过滤字段（如 ``status`` /
  ``customer_id``），减少回业务表。
"""

from __future__ import annotations

from .base import *  # noqa: F401,F403


# Anspire 网关 text-embedding-v4 输出维度。
# 维度固定不可变更：如需切换 embedding 模型，必须 DROP 表后重建。
EMBEDDING_DIMENSION = 1024


class EntityEmbedding(UUIDMixin, TimestampMixin, Base):
    """通用实体向量索引行。

    一行 = 一条业务表行的 embedding + 冗余信息。MCP ``semantic_search``
    通过 ``ORDER BY embedding <=> :query_embedding`` 做最近邻检索。
    """

    __tablename__ = "entity_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "enterprise_id",
            "source_table",
            "source_id",
            name="uq_entity_embedding_enterprise_source",
        ),
        Index(
            "ix_entity_emb_enterprise_source",
            "enterprise_id",
            "source_table",
        ),
        Index(
            "ix_entity_emb_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 业务表名，例如 ods_opportunity / ods_delivery / ods_collection。
    # 与 mcp_schema_registry.table_name 对齐，便于按表过滤和管理。
    source_table: Mapped[str] = mapped_column(String(120), nullable=False)
    # 业务表主键值（字符串化以兼容 uuid / bigint / text 等不同 PK 类型）。
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # 拼接后的全文文本（用于生成 embedding；检索时回 snippet 给 Agent）。
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    # content_text 的 SHA256，增量重建时跳过未变更行。
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # 向量；维度固定为 EMBEDDING_DIMENSION（1024）。
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSION))
    # 冗余字段：高频过滤字段（如 status / customer_id / industry），
    # 在 mcp_schema_registry.embedding_config_json.metadata_fields 中配置。
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONType, default=dict, nullable=False
    )
    # 单行索引状态：pending / indexed / failed / stale。
    # - pending:  新创建 / 内容变更待重新生成 embedding
    # - indexed:  embedding 已成功生成
    # - failed:   embedding 调用失败，error_message 记录原因
    # - stale:    业务表行已删除，本行待清理
    index_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    # 最近一次成功生成 embedding 的时间，便于判断是否需要重建。
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = ["EntityEmbedding", "EMBEDDING_DIMENSION"]
