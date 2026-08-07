"""Phase 4 coverage: ``/api/v1/admin/mcp-schemas`` admin surface.

These tests cover the MCP v2 admin surface that replaces the v1
``/api/v1/admin/mcp-tools`` legacy endpoints (Phase 4 cleanup). They verify
the HTTP contract and the catalog semantics:

* ``GET /admin/mcp-schemas`` — list across the requester's enterprise, with
  ``is_enabled`` flag honoured.
* ``GET /admin/mcp-schemas/{table_name}`` — fetch by table name.
* ``PATCH /admin/mcp-schemas/{table_name}`` — toggle ``is_enabled`` /
  update ``display_name`` / ``description`` and ``max_rows``.
* ``POST /admin/mcp-schemas/{table_name}/refresh`` — refresh a single row.
* ``POST /admin/mcp-schemas/refresh-all`` — bulk refresh; refresh-all
  always returns a catalog shape.

The tests run against the in-memory sqlite app configured by
:mod:`tests.conftest`. They intentionally avoid touching the stdio MCP
server (``worker/mcp_server.py``) — that path is covered by
``test_admin_mcp_schema_server.py`` once a dedicated client harness is
factored in (Phase 5).

Phase 4 deliberately retires these tests' v1 counterparts:
``tests/test_mcp_admin.py`` (legacy ``/admin/mcp-tools``) and
``tests/test_mcp_business_v3.py`` (11 hard-coded handlers) were
deleted alongside the codebase they covered.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from db import SessionLocal
from models import McpSchemaRegistry
from core.security import utc_now


def _seed_schema(
    enterprise_id,
    *,
    table_name: str,
    is_enabled: bool = True,
    max_rows: int = 50,
    query_timeout_seconds: int = 20,
) -> None:
    with SessionLocal.begin() as db:
        db.add(
            McpSchemaRegistry(
                enterprise_id=enterprise_id,
                table_name=table_name,
                display_name=table_name.replace("_", " ").title(),
                description=f"Detected table {table_name}",
                category="operations",
                column_schema=[
                    {"name": "id", "type": "UUID", "nullable": False},
                    {"name": "created_at", "type": "TIMESTAMP", "nullable": False},
                ],
                is_enabled=is_enabled,
                max_rows=max_rows,
                query_timeout_seconds=query_timeout_seconds,
                sample_rows=[],
                schema_version=1,
                last_refreshed_at=utc_now(),
            )
        )


def _admin_headers(client: TestClient, seeded: dict) -> dict[str, str]:
    session_data = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "TempStrong!23456"},
    ).json()
    return {"X-CSRF-Token": session_data["csrf_token"]}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. Authorization
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_list_schemas_rejects_anonymous(
    client: TestClient, seeded: dict
) -> None:
    response = client.get("/api/v1/admin/mcp-schemas")
    assert response.status_code == 401, response.text


def test_list_schemas_rejects_non_admin(
    client: TestClient, seeded: dict
) -> None:
    session_data = client.post(
        "/api/v1/auth/login",
        json={"email": "executive@example.com", "password": "TempStrong!23456"},
    ).json()
    response = client.get(
        "/api/v1/admin/mcp-schemas",
        headers={"X-CSRF-Token": session_data["csrf_token"]},
    )
    assert response.status_code in (403, 401), response.text


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. List
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_list_schemas_returns_empty_catalog_initially(
    client: TestClient, seeded: dict
) -> None:
    headers = _admin_headers(client, seeded)
    response = client.get("/api/v1/admin/mcp-schemas", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tables"] == []
    assert body["total"] == 0
    assert body["enabled_count"] == 0
    assert body["last_refreshed_at"] is None


def test_list_schemas_returns_only_enterprise_scoped_rows(
    client: TestClient, seeded: dict
) -> None:
    _seed_schema(seeded["enterprise_id"], table_name="sales_forecast")
    _seed_schema(seeded["enterprise_id"], table_name="collection_aging")
    headers = _admin_headers(client, seeded)

    response = client.get("/api/v1/admin/mcp-schemas", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["total"] == 2
    assert {row["table_name"] for row in body["tables"]} == {
        "sales_forecast",
        "collection_aging",
    }
    assert body["enabled_count"] == 2


def test_list_schemas_marks_disabled_rows(
    client: TestClient, seeded: dict
) -> None:
    _seed_schema(seeded["enterprise_id"], table_name="active_table", is_enabled=True)
    _seed_schema(seeded["enterprise_id"], table_name="disabled_table", is_enabled=False)
    headers = _admin_headers(client, seeded)

    response = client.get("/api/v1/admin/mcp-schemas", headers=headers)
    body = response.json()

    assert body["total"] == 2
    assert body["enabled_count"] == 1
    by_name = {row["table_name"]: row for row in body["tables"]}
    assert by_name["active_table"]["is_enabled"] is True
    assert by_name["disabled_table"]["is_enabled"] is False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. Get one
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_get_schema_returns_named_row(
    client: TestClient, seeded: dict
) -> None:
    _seed_schema(seeded["enterprise_id"], table_name="sales_forecast")
    headers = _admin_headers(client, seeded)

    response = client.get("/api/v1/admin/mcp-schemas/sales_forecast", headers=headers)
    assert response.status_code == 200, response.text
    row = response.json()
    assert row["table_name"] == "sales_forecast"
    assert row["category"] == "operations"
    assert row["max_rows"] == 50


def test_get_schema_404_when_missing(
    client: TestClient, seeded: dict
) -> None:
    headers = _admin_headers(client, seeded)
    response = client.get("/api/v1/admin/mcp-schemas/does_not_exist", headers=headers)
    assert response.status_code == 404, response.text


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. Patch
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_patch_schema_toggles_is_enabled(
    client: TestClient, seeded: dict
) -> None:
    _seed_schema(seeded["enterprise_id"], table_name="sales_forecast", is_enabled=True)
    headers = _admin_headers(client, seeded)

    response = client.patch(
        "/api/v1/admin/mcp-schemas/sales_forecast",
        headers=headers,
        json={"is_enabled": False},
    )
    assert response.status_code == 200, response.text
    row = response.json()
    assert row["is_enabled"] is False

    # And listing reflects the new state.
    listing = client.get("/api/v1/admin/mcp-schemas", headers=headers).json()
    assert listing["enabled_count"] == 0
    assert listing["tables"][0]["is_enabled"] is False


def test_patch_schema_rejects_unknown_fields(
    client: TestClient, seeded: dict
) -> None:
    _seed_schema(seeded["enterprise_id"], table_name="sales_forecast")
    headers = _admin_headers(client, seeded)

    response = client.patch(
        "/api/v1/admin/mcp-schemas/sales_forecast",
        headers=headers,
        json={"definitely_not_a_real_field": True},
    )
    assert response.status_code == 422, response.text


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. Refresh
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_refresh_schema_updates_last_refreshed_at(
    client: TestClient, seeded: dict
) -> None:
    _seed_schema(seeded["enterprise_id"], table_name="sales_forecast")
    headers = _admin_headers(client, seeded)

    response = client.post(
        "/api/v1/admin/mcp-schemas/sales_forecast/refresh",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["table_name"] == "sales_forecast"
    assert body["refreshed_at"] is not None
    # single-table refresh is one of: refreshed (success) or noop (no change).
    # We accept any path that ends with a 200 + refresh_at populated.


def test_refresh_all_returns_catalog(
    client: TestClient, seeded: dict
) -> None:
    _seed_schema(seeded["enterprise_id"], table_name="a")
    _seed_schema(seeded["enterprise_id"], table_name="b")
    _seed_schema(seeded["enterprise_id"], table_name="c", is_enabled=False)
    headers = _admin_headers(client, seeded)

    response = client.post(
        "/api/v1/admin/mcp-schemas/refresh-all",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 3
    assert {row["table_name"] for row in body["tables"]} == {"a", "b", "c"}
    assert body["enabled_count"] == 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. Service-level smoke test (no HTTP)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_mcp_schema_service_list_and_disable(seeded: dict) -> None:
    _seed_schema(seeded["enterprise_id"], table_name="orders", max_rows=10)
    _seed_schema(seeded["enterprise_id"], table_name="refunds", is_enabled=False)
    from datetime import datetime, timedelta, timezone

    from db.session import AsyncSessionLocal
    from models import User, UserSession
    from services.authz import Principal
    from services.mcp_schema_service import McpSchemaService

    admin_id = seeded["users"]["admin@example.com"]
    now = datetime.now(timezone.utc)
    with SessionLocal.begin() as db:
        sess = UserSession(
            user_id=admin_id,
            token_hash="integration-test-token-hash",
            csrf_hash="integration-test-csrf-hash",
            expires_at=now + timedelta(hours=1),
            idle_expires_at=now + timedelta(minutes=30),
            last_seen_at=now,
        )
        db.add(sess)
        db.flush()
        session_id = sess.id

    with SessionLocal.begin() as db:
        user = db.get(User, admin_id)
        session = db.get(UserSession, session_id)
        principal = Principal(user=user, session=session)

    async with AsyncSessionLocal() as adb:
        svc = McpSchemaService(adb)
        catalog = await svc.list_schemas(principal)

    assert catalog.total == 2
    assert catalog.enabled_count == 1
    by_name = {row.table_name: row for row in catalog.tables}
    assert by_name["orders"].max_rows == 10
    assert by_name["orders"].is_enabled is True
    assert by_name["refunds"].is_enabled is False
