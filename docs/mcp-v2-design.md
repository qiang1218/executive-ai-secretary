# MCP v2 设计文档

## 一、现有 MCP 实现总结

### 1.1 当前架构：Case-by-Case 模式

```
用户问题
  │
  ▼
Harness 编排层（plan prompt）
  │  从 planner_catalog 中选择工具
  │
  ▼
MCP 工具执行（11 个硬编码工具）
  ├─ get_overall_business()       → 硬编码 SQL，查 3 张表
  ├─ get_opportunity_funnel()     → 硬编码 SQL，按 stage 分组
  ├─ get_sales_forecast()         → 硬编码 SQL，经验权重计算
  ├─ get_customer_status()        → 硬编码 SQL，跨 4 张表关联
  ├─ get_delivery_status()        → 硬编码 SQL
  ├─ get_finance_margin()         → 硬编码 SQL
  ├─ get_collection_aging()       → 硬编码 SQL
  ├─ get_organization_performance() → 硬编码 SQL，按事业部聚合
  ├─ get_daily_changes()          → 硬编码 SQL，批次对比
  ├─ get_target_completion()      → 占位（数据未接入）
  └─ list_query_scopes()          → 权限范围查询
```

### 1.2 核心代码位置

| 文件 | 内容 |
|------|------|
| `worker_old/mcp_registry.py` | `MCP_TOOL_SPECS`（11 个工具规范定义）、`effective_catalog()`、`planner_catalog()` |
| `services/business_tools.py` | 11 个 handler 函数，每个约 50-200 行硬编码 SQL |
| `services/mcp_tool_service.py` | CRUD 管理（列表/创建组合工具/更新配置/校验就绪度） |
| `models/config.py` | `McpToolConfig`（企业配置）+ `McpToolDefinition`（组合工具定义） |
| `schemas/mcp.py` | `McpToolOut` / `McpToolUpdate` / `McpCompositeToolCreate` 等 |
| `api/routes/admin_mcp.py` | 4 个 REST 端点：GET/POST/PATCH/validate |
| `services/harness_config.py` | plan prompt 中引用 MCP 工具 |
| `worker_old/mcp_app.py` | 独立 FastAPI 子应用 `/v1/tools/call`（MCP Hub 接口） |

### 1.3 问题

1. **工具爆炸**：每个查询需求 = 一个工具 + 一段 SQL，11 个已嫌多，未来可能 50+
2. **扩展性差**：新增工具需改 `MCP_TOOL_SPECS` + `business_tools.py` + 前端 + 数据库迁移，5 个文件联动
3. **不可复用**：每个工具的 SQL 完全独立，相似查询（不同维度汇总）无法共享逻辑
4. **与 Worker 脱节**：业务工具走 Harness 编排直接执行，不走 AIAgent 的 tool calling，AIAgent 不知道这些工具存在

---

## 二、新方案：通用 MCP（3 步模式）

### 2.1 核心思路

将 MCP 从「N 个专用工具」收敛为 **3 个通用工具**：

| 工具 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `discover_schema` | 获取可用表列表 | 无（或 category 过滤） | 表名、中文名、用途说明、行数、分类 |
| `query_schema` | 获取指定表的列结构 | table_name | 列名、类型、注释、是否可过滤、外键关系、示例值 |
| `execute_query` | 执行 Agent 生成的 SQL | sql, params | 列名、数据行、行数 |

### 2.2 数据流

```
用户："华南区上月回款情况怎么样？"
  │
  ▼
Worker (AIAgent + 注册的 MCP 工具)
  │
  ├─ Step 1: Agent 调用 discover_schema()
  │    返回可用表列表：fact_finance_collection, dim_customer, organization_units, ...
  │
  ├─ Step 2: Agent 调用 query_schema("fact_finance_collection")
  │    返回列结构：receivable_amount (numeric), collected_amount (numeric),
  │    overdue_days (integer), customer_id (uuid → dim_customer), ...
  │
  ├─ Step 3: Agent 调用 query_schema("dim_customer")（如需客户名）
  │    返回列结构：display_name, industry, region, ...
  │
  ├─ Step 4: Agent 基于 schema 生成 SQL
  │    SELECT ou.name, SUM(fc.outstanding_amount) AS total_outstanding
  │    FROM fact_finance_collection fc
  │    JOIN organization_units ou ON fc.organization_unit_id = ou.id
  │    WHERE fc.overdue_days > 0
  │    GROUP BY ou.name
  │    ORDER BY total_outstanding DESC
  │
  └─ Step 5: Agent 调用 execute_query(sql)
       返回查询结果 → Agent 生成自然语言回答
```

