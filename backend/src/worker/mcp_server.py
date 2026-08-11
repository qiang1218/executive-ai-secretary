"""MCP stdio server：数据 schema 发现 + SQL 执行 + 语义检索。

通过 stdin/stdout 与 AIAgent 的 MCP 客户端通信，
协议为 JSON-RPC 2.0 (MCP 2024-11-05)。

注册给 AIAgent 的方式：
    register_mcp_servers({
        "executive-data": {
            "command": sys.executable,
            "args": ["-m", "worker.mcp_server"],
            "env": {"DATABASE_URL": os.environ["DATABASE_URL"]},
        }
    })

提供 4 个工具：
    1. discover_schema   - 列出可用表及简介
    2. query_schema      - 获取指定表的列结构
    3. execute_query     - 执行只读 SQL（安全校验）
    4. semantic_search   - 按语义模糊检索业务实体（pgvector + Anspire embedding）
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time

import asyncpg
import httpx

logger = logging.getLogger(__name__)

# ── 数据库连接池 ──────────────────────────────────────────

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        dsn = os.environ.get("DATABASE_URL", "")
        if not dsn:
            raise RuntimeError("DATABASE_URL environment variable is not set")
        # asyncpg 只接受 postgresql:// / postgres://，去掉 SQLAlchemy 的驱动后缀
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
        _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    return _pool


def _get_enterprise_id() -> str:
    """从环境变量读取企业 ID（由 API 侧通过 mcp_servers.env 注入）。

    多企业隔离的关键：MCP server 子进程通过此 env 限定数据范围，
    避免跨企业串库。缺失时返回空串，SQL 会匹配不到任何行（安全失败）。
    """
    return os.environ.get("ENTERPRISE_ID", "").strip()


# ── 工具 1：discover_schema ────────────────────────────────

async def handle_discover_schema(_params: dict) -> dict:
    """列出可用表及简介。"""
    enterprise_id = _get_enterprise_id()
    if not enterprise_id:
        return {"tables": [], "error": "ENTERPRISE_ID not configured"}

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT table_name, display_name, description, category,
                   is_enabled, max_rows, query_timeout_seconds
            FROM mcp_schema_registry
            WHERE is_enabled = true AND enterprise_id = $1
            ORDER BY category, display_name
            """,
            enterprise_id,
        )
    return {
        "tables": [
            {
                "table_name": r["table_name"],
                "display_name": r["display_name"],
                "description": r["description"],
                "category": r["category"],
                "max_rows": r["max_rows"],
                "query_timeout_seconds": r["query_timeout_seconds"],
            }
            for r in rows
        ]
    }


# ── 工具 2：query_schema ───────────────────────────────────

async def handle_query_schema(params: dict) -> dict:
    """获取指定表的列结构。"""
    table_name = (params.get("table_name") or "").strip()
    if not table_name:
        return {"error": "table_name is required"}

    enterprise_id = _get_enterprise_id()
    if not enterprise_id:
        return {"error": "ENTERPRISE_ID not configured"}

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM mcp_schema_registry "
            "WHERE table_name = $1 AND is_enabled = true AND enterprise_id = $2",
            table_name,
            enterprise_id,
        )
        if row is None:
            return {"error": f"Table '{table_name}' not found or not enabled"}

        columns = json.loads(row["column_schema"]) if row["column_schema"] else []
        sample = json.loads(json.dumps(row["sample_rows"], default=str)) if row["sample_rows"] else None

    return {
        "table_name": row["table_name"],
        "display_name": row["display_name"],
        "description": row["description"],
        "columns": columns,
        "sample_rows": sample,
    }


# ── 工具 3：execute_query ──────────────────────────────────

