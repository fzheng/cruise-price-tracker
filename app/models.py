from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict

from sqlalchemy import Date, DateTime, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class CruisePriceSnapshot(Base):
    """Represents a single scrape of the cruise booking page."""

    __tablename__ = "cruise_price_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    itinerary_name: Mapped[str | None] = mapped_column(String(255))
    leaving_from: Mapped[str | None] = mapped_column(String(255))
    onboard: Mapped[str | None] = mapped_column(String(255))
    sail_start_date: Mapped[date | None] = mapped_column(Date())
    sail_end_date: Mapped[date | None] = mapped_column(Date())
    guest_summary: Mapped[str | None] = mapped_column(String(255))
    room_type: Mapped[str | None] = mapped_column(String(255))
    room_subtype: Mapped[str | None] = mapped_column(String(255))
    room_category: Mapped[str | None] = mapped_column(String(25))
    cruise_fare: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    discounts: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    taxes_and_fees: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency_code: Mapped[str | None] = mapped_column(String(16))
    url: Mapped[str | None] = mapped_column(Text())
    raw_payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return "CruisePriceSnapshot(id={0}, itinerary={1}, total={2})".format(
            self.id, self.itinerary_name, self.total_price
        )