### 2.3 安全边界

`execute_query` 需要多层防护：

| 层级 | 措施 | 说明 |
|------|------|------|
| 语法层 | SQL 解析校验 | 用 `sqlglot` 解析 AST，仅允许 SELECT |
| 表级 | 表白名单 | 只能查 `mcp_schema_registry` 中启用（is_enabled=true）的表 |
| 行级 | 强制注入 | 自动注入 `enterprise_id = $enterprise_id` 过滤条件 |
| 权限 | 组织过滤 | 自动注入 `organization_unit_id = ANY($org_ids)` |
| 数量 | 行数限制 | 默认 100 行，通过 `mcp_schema_registry.max_rows` 配置 |
| 时间 | 超时限制 | 默认 10s |
| 危险函数 | 黑名单 | 禁止 `pg_sleep`、`pg_read_file`、`lo_import` 等 |

---

## 三、架构决策：MCP Server 放在哪

### 3.1 两种方案对比

```
当前部署架构：
  ┌──────────┐    HTTP/SSE     ┌──────────┐
  │  API     │ ◄──────────────► │  Worker  │
  │  :8000   │   (hermes_client)│  :8001   │
  └──────────┘                  └──────────┘
       │                              │
       │ PostgreSQL                   │ AIAgent (hermes-agent)
       │                              │   ├─ LLM 调用
       │                              │   └─ tool calling
       │                              │       └─ MCP 工具? ← 在哪执行?
```

#### 方案 A：MCP Server 在 API 侧（HTTP MCP）

```
  ┌─────────────────────────────────────────────────────┐
  │  API :8000                                          │
  │  ┌──────────────────────┐                           │
  │  │  MCP HTTP Server     │  暴露 HTTP/SSE 端点       │
  │  │  /mcp/sse            │  discover_schema          │
  │  │                      │  query_schema             │
  │  │                      │  execute_query            │
  │  └──────────┬───────────┘                           │
  │             │                                       │
  │             ▼                                       │
  │  ┌──────────────────────┐                           │
  │  │  数据库连接 (asyncpg) │                           │
  │  └──────────────────────┘                           │
  └─────────────────────────────────────────────────────┘
                    ▲
                    │ HTTP (tool call via MCP protocol)
                    │
  ┌────────────────┴────────────────────────────────────┐
  │  Worker :8001                                       │
  │  ┌──────────────────────┐                           │
  │  │  AIAgent             │                           │
  │  │  register_mcp_servers│                           │
  │  │    {"data-api": {    │                           │
  │  │      "url":          │                           │
  │  │    "http://127.0.0.1:│                           │
  │  │         8000/mcp/sse"│                           │
  │  │    }}                │                           │
  │  └──────────────────────┘                           │
  └─────────────────────────────────────────────────────┘
```

- **优点**：API 已有数据库连接，无需重复配置；MCP 逻辑与现有服务层复用
- **缺点**：网络往返（localhost HTTP，延迟可忽略）；API 需要新增 FastAPI 子应用
- **耦合**：Worker 依赖 API 运行（单进程模式已满足）

#### 方案 B：MCP Server 在 Worker 侧（stdio MCP）

```
  ┌──────────────────────────┐      ┌──────────────────────────┐
  │  API :8000               │      │  Worker :8001             │
  │  ┌────────────────────┐  │      │  ┌────────────────────┐  │
  │  │  数据库连接         │  │      │  │  AIAgent           │  │
  │  └────────────────────┘  │      │  │  register_mcp_servers│  │
  └──────────────────────────┘      │  │    {"data": {       │  │
                                    │  │      "command":     │  │
                                    │  │    "python",        │  │
                                    │  │      "args": [      │  │
                                    │  │    "-m",            │  │
                                    │  │  "worker.mcp_server"│  │
                                    │  │      ]              │  │
                                    │  │    }}               │  │
                                    │  └─────────┬──────────┘  │
                                    │            │ stdio        │
                                    │  ┌─────────▼──────────┐  │
                                    │  │  MCP stdio Server  │  │
                                    │  │  (独立 Python 进程) │  │
                                    │  │  discover_schema    │  │
                                    │  │  query_schema       │  │
                                    │  │  execute_query      │  │
                                    │  └─────────┬──────────┘  │
                                    │            │             │
                                    │  ┌─────────▼──────────┐  │
                                    │  │  数据库连接 (asyncpg)│  │
                                    │  └────────────────────┘  │
                                    └──────────────────────────┘
```

- **优点**：hermes-agent 原生支持的 MCP 模式；独立进程隔离
- **缺点**：Worker 需要独立的数据库连接配置；多一层子进程管理；Windows 下 stdio 可能有 GBK 编码问题
- **耦合**：Worker 独立拥有数据库访问能力

