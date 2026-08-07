"""MCP stdio server：数据 schema 发现 + SQL 执行。

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

提供 3 个工具：
    1. discover_schema  - 列出可用表及简介
    2. query_schema     - 获取指定表的列结构
    3. execute_query    - 执行只读 SQL（安全校验）
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

import asyncpg

logger = logging.getLogger(__name__)

# ── 数据库连接池 ──────────────────────────────────────────

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        dsn = os.environ.get("DATABASE_URL", "")
        if not dsn:
            raise RuntimeError("DATABASE_URL environment variable is not set")
        _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    return _pool


# ── 工具 1：discover_schema ────────────────────────────────

async def handle_discover_schema(_params: dict) -> dict:
    """列出可用表及简介。"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT table_name, display_name, description, category,
                   is_enabled, max_rows, query_timeout_seconds
            FROM mcp_schema_registry
            WHERE is_enabled = true
            ORDER BY category, display_name
        """)
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

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM mcp_schema_registry WHERE table_name = $1 AND is_enabled = true",
            table_name,
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

    pool = await get_pool()
    async with pool.acquire() as conn:
        allowed = await conn.fetch(
            "SELECT table_name FROM mcp_schema_registry WHERE is_enabled = true"
        )
        allowed_names = {r["table_name"].lower() for r in allowed}

    for name in referenced_tables:
        if name not in allowed_names:
            return {"error": f"Table '{name}' is not in the allowed list"}

    # 5. 执行
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
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
}

HANDLERS = {
    "discover_schema": handle_discover_schema,
    "query_schema": handle_query_schema,
    "execute_query": handle_execute_query,
}


async def main() -> None:
    """MCP stdio 主循环：从 stdin 读取 JSON-RPC，向 stdout 写入响应。"""
    loop = asyncio.get_running_loop()

    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    writer_transport, writer_protocol = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout
    )
    writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, loop)

    buffer = b""
    while True:
        chunk = await reader.read(65536)
        if not chunk:
            break
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            line = line.strip()
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

            writer.write((json.dumps(response, ensure_ascii=False) + "\n").encode())
            await writer.drain()


if __name__ == "__main__":
    asyncio.run(main())
