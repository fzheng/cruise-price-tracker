from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Sequence

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
    subject, text_body, html_body = _build_price_change_message(previous, current, diff, direction)
    _send_email(email, subject, text_body, html_body)


def send_test_email(recipient: str) -> None:
    if not settings.sendgrid_api_key:
        raise RuntimeError("SendGrid API key not configured")
    subject = "Cruise Price Tracker alert test"
    text_body = (
        f"Hi there!\n\nThis is a quick confirmation that {settings.app_name} can reach you.\n"
        "You'll receive a real alert whenever the total cruise price changes.\n\n"
        "Safe travels!"
    )
    html_body = _wrap_html_body(
        "<p>Hi there!</p>"
        "<p>This is a quick confirmation that <strong>{app}</strong> can reach you. "
        "You'll receive a real alert whenever the total cruise price changes.</p>"
        "<p>Safe travels!</p>".format(app=settings.app_name)
    )
    _send_email(recipient, subject, text_body, html_body)


def _send_email(recipient: str, subject: str, text_body: str, html_body: Optional[str] = None) -> None:
    payload = {
        "personalizations": [{"to": [{"email": recipient}], "subject": subject}],
        "from": {"email": settings.notification_from_email, "name": settings.app_name},
        "content": [{"type": "text/plain", "value": text_body}],
    }
    if html_body:
        payload["content"].append({"type": "text/html", "value": html_body})

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


def _build_price_change_message(
    previous: CruisePriceSnapshot, current: CruisePriceSnapshot, diff: str, direction: str
) -> tuple[str, str, str]:
    subject = f"{settings.app_name}: price {direction} by {diff}"
    prev_lines = _snapshot_lines(previous)
    curr_lines = _snapshot_lines(current)
    text_body = _build_text_body(direction, diff, prev_lines, curr_lines)
    html_body = _build_html_body(direction, diff, prev_lines, curr_lines)
    return subject, text_body, html_body


def _build_text_body(
    direction: str, diff: str, previous: Sequence[tuple[str, str]], current: Sequence[tuple[str, str]]
) -> str:
    lines = [
        f"The total price has {direction} by {diff}.",
        "",
        "Most recent quote:",
    ]
    lines.extend(f"- {label}: {value}" for label, value in current)
    lines.extend(
        [
            "",
            "Previous quote:",
        ]
    )
    lines.extend(f"- {label}: {value}" for label, value in previous)
    lines.append("")
    lines.append(f"— {settings.app_name}")
    return "\n".join(lines)


def _build_html_body(
    direction: str, diff: str, previous: Sequence[tuple[str, str]], current: Sequence[tuple[str, str]]
) -> str:
    body = (
        f"<p style='font-size:16px;margin:0 0 12px;'>The total price has <strong>{direction}</strong> by "
        f"<strong>{diff}</strong>.</p>"
        f"{_table_html('Current snapshot', current)}"
        f"{_table_html('Previous snapshot', previous)}"
        "<p style='margin-top:16px;color:#64748b;font-size:13px;'>You are receiving this alert because you subscribed to "
        f"updates from {settings.app_name}. Manage alerts inside the dashboard.</p>"
    )
    return _wrap_html_body(body)


def _table_html(title: str, rows: Sequence[tuple[str, str]]) -> str:
    row_html = "".join(
        f"<tr><td style='padding:6px 8px;color:#94a3b8;'>{label}</td>"
        f"<td style='padding:6px 8px;font-weight:600;color:#0f172a;'>{value}</td></tr>"
        for label, value in rows
    )
    return (
        "<div style='margin-bottom:16px;'>"
        f"<h3 style='margin:0 0 8px;color:#0f172a;'>{title}</h3>"
        "<table width='100%' cellspacing='0' cellpadding='0' "
        "style='border-collapse:collapse;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;'>"
        f"{row_html}</table></div>"
    )


def _wrap_html_body(inner: str) -> str:
    return (
        "<!DOCTYPE html><html><body style='font-family:Inter,Segoe UI,sans-serif;background:#e2e8f0;"
        "padding:24px;margin:0;'>"
        "<div style='max-width:520px;margin:0 auto;background:#ffffff;padding:24px;border-radius:16px;"
        "box-shadow:0 10px 25px rgba(15,23,42,0.08);'>"
        f"<h2 style='margin-top:0;margin-bottom:12px;color:#0f172a;'>{settings.app_name}</h2>"
        f"{inner}"
        "</div></body></html>"
    )


def _snapshot_lines(snapshot: CruisePriceSnapshot) -> list[tuple[str, str]]:
    return [
        ("Scraped at", snapshot.scraped_at.isoformat()),
        ("Total price", _format_currency(snapshot.total_price)),
        ("Subtotal", _format_currency(snapshot.subtotal)),
        ("Cruise fare", _format_currency(snapshot.cruise_fare)),
        ("Discounts", _format_currency(snapshot.discounts)),
        ("Taxes & fees", _format_currency(snapshot.taxes_and_fees)),
    ]


def _format_currency(value: Optional[Decimal]) -> str:
    if value is None:
        return "N/A"
    return f"${value:,.2f}"
