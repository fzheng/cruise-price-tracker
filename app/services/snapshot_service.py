from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from collections import OrderedDict
from datetime import datetime

from ..models import CruisePriceSnapshot
from ..schemas import ChartPoint, CruiseSnapshotCreate


def create_snapshot(db: Session, payload: CruiseSnapshotCreate) -> CruisePriceSnapshot:
    """Persist a new snapshot in the database."""

    snapshot = CruisePriceSnapshot(**payload.model_dump())
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def get_latest_snapshot(db: Session) -> CruisePriceSnapshot | None:
    stmt = select(CruisePriceSnapshot).order_by(CruisePriceSnapshot.scraped_at.desc()).limit(1)
    return db.scalars(stmt).first()


def get_snapshots(db: Session, limit: int = 50) -> list[CruisePriceSnapshot]:
    stmt = select(CruisePriceSnapshot).order_by(CruisePriceSnapshot.scraped_at.desc()).limit(limit)
    return list(db.scalars(stmt))


def get_chart_points(db: Session, limit: int = 100, window: str = "hours") -> list[ChartPoint]:
    stmt = select(CruisePriceSnapshot).order_by(CruisePriceSnapshot.scraped_at.asc()).limit(limit)
    rows = db.scalars(stmt).all()
    return _bucket_points(rows, window)


def _bucket_points(rows: list[CruisePriceSnapshot], window: str) -> list[ChartPoint]:
    if window == "hours":
        selected = rows
    else:
        grouped: OrderedDict[str, CruisePriceSnapshot] = OrderedDict()
        for row in rows:
            key = _bucket_key(row.scraped_at, window)
            grouped[key] = row  # keep the latest row for each bucket
        selected = list(grouped.values())
    return [
        ChartPoint(
            scraped_at=row.scraped_at,
            cruise_fare=row.cruise_fare,
            discounts=row.discounts,
            subtotal=row.subtotal,
            taxes_and_fees=row.taxes_and_fees,
            total_price=row.total_price,
        )
        for row in selected
    ]


def _bucket_key(timestamp: datetime, window: str) -> str:
    if window == "days":
        return timestamp.strftime("%Y-%m-%d")
    if window == "months":
        return timestamp.strftime("%Y-%m")
    return timestamp.isoformat()