### 3.2 推荐：方案 B（Worker 侧 stdio MCP）

**理由**：

1. **符合 hermes-agent 原生机制**：AIAgent 的 `register_mcp_servers()` 设计就是通过 stdio 子进程通信，HTTP MCP 需要额外的 HTTP transport 支持且不如 stdio 成熟
2. **职责清晰**：数据查询工具是 Worker 的"手"，应该跟着 AIAgent 走；API 侧专注 REST 管理和会话路由
3. **数据库连接**：Worker 进程已经可以通过环境变量获得 `DATABASE_URL`（和 API 共用同一个 PostgreSQL）
4. **独立可测试**：MCP server 可以脱离 Worker 单独启动调试

**具体实现**：

```python
# worker/agent.py 中注册
from tools.mcp_tool import register_mcp_servers

register_mcp_servers({
    "executive-data": {
        "command": sys.executable,          # 同 Python 解释器
        "args": ["-m", "worker.mcp_server"], # 模块路径
        "env": {
            "DATABASE_URL": os.environ["DATABASE_URL"],  # 继承数据库连接
        },
        "timeout": 30,
        "connect_timeout": 10,
    }
})
```

---

## 四、数据库设计

### 4.1 新表：`mcp_schema_registry`

```sql
CREATE TABLE mcp_schema_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    table_name VARCHAR(120) NOT NULL,            -- 物理表名
    display_name VARCHAR(160) NOT NULL,           -- 中文显示名
    description TEXT NOT NULL,                    -- 表用途说明
    category VARCHAR(80) NOT NULL DEFAULT '',     -- 分类：opportunity/delivery/collection/dimension
    column_schema JSONB NOT NULL DEFAULT '[]',    -- 列定义缓存
    is_enabled BOOLEAN NOT NULL DEFAULT true,     -- 是否对 Agent 可见
    is_indexed BOOLEAN NOT NULL DEFAULT false,    -- 是否已建立向量索引（语义搜索用）
    max_rows INTEGER NOT NULL DEFAULT 100,        -- 最大返回行数
    query_timeout_seconds INTEGER NOT NULL DEFAULT 10, -- 查询超时
    sample_rows JSONB,                            -- 示例数据缓存
    schema_version INTEGER NOT NULL DEFAULT 1,
    last_refreshed_at TIMESTAMPTZ,                -- schema 最后刷新时间
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(enterprise_id, table_name)
);

CREATE INDEX ix_mcp_schema_enterprise_enabled
    ON mcp_schema_registry(enterprise_id, is_enabled);
CREATE INDEX ix_mcp_schema_enterprise_category
    ON mcp_schema_registry(enterprise_id, category);
```

### 4.2 `column_schema` JSONB 结构

```json
[
  {
    "name": "id",
    "type": "uuid",
    "nullable": false,
    "comment": "主键",
    "is_primary_key": true,
    "references": null
  },
  {
    "name": "receivable_amount",
    "type": "numeric",
    "nullable": false,
    "comment": "应收金额",
    "is_primary_key": false,
    "references": null
  },
  {
    "name": "customer_id",
    "type": "uuid",
    "nullable": false,
    "comment": "关联客户",
    "is_primary_key": false,
    "references": {
      "table": "dim_customer",
      "column": "id"
    }
  }
]
```

### 4.3 初始化数据（从现有数据库自动发现）

```sql
-- 系统启动时通过 SQLAlchemy Inspector 自动发现表结构，无需手工插入。
-- 管理端提供「刷新 Schema」按钮触发重新发现。
```

---

## 五、Worker 侧实现

### 5.1 新文件：`worker/mcp_server.py`

```
backend/src/worker/
├── __init__.py
├── app.py              ← 已有，Worker FastAPI
├── agent.py            ← 已有，AgentRunner
├── session_store.py    ← 已有，会话映射
└── mcp_server.py       ← 新增，MCP stdio server
```

`mcp_server.py` 是一个符合 MCP 协议的 stdio server，实现 3 个工具：

