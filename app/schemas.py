from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CruiseSnapshotBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_encoders={Decimal: lambda v: float(v) if v is not None else None})

    itinerary_name: str | None = None
    leaving_from: str | None = None
    onboard: str | None = None
    sail_start_date: date | None = None
    sail_end_date: date | None = None
    guest_summary: str | None = None
    room_type: str | None = None
    room_subtype: str | None = None
    room_category: str | None = None
    cruise_fare: Decimal | None = None
    discounts: Decimal | None = None
    subtotal: Decimal | None = None
    taxes_and_fees: Decimal | None = None
    total_price: Decimal | None = None
    currency_code: str | None = None
    url: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class CruiseSnapshotCreate(CruiseSnapshotBase):
    scraped_at: datetime


class CruiseSnapshot(CruiseSnapshotBase):
    id: UUID
    scraped_at: datetime


class ChartPoint(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: lambda v: float(v) if v is not None else None})

    scraped_at: datetime
    cruise_fare: Decimal | None = None
    discounts: Decimal | None = None
    subtotal: Decimal | None = None
    taxes_and_fees: Decimal | None = None
    total_price: Decimal | None = None


class NotificationSettings(BaseModel):
    email: EmailStr


class NotificationStatus(BaseModel):
    email: EmailStr | None = None
