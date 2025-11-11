from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import CruisePriceSnapshot, NotificationPreference

logger = logging.getLogger(__name__)


def get_notification_email(db: Session) -> Optional[str]:
    stmt = select(NotificationPreference).limit(1)
    row = db.scalars(stmt).first()
    return row.email if row else None


def upsert_notification_email(db: Session, email: str) -> str:
    stmt = select(NotificationPreference).limit(1)
    pref = db.scalars(stmt).first()
    now = datetime.now().astimezone()
    if pref:
        pref.email = email
        pref.updated_at = now
    else:
        pref = NotificationPreference(email=email, updated_at=now)
        db.add(pref)
    db.commit()
    return pref.email


def notify_price_change(db: Session, previous: CruisePriceSnapshot, current: CruisePriceSnapshot) -> None:
    email = get_notification_email(db)
    if not email:
        logger.info("Price changed but no notification email configured")
        return
    if not settings.sendgrid_api_key:
        logger.warning("SendGrid API key missing; skipping price change email")
        return
    prev_total = previous.total_price or Decimal(0)
    curr_total = current.total_price or Decimal(0)
    diff_value = curr_total - prev_total
    diff = _format_currency(abs(diff_value))
    direction = "increased" if diff_value > 0 else "decreased"
    subject = f"Cruise price {direction}: {diff}"
    body = _build_email_body(previous, current, diff, direction)
    _send_email(email, subject, body)


def send_test_email(recipient: str) -> None:
    if not settings.sendgrid_api_key:
        raise RuntimeError("SendGrid API key not configured")
    subject = "Cruise Price Tracker test alert"
    body = "This is a test email confirming that price alerts are configured correctly."
    _send_email(recipient, subject, body)


def _send_email(recipient: str, subject: str, body: str) -> None:
    payload = {
        "personalizations": [{"to": [{"email": recipient}], "subject": subject}],
        "from": {"email": settings.notification_from_email, "name": settings.app_name},
        "content": [
            {"type": "text/plain", "value": body},
        ],
    }
    response = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {settings.sendgrid_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )
    if response.status_code >= 400:
        logger.error("SendGrid API error %s: %s", response.status_code, response.text)
        response.raise_for_status()


def _build_email_body(
    previous: CruisePriceSnapshot, current: CruisePriceSnapshot, diff: str, direction: str
) -> str:
    lines = [
        f"The total price has {direction}: {diff}",
        "",
        "Previous snapshot:",
        _format_snapshot(previous),
        "",
        "Current snapshot:",
        _format_snapshot(current),
    ]
    return "\n".join(lines)


def _format_snapshot(snapshot: CruisePriceSnapshot) -> str:
    return "\n".join(
        [
            f"Scraped at: {snapshot.scraped_at.isoformat()}",
            f"Total price: {_format_currency(snapshot.total_price)}",
            f"Subtotal: {_format_currency(snapshot.subtotal)}",
            f"Cruise fare: {_format_currency(snapshot.cruise_fare)}",
            f"Discounts: {_format_currency(snapshot.discounts)}",
            f"Taxes & fees: {_format_currency(snapshot.taxes_and_fees)}",
        ]
    )


def _format_currency(value: Optional[Decimal]) -> str:
    if value is None:
        return "N/A"
    return f"${value:,.2f}"