```python
"""MCP stdio server：数据 schema 发现 + SQL 执行。

通过 stdio (stdin/stdout) 与 AIAgent 的 MCP 客户端通信，
协议为 JSON-RPC 2.0。

注册给 AIAgent 的方式：
    register_mcp_servers({
        "executive-data": {
            "command": sys.executable,
            "args": ["-m", "worker.mcp_server"],
            "env": {"DATABASE_URL": os.environ["DATABASE_URL"]},
        }
    })
"""

import asyncio
import json
import os
import sys

import asyncpg
import sqlglot
from sqlglot import exp


# ── 数据库连接 ──────────────────────────────────────────

_pool: asyncpg.Pool | None = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            os.environ["DATABASE_URL"],
            min_size=1,
            max_size=4,
        )
    return _pool


# ── 工具 1：discover_schema ──────────────────────────────

async def handle_discover_schema(params: dict) -> dict:
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


# ── 工具 2：query_schema ─────────────────────────────────

async def handle_query_schema(params: dict) -> dict:
    """获取指定表的列结构。"""
    table_name = params.get("table_name", "")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM mcp_schema_registry WHERE table_name = $1 AND is_enabled = true",
            table_name,
        )
        if row is None:
            return {"error": f"Table '{table_name}' not found or not enabled"}

        columns = json.loads(row["column_schema"])
        sample = json.loads(row["sample_rows"]) if row["sample_rows"] else None

    return {
        "table_name": row["table_name"],
        "display_name": row["display_name"],
        "description": row["description"],
        "columns": columns,
        "sample_rows": sample,
    }


# ── 工具 3：execute_query ────────────────────────────────

async def handle_execute_query(params: dict) -> dict:
    """安全执行 SELECT 查询。"""
    sql = params.get("sql", "")
    if not sql.strip():
        return {"error": "SQL is empty"}

    # 1. SQL 语法校验
    try:
        parsed = sqlglot.parse_one(sql)
    except Exception as e:
        return {"error": f"SQL parse error: {e}"}

    # 2. 仅允许 SELECT
    if not isinstance(parsed, exp.Select):
        return {"error": "Only SELECT statements are allowed"}

    # 3. 表名白名单校验
    table_names = [t.name.lower() for t in parsed.find_all(exp.Table) if t.name]
    pool = await get_pool()
    async with pool.acquire() as conn:
        allowed = await conn.fetch(
            "SELECT table_name FROM mcp_schema_registry WHERE is_enabled = true"
        )
        allowed_names = {r["table_name"].lower() for r in allowed}
    for name in table_names:
        if name not in allowed_names:
            return {"error": f"Table '{name}' is not in the allowed list"}

    # 4. 危险函数黑名单
    dangerous = {"pg_sleep", "pg_read_file", "pg_read_binary_file",
                 "pg_ls_dir", "lo_import", "lo_export"}
    for func in parsed.find_all(exp.Func):
        if func.sql_name().lower() in dangerous:
            return {"error": f"Function '{func.sql_name()}' is not allowed"}

    # 5. 执行（自动超时）
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, timeout=10)
    except Exception as e:
        return {"error": f"Query execution error: {e}"}

    columns = list(rows[0].keys()) if rows else []
    return {
        "columns": columns,
        "rows": [dict(r) for r in rows],
        "row_count": len(rows),
    }


# ── MCP JSON-RPC 主循环 ──────────────────────────────────

TOOLS = {
    "discover_schema": {
        "name": "discover_schema",
        "description": "列出所有可用的数据表及其用途说明。用于了解有哪些数据可以查询。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "可选，按分类过滤表，如 opportunity/delivery/collection"
                }
            }
        }
    },
    "query_schema": {
        "name": "query_schema",
        "description": "获取指定表的列结构（列名、类型、说明、外键关系）和示例数据。用于了解表的字段含义后生成正确的 SQL。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "表名，从 discover_schema 返回的 table_name 中选择"
                }
            },
            "required": ["table_name"]
        }
    },
    "execute_query": {
        "name": "execute_query",
        "description": (
            "执行一条只读 SQL 查询（仅 SELECT）。"
            "查询前必须先通过 discover_schema 和 query_schema 了解表结构。"
            "查询结果最多返回 100 行。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "要执行的 SELECT 语句"
                }
            },
            "required": ["sql"]
        }
    },
}

HANDLERS = {
    "discover_schema": handle_discover_schema,
    "query_schema": handle_query_schema,
    "execute_query": handle_execute_query,
}


async def main():
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
                        "serverInfo": {"name": "executive-data", "version": "1.0.0"},
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
                            "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}]},
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
```

### 5.2 修改：`worker/agent.py`

在 `AgentRunner.chat()` 调用前注册 MCP server（仅首次）：

```python
import sys
import os
from tools.mcp_tool import register_mcp_servers

_mcp_registered = False

async def _ensure_mcp_registered():
    global _mcp_registered
    if _mcp_registered:
        return
    register_mcp_servers({
        "executive-data": {
            "command": sys.executable,
            "args": ["-m", "worker.mcp_server"],
            "env": {"DATABASE_URL": os.environ["DATABASE_URL"]},
            "timeout": 30,
            "connect_timeout": 10,
        }
    })
    _mcp_registered = True
```

