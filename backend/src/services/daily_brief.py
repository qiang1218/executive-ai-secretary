from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import Settings
from services.data_freshness import effective_domain_status
from models import (
    DailySnapshot,
    DataDomainStatus,
    DataSyncRun,
    FactDelivery,
    FactFinanceCollection,
    FactOpportunity,
    FactTarget,
)
from schemas import (
    DailyBriefDomainReadinessOut,
    DailyBriefItemOut,
    DailyBriefOut,
)
from core.security import as_utc, utc_now

DOMAIN_ORDER = ("opportunity", "delivery", "collection", "target")
SUCCESSFUL_SYNC_STATUSES = ("completed", "succeeded")
SUCCESSFUL_ACTIVATION_STATUSES = ("activated", "unchanged")


def _opaque_batch_id(source_batch_id: str | None) -> str | None:
    if not source_batch_id:
        return None
    digest = hashlib.sha256(source_batch_id.encode("utf-8")).hexdigest()[:20]
    return f"batch_{digest}"


async def _latest_successful_batch_ids(db: AsyncSession, enterprise_id: uuid.UUID) -> list[str]:
    result = await db.execute(
        select(DataSyncRun.source_batch_id)
        .where(
            DataSyncRun.enterprise_id == enterprise_id,
            DataSyncRun.status.in_(SUCCESSFUL_SYNC_STATUSES),
            DataSyncRun.atomic_activation_status.in_(SUCCESSFUL_ACTIVATION_STATUSES),
            DataSyncRun.source_batch_id.is_not(None),
        )
        .order_by(
            func.coalesce(
                DataSyncRun.activated_at,
                DataSyncRun.completed_at,
                DataSyncRun.created_at,
            ).desc()
        )
    )
    rows = result.scalars().all()
    return list(dict.fromkeys(value for value in rows if value))


async def _latest_snapshots_for_batch(
    db: AsyncSession,
    *,
    enterprise_id: uuid.UUID,
    organization_unit_ids: set[uuid.UUID],
    source_batch_id: str,
    covers_all_connected_units: bool,
) -> tuple[list[DailySnapshot], bool]:
    if covers_all_connected_units:
        enterprise_snapshot = await db.scalar(
            select(DailySnapshot)
            .where(
                DailySnapshot.enterprise_id == enterprise_id,
                DailySnapshot.organization_unit_id.is_(None),
                DailySnapshot.source_batch_id == source_batch_id,
            )
            .order_by(
                DailySnapshot.snapshot_date.desc(),
                DailySnapshot.source_data_as_of.desc(),
            )
            .limit(1)
        )
        if enterprise_snapshot is not None:
            return [enterprise_snapshot], True

    result = await db.execute(
        select(DailySnapshot)
        .where(
            DailySnapshot.enterprise_id == enterprise_id,
            DailySnapshot.organization_unit_id.in_(organization_unit_ids),
            DailySnapshot.source_batch_id == source_batch_id,
        )
        .order_by(
            DailySnapshot.snapshot_date.desc(),
            DailySnapshot.source_data_as_of.desc(),
        )
    )
    rows = result.scalars().all()
    latest_by_unit: dict[uuid.UUID, DailySnapshot] = {}
    for row in rows:
        if row.organization_unit_id is not None:
            latest_by_unit.setdefault(row.organization_unit_id, row)
    return list(latest_by_unit.values()), False


async def _latest_legacy_snapshots(
    db: AsyncSession,
    *,
    enterprise_id: uuid.UUID,
    organization_unit_ids: set[uuid.UUID],
    covers_all_connected_units: bool,
) -> tuple[list[DailySnapshot], bool]:
    """Read pre-batch snapshots without ever using an enterprise row for a partial scope."""

    if covers_all_connected_units:
        enterprise_snapshot = await db.scalar(
            select(DailySnapshot)
            .where(
                DailySnapshot.enterprise_id == enterprise_id,
                DailySnapshot.organization_unit_id.is_(None),
                DailySnapshot.source_batch_id.is_(None),
            )
            .order_by(
                DailySnapshot.snapshot_date.desc(),
                DailySnapshot.source_data_as_of.desc(),
            )
            .limit(1)
        )
        if enterprise_snapshot is not None:
            return [enterprise_snapshot], True

    result = await db.execute(
        select(DailySnapshot)
        .where(
            DailySnapshot.enterprise_id == enterprise_id,
            DailySnapshot.organization_unit_id.in_(organization_unit_ids),
            DailySnapshot.source_batch_id.is_(None),
        )
        .order_by(
            DailySnapshot.snapshot_date.desc(),
            DailySnapshot.source_data_as_of.desc(),
        )
    )
    rows = result.scalars().all()
    if not rows:
        return [], False
    newest_date = rows[0].snapshot_date
    latest_by_unit: dict[uuid.UUID, DailySnapshot] = {}
    for row in rows:
        if row.snapshot_date != newest_date:
            break
        if row.organization_unit_id is not None:
            latest_by_unit.setdefault(row.organization_unit_id, row)
    return list(latest_by_unit.values()), False