async def handle_execute_query(params: dict) -> dict:
    """安全执行 SELECT 查询。

    校验规则：
    1. 仅允许 SELECT
    2. 表名必须在 mcp_schema_registry 白名单中
    3. 禁止危险函数（pg_sleep 等）
    4. 超时 10s
    """
    sql = (params.get("sql") or "").strip()
    if not sql:
        return {"error": "SQL is empty"}

    # 1. 仅允许 SELECT（简单规则校验，不依赖 sqlglot）
    sql_upper = sql.upper().strip()
    if not sql_upper.startswith("SELECT"):
        return {"error": "Only SELECT statements are allowed"}

    # 2. 危险关键字检测
    dangerous_keywords = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "TRUNCATE", "GRANT", "REVOKE", "COPY", "EXECUTE",
    ]
    for kw in dangerous_keywords:
        if kw in sql_upper.split():
            return {"error": f"Operation '{kw}' is not allowed"}

    # 3. 危险函数检测
    dangerous_funcs = [
        "pg_sleep", "pg_read_file", "pg_read_binary_file",
        "pg_ls_dir", "lo_import", "lo_export", "pg_terminate_backend",
        "pg_cancel_backend",
    ]
    sql_lower = sql.lower()
    for func in dangerous_funcs:
        if func in sql_lower:
            return {"error": f"Function '{func}' is not allowed"}

    # 4. 表名白名单校验（从查询中提取表名）
    import re
    table_pattern = re.compile(
        r'(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        re.IGNORECASE,
    )
    referenced_tables = [m.group(1).lower() for m in table_pattern.finditer(sql)]
    if not referenced_tables:
        return {"error": "No table references found in SQL"}

    enterprise_id = _get_enterprise_id()
    if not enterprise_id:
        return {"error": "ENTERPRISE_ID not configured"}

    pool = await get_pool()
    async with pool.acquire() as conn:
        allowed = await conn.fetch(
            "SELECT table_name FROM mcp_schema_registry "
            "WHERE is_enabled = true AND enterprise_id = $1",
            enterprise_id,
        )
        allowed_names = {r["table_name"].lower() for r in allowed}

    for name in referenced_tables:
        if name not in allowed_names:
            return {"error": f"Table '{name}' is not in the allowed list"}

    # 5. 执行（ODS 表在 executive_source_v3 schema，设置 search_path）
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("SET search_path TO executive_source_v3, public")
            rows = await conn.fetch(sql, timeout=10)
    except asyncpg.exceptions.QueryCanceledError:
        return {"error": "Query timed out (10s limit)"}
    except Exception as e:
        return {"error": f"Query execution error: {e}"}

    columns = list(rows[0].keys()) if rows else []
    return {
        "columns": columns,
        "rows": [dict(r) for r in rows],
        "row_count": len(rows),
    }


# ── 工具 4：semantic_search ────────────────────────────────

# Anspire embedding 接口配置（与 API 进程共用同一组凭证）。
# API key 在子进程启动时从 ModelProviderConfig 解密获取并缓存。
_EMBEDDING_ENDPOINT = os.environ.get(
    "ANSPIRE_EMBEDDING_ENDPOINT",
    "https://open-gateway.anspire.cn/v6/embeddings",
)
_EMBEDDING_MODEL = os.environ.get("ANSPIRE_EMBEDDING_MODEL", "text-embedding-v4")
_EMBEDDING_TIMEOUT = float(os.environ.get("EMBEDDING_REQUEST_TIMEOUT", "30"))
_EMBEDDING_MAX_CHARS = int(os.environ.get("EMBEDDING_MAX_CONTENT_CHARS", "1500"))

# 进程内缓存：避免每次检索都查 model_provider_configs
_cached_embedding_api_key: str | None = None
_cached_embedding_api_key_at: float = 0.0
_EMBEDDING_KEY_CACHE_TTL = 300.0  # 5 分钟