---

## 六、API 侧实现

### 6.1 新文件：`services/mcp_schema_service.py`

```python
"""MCP Schema 管理服务。

提供表级别的 schema 注册、发现、刷新功能。
"""

class McpSchemaService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_schemas(self, principal: Principal) -> McpSchemaCatalogOut:
        """列出企业的所有注册表。"""
        ...

    async def refresh_schema(self, table_name: str, principal: Principal) -> McpSchemaOut:
        """刷新指定表的 schema（重新读取列结构 + 示例数据）。"""
        # 使用 SQLAlchemy Inspector 自动发现
        ...

    async def update_schema(self, table_name: str, payload: McpSchemaUpdate, principal: Principal) -> McpSchemaOut:
        """更新表的显示名称、描述、启用状态等。"""
        ...

    async def refresh_all(self, principal: Principal) -> McpSchemaCatalogOut:
        """刷新所有表的 schema。"""
        ...
```

### 6.2 新路由：`api/routes/admin_mcp.py`（重写）

```
GET    /admin/mcp-schemas           → 列出所有表
PATCH  /admin/mcp-schemas/{name}    → 更新表配置
POST   /admin/mcp-schemas/{name}/refresh → 刷新 schema
POST   /admin/mcp-schemas/refresh-all    → 刷新所有
```

### 6.3 Schema 自动发现

```python
from sqlalchemy import inspect

async def _discover_table_schema(db_url: str, table_name: str) -> list[dict]:
    """通过 SQLAlchemy Inspector 自动发现表结构。"""
    engine = create_async_engine(db_url)
    async with engine.connect() as conn:
        insp = inspect(conn)
        columns = await conn.run_sync(lambda sync_conn: insp.get_columns(table_name))
        pk = await conn.run_sync(lambda sync_conn: insp.get_pk_constraint(table_name))
        fks = await conn.run_sync(lambda sync_conn: insp.get_foreign_keys(table_name))
    ...
```

---

## 七、前端调整

### 7.1 管理面板重构

`McpSchemaPanel` 替代 `McpToolsPanel`：

- 左侧：表列表（按 category 分组，搜索过滤）
- 右侧：表详情（列结构预览、示例数据、外键关系图）
- 操作：启用/停用表、刷新 schema、调整 max_rows/超时

### 7.2 类型定义

```typescript
type McpTableSchema = {
  table_name: string;
  display_name: string;
  description: string;
  category: string;
  column_schema: McpColumnSchema[];
  is_enabled: boolean;
  max_rows: number;
  query_timeout_seconds: number;
  sample_rows: Record<string, unknown>[] | null;
  schema_version: number;
  last_refreshed_at: string | null;
};

type McpColumnSchema = {
  name: string;
  type: string;
  nullable: boolean;
  comment: string;
  is_primary_key: boolean;
  references: { table: string; column: string } | null;
};
```

---

## 八、迁移路径

| Phase | 内容 | 新旧关系 |
|-------|------|---------|
| **Phase 1** | 新建 `mcp_schema_registry` 表 + 迁移脚本；实现 `worker/mcp_server.py`；实现 `McpSchemaService`；前端新面板 | 新旧并存，互不影响 |
| **Phase 2** | Worker 注册新 MCP server；Harness 的 plan prompt 切换为 3 步模式；MCP Hub 调用新接口 | 旧 11 个工具仍可用，plan 优先用新模式 |
| **Phase 3** | 前端管理页切换为新面板；删除旧面板 | 旧前端代码移除 |
| **Phase 4** | 删除 `business_tools.py` 的 11 个 handler；删除 `mcp_tool_configs` + `mcp_tool_definitions` 表；删除旧 schema/路由 | 彻底清理 |

---

## 九、待讨论

1. **execute_query 的行级权限注入**：自动注入 `enterprise_id` + `organization_unit_ids` 需要解析 SQL AST 并改写 WHERE 子句，实现复杂度较高。Phase 1 可以先不做自动注入，仅依赖表名白名单 + enterprise_id 已通过数据隔离保证安全。

2. **Schema 缓存的刷新策略**：每次查询前是否重新发现 schema？还是依赖管理端手动刷新？建议：首次启动全量发现，之后管理端手动触发增量刷新。

3. **LLM 生成的 SQL 质量**：需要在 system prompt 中给出 SQL 编写规范（表名、字段名必须从 schema 中获取、必须加 `is_current = true` 过滤等），必要时在 execute_query 中加入自动改写。