async def _resolve_snapshots(
    db: AsyncSession,
    *,
    enterprise_id: uuid.UUID,
    organization_unit_ids: set[uuid.UUID],
    covers_all_connected_units: bool,
) -> tuple[list[DailySnapshot], bool, str | None]:
    for source_batch_id in await _latest_successful_batch_ids(db, enterprise_id):
        rows, uses_enterprise_snapshot = await _latest_snapshots_for_batch(
            db,
            enterprise_id=enterprise_id,
            organization_unit_ids=organization_unit_ids,
            source_batch_id=source_batch_id,
            covers_all_connected_units=covers_all_connected_units,
        )
        if rows:
            return rows, uses_enterprise_snapshot, source_batch_id
    rows, uses_enterprise_snapshot = await _latest_legacy_snapshots(
        db,
        enterprise_id=enterprise_id,
        organization_unit_ids=organization_unit_ids,
        covers_all_connected_units=covers_all_connected_units,
    )
    return rows, uses_enterprise_snapshot, None


def _metric_total(snapshots: Iterable[DailySnapshot], name: str) -> tuple[bool, float]:
    found = False
    total = 0.0
    for snapshot in snapshots:
        if name not in snapshot.metrics_json:
            continue
        found = True
        value = snapshot.metrics_json.get(name)
        if isinstance(value, int | float):
            total += float(value)
    return found, total


async def _fact_count(
    db: AsyncSession,
    model: type[FactOpportunity | FactDelivery | FactFinanceCollection | FactTarget],
    *,
    enterprise_id: uuid.UUID,
    organization_unit_ids: set[uuid.UUID],
) -> int:
    return int(
        await db.scalar(
            select(func.count(model.id)).where(
                model.enterprise_id == enterprise_id,
                model.organization_unit_id.in_(organization_unit_ids),
                model.is_current.is_(True),
            )
        )
        or 0
    )


async def _scoped_record_counts(
    db: AsyncSession,
    *,
    enterprise_id: uuid.UUID,
    organization_unit_ids: set[uuid.UUID],
) -> dict[str, int]:
    return {
        "opportunity": await _fact_count(
            db,
            FactOpportunity,
            enterprise_id=enterprise_id,
            organization_unit_ids=organization_unit_ids,
        ),
        "delivery": await _fact_count(
            db,
            FactDelivery,
            enterprise_id=enterprise_id,
            organization_unit_ids=organization_unit_ids,
        ),
        "collection": await _fact_count(
            db,
            FactFinanceCollection,
            enterprise_id=enterprise_id,
            organization_unit_ids=organization_unit_ids,
        ),
        "target": await _fact_count(
            db,
            FactTarget,
            enterprise_id=enterprise_id,
            organization_unit_ids=organization_unit_ids,
        ),
    }


async def _domain_readiness(
    db: AsyncSession,
    *,
    enterprise_id: uuid.UUID,
    organization_unit_ids: set[uuid.UUID],
    settings: Settings,
) -> list[DailyBriefDomainReadinessOut]:
    result = await db.execute(
        select(DataDomainStatus).where(DataDomainStatus.enterprise_id == enterprise_id)
    )
    rows = result.scalars().all()
    by_domain = {row.domain: row for row in rows}
    record_counts = await _scoped_record_counts(
        db,
        enterprise_id=enterprise_id,
        organization_unit_ids=organization_unit_ids,
    )
    output: list[DailyBriefDomainReadinessOut] = []
    for domain in DOMAIN_ORDER:
        row = by_domain.get(domain)
        output.append(
            DailyBriefDomainReadinessOut(
                domain=domain,
                readiness=(
                    effective_domain_status(row, settings.data_stale_after_hours)
                    if row is not None
                    else "unavailable"
                ),
                data_as_of=row.source_data_as_of if row is not None else None,
                record_count=record_counts[domain],
            )
        )
    return output


def _brief_readiness(
    *,
    snapshots: list[DailySnapshot],
    domains: list[DailyBriefDomainReadinessOut],
    expected_scope_size: int,
    uses_enterprise_snapshot: bool,
) -> str:
    if not snapshots:
        return "unavailable"
    if not uses_enterprise_snapshot and len(snapshots) != expected_scope_size:
        return "partial"
    states = {
        row.readiness for row in domains if row.domain in {"delivery", "collection"}
    }
    if states & {"failed", "partial", "not_configured", "never_synced", "unavailable"}:
        return "partial"
    if "stale" in states:
        return "stale"
    return "ready"