async def _get_embedding_api_key() -> str:
    """从 model_provider_configs 解密出 Anspire API key。

    复用 ``services.anspire.decrypt_anspire_api_key``；MCP server 是独立
    子进程，需要从 DB 读 ModelProviderConfig 行后调用解密函数。
    """
    global _cached_embedding_api_key, _cached_embedding_api_key_at
    now = time.monotonic()
    if (
        _cached_embedding_api_key is not None
        and now - _cached_embedding_api_key_at < _EMBEDDING_KEY_CACHE_TTL
    ):
        return _cached_embedding_api_key

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, enterprise_id, api_key_ciphertext, api_key_nonce,
                   encryption_key_version
            FROM model_provider_configs
            WHERE provider = 'anspire'
              AND endpoint_url = 'https://open-gateway.anspire.ai/v6'
              AND is_enabled = true
              AND last_test_status = 'success'
            LIMIT 1
            """
        )
    if row is None or not row["api_key_ciphertext"] or not row["api_key_nonce"]:
        raise RuntimeError(
            "Anspire 模型供应商未配置或未通过测试，无法调用 embedding 接口"
        )

    # 复用 services.anspire 的解密逻辑（构造 ModelProviderConfig 对象）
    import uuid as _uuid
    from configs.settings import get_settings
    from models.config import ModelProviderConfig
    from services.anspire import decrypt_anspire_api_key

    settings = get_settings()
    config = ModelProviderConfig(
        id=_uuid.UUID(str(row["id"])),
        enterprise_id=_uuid.UUID(str(row["enterprise_id"])),
        api_key_ciphertext=row["api_key_ciphertext"],
        api_key_nonce=row["api_key_nonce"],
        encryption_key_version=row["encryption_key_version"],
    )
    api_key = decrypt_anspire_api_key(config, settings)

    _cached_embedding_api_key = api_key
    _cached_embedding_api_key_at = now
    return api_key


async def _embed_query_text(text: str) -> list[float]:
    """调 Anspire /v6/embeddings 接口把 query 转 vector。"""
    api_key = await _get_embedding_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": _EMBEDDING_MODEL, "input": [text]}
    async with httpx.AsyncClient(timeout=_EMBEDDING_TIMEOUT) as client:
        resp = await client.post(_EMBEDDING_ENDPOINT, headers=headers, json=payload)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Embedding 接口返回 HTTP {resp.status_code}: {resp.text[:300]}"
        )
    body = resp.json()
    data = body.get("data") or []
    if not data:
        raise RuntimeError("Embedding 接口返回空 data")
    return list(map(float, data[0]["embedding"]))


async def handle_semantic_search(params: dict) -> dict:
    """按语义模糊检索业务实体。

    流程：
    1. 调 Anspire embedding 接口把 ``query`` 转 vector
    2. 在 ``entity_embeddings`` 表上做 HNSW 最近邻检索（cosine 距离）
    3. 应用 ``source_table`` / ``min_score`` / ``metadata`` 过滤
    4. 返回 ``[{source_table, source_id, snippet, metadata, score}]``

    本工具是辅助检索，不能替代 ``execute_query``。Agent 拿到 ``source_id``
    后应再用 ``execute_query`` 查询完整字段。
    """
    query_text = (params.get("query") or "").strip()
    if not query_text:
        return {"error": "query is required"}

    enterprise_id = _get_enterprise_id()
    if not enterprise_id:
        return {"error": "ENTERPRISE_ID not configured"}

    source_table = (params.get("source_table") or "").strip()
    min_score = float(params.get("min_score") or 0.0)
    top_k = int(params.get("top_k") or 10)
    if top_k < 1:
        top_k = 10
    if top_k > 100:
        top_k = 100
    filters = params.get("filters") or {}
    if not isinstance(filters, dict):
        return {"error": "filters must be an object"}

    # 1. 调 embedding API
    try:
        query_embedding = await _embed_query_text(query_text)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"embedding_failed: {exc}"}

    # 2. pgvector 最近邻查询（带过滤）
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 构建 SQL：pgvector 的 <=> 操作符返回 cosine 距离，score = 1 - distance
        # asyncpg 不支持直接传 list[float] 给 vector 类型，需转成 pgvector 字符串
        embedding_str = "[" + ",".join(f"{x:.8f}" for x in query_embedding) + "]"
        sql = (
            "SELECT source_table, source_id, content_text, metadata_json, "
            "       1 - (embedding <=> $1::vector) AS score "
            "FROM entity_embeddings "
            "WHERE enterprise_id = $2 "
            "  AND index_status = 'indexed' "
            "  AND embedding IS NOT NULL"
        )
        sql_params: list = [embedding_str, enterprise_id]
        param_idx = 3

        if source_table:
            sql += f" AND source_table = ${param_idx}"
            sql_params.append(source_table)
            param_idx += 1

        # metadata_json 过滤：metadata_json->>$key = $value
        for key, value in filters.items():
            if not isinstance(key, str) or not key.replace("_", "").isalnum():
                continue  # 防注入：字段名严格校验
            sql += f" AND metadata_json->>${param_idx} = ${param_idx + 1}"
            sql_params.append(key)
            sql_params.append(str(value))
            param_idx += 2

        sql += f" ORDER BY embedding <=> $1::vector LIMIT ${param_idx}"
        sql_params.append(top_k)

        try:
            rows = await conn.fetch(sql, *sql_params)
        except Exception as exc:  # noqa: BLE001
            return {"error": f"vector_query_failed: {exc}"}

    # 3. 后处理：min_score 过滤 + snippet 截断
    matches = []
    for r in rows:
        score = float(r["score"]) if r["score"] is not None else 0.0
        if score < min_score:
            continue
        snippet = r["content_text"] or ""
        if len(snippet) > 200:
            snippet = snippet[:200] + "..."
        matches.append(
            {
                "source_table": r["source_table"],
                "source_id": str(r["source_id"]),
                "snippet": snippet,
                "metadata": r["metadata_json"] or {},
                "score": round(score, 4),
            }
        )

    return {
        "query": query_text,
        "matches": matches,
        "match_count": len(matches),
        "note": (
            "本工具是辅助检索；如需完整字段，请用 execute_query 工具按 "
            "source_table + source_id 查询对应业务表。"
        ),
    }


# ── MCP JSON-RPC 主循环 ────────────────────────────────────

TOOLS = {
    "discover_schema": {
        "name": "discover_schema",
        "description": (
            "列出所有可用的数据表及其用途说明。"
            "用于了解有哪些数据可以查询。在编写任何 SQL 之前必须先调用此工具。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    "query_schema": {
        "name": "query_schema",
        "description": (
            "获取指定表的列结构（列名、类型、说明、外键关系）和示例数据。"
            "在编写 SQL 查询之前必须先调用此工具了解表字段。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "表名，从 discover_schema 返回的 table_name 中选择",
                },
            },
            "required": ["table_name"],
        },
    },
    "execute_query": {
        "name": "execute_query",
        "description": (
            "执行一条只读 SQL 查询（仅 SELECT）。"
            "查询前必须先通过 discover_schema 和 query_schema 了解表结构。"
            "查询结果最多返回 100 行。"
            "建议在 WHERE 条件中使用 is_current = true 过滤当前有效数据。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "要执行的 SELECT 语句。仅允许 SELECT。",
                },
            },
            "required": ["sql"],
        },
    },
    "semantic_search": {
        "name": "semantic_search",
        "description": (
            "按语义模糊检索业务实体（商机/交付/回款）。"
            "当用户问题含'类似''相关''像''哪些'等模糊词，"
            "或精确字段过滤无法命中时使用本工具。"
            "返回 source_table + source_id + snippet + score 列表。"
            "拿到 source_id 后必须再用 execute_query 查询完整字段。"
            "注意：本工具是辅助检索，不能替代 execute_query；"
            "精确字段查询（如'列出所有金额>100万的项目'）请直接用 execute_query。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "自然语言查询，例如'与新能源相关的商机'",
                },
                "source_table": {
                    "type": "string",
                    "description": (
                        "可选：限定在某张业务表内搜索。"
                        "可选值：ods_opportunity / ods_delivery / ods_collection。"
                        "留空则跨表搜索。"
                    ),
                },
                "filters": {
                    "type": "object",
                    "description": (
                        "可选：按 metadata 字段精确过滤，增强检索精度。"
                        "key-value 形式，例如 {\"industry\": \"新能源\", "
                        "\"status_code\": \"active\"}。"
                        "可用字段取决于索引构建时配置的 metadata_fields。"
                    ),
                },
                "min_score": {
                    "type": "number",
                    "description": "可选：最低相似度阈值（0-1），默认 0。",
                },
                "top_k": {
                    "type": "integer",
                    "description": "可选：返回数量，默认 10，最大 100。",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
}

HANDLERS = {
    "discover_schema": handle_discover_schema,
    "query_schema": handle_query_schema,
    "execute_query": handle_execute_query,
    "semantic_search": handle_semantic_search,
}


async def main() -> None:
    """MCP stdio 主循环：从 stdin 读取 JSON-RPC，向 stdout 写入响应。

    使用 ``asyncio.to_thread`` 读 stdin，兼容 Windows ProactorEventLoop 和
    Linux SelectorEventLoop；避免 ``connect_read_pipe`` 在 Windows 上的句柄错误。
    """
    while True:
        # 按行读 stdin（阻塞在线程里，不阻塞事件循环）
        line_bytes = await asyncio.to_thread(sys.stdin.buffer.readline)
        if not line_bytes:
            break
        line = line_bytes.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        request_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "executive-data", "version": "2.0.0"},
                },
            }
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": list(TOOLS.values())},
            }
        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            handler = HANDLERS.get(tool_name)
            if handler:
                try:
                    result = await handler(arguments)
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result, ensure_ascii=False, default=str),
                                }
                            ]
                        },
                    }
                except Exception as e:
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32000, "message": str(e)},
                    }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                }
        elif method == "notifications/initialized":
            # 忽略初始化通知
            continue
        else:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"},
            }

        # 直接写 stdout（线程安全：单线程事件循环内，无并发写入）
        sys.stdout.buffer.write(
            (json.dumps(response, ensure_ascii=False) + "\n").encode()
        )
        sys.stdout.buffer.flush()


if __name__ == "__main__":
    asyncio.run(main())