def _brief_data_as_of(
    *,
    snapshots: list[DailySnapshot],
    domains: list[DailyBriefDomainReadinessOut],
):
    domain_cutoffs = [
        row.data_as_of
        for row in domains
        if row.domain in {"delivery", "collection"} and row.data_as_of is not None
    ]
    if domain_cutoffs:
        return min(domain_cutoffs, key=as_utc)
    snapshot_cutoffs = [row.source_data_as_of for row in snapshots]
    return min(snapshot_cutoffs, key=as_utc, default=None)


async def build_daily_brief(
    db: AsyncSession,
    *,
    enterprise_id: uuid.UUID,
    organization_unit_ids: set[uuid.UUID],
    connected_organization_unit_ids: set[uuid.UUID],
    settings: Settings,
) -> DailyBriefOut:
    covers_all_connected_units = organization_unit_ids == connected_organization_unit_ids
    snapshots, uses_enterprise_snapshot, source_batch_id = await _resolve_snapshots(
        db,
        enterprise_id=enterprise_id,
        organization_unit_ids=organization_unit_ids,
        covers_all_connected_units=covers_all_connected_units,
    )

    _, delayed_total = _metric_total(snapshots, "delivery_delayed_count")
    _, overdue_amount = _metric_total(snapshots, "overdue_amount")
    overdue_count_found, overdue_count_total = _metric_total(
        snapshots,
        "overdue_record_count",
    )
    overdue_count = int(overdue_count_total)
    if overdue_amount > 0 and not overdue_count_found:
        overdue_count = int(
            await db.scalar(
                select(func.count(FactFinanceCollection.id)).where(
                    FactFinanceCollection.enterprise_id == enterprise_id,
                    FactFinanceCollection.organization_unit_id.in_(organization_unit_ids),
                    FactFinanceCollection.is_current.is_(True),
                    FactFinanceCollection.overdue_days > 0,
                    FactFinanceCollection.outstanding_amount > 0,
                )
            )
            or 0
        )

    items_by_rule: dict[str, DailyBriefItemOut] = {}
    delayed_count = int(delayed_total)
    if delayed_count > 0:
        items_by_rule["delivery_delayed"] = DailyBriefItemOut(
            rule_id="delivery_delayed",
            domain="delivery",
            title=f"{delayed_count} 个交付项目已延期",
            detail="需确认当前里程碑、责任人与新的完成时间。",
            affected_count=delayed_count,
        )
    if overdue_amount > 0:
        detail = "需确认责任人、客户承诺日期与回款闭环。"
        if overdue_count > 0:
            detail = f"涉及 {overdue_count} 笔应收款，{detail}"
        items_by_rule["collection_overdue"] = DailyBriefItemOut(
            rule_id="collection_overdue",
            domain="collection",
            title="存在逾期回款待确认",
            detail=detail,
            affected_count=overdue_count,
            amount=round(overdue_amount, 2),
            unit="元",
        )
    items = [
        item
        for rule_id in ("delivery_delayed", "collection_overdue")
        if (item := items_by_rule.get(rule_id)) is not None
    ]
    domains = await _domain_readiness(
        db,
        enterprise_id=enterprise_id,
        organization_unit_ids=organization_unit_ids,
        settings=settings,
    )
    return DailyBriefOut(
        brief_date=max((row.snapshot_date for row in snapshots), default=None),
        data_as_of=_brief_data_as_of(snapshots=snapshots, domains=domains),
        source_batch_id=_opaque_batch_id(source_batch_id),
        readiness=_brief_readiness(
            snapshots=snapshots,
            domains=domains,
            expected_scope_size=len(organization_unit_ids),
            uses_enterprise_snapshot=uses_enterprise_snapshot,
        ),
        attention_count=len(items),
        items=items,
        domains=domains,
        organization_unit_ids=sorted(organization_unit_ids, key=str),
        uses_enterprise_snapshot=uses_enterprise_snapshot,
        generated_at=utc_now(),
    )


class DailyBriefService:
    """Service for assembling the daily executive brief.

    Follows the anspire service convention: receive the database session and
    settings in the constructor, expose business methods. New code should
    prefer ``DailyBriefService(db, settings).build(...)`` over the module-level
    ``build_daily_brief(db, ..., settings=...)`` function; both are equivalent.
    """

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def build(
        self,
        *,
        enterprise_id: uuid.UUID,
        organization_unit_ids: set[uuid.UUID],
        connected_organization_unit_ids: set[uuid.UUID],
    ) -> DailyBriefOut:
        """Build the daily brief for the given enterprise and scope."""
        return await build_daily_brief(
            self._session,
            enterprise_id=enterprise_id,
            organization_unit_ids=organization_unit_ids,
            connected_organization_unit_ids=connected_organization_unit_ids,
            settings=self._settings,
        )
