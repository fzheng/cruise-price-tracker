from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict

from dateutil import parser as date_parser
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

from ..config import settings
from ..schemas import CruiseSnapshotCreate

logger = logging.getLogger(__name__)


class RoyalCaribbeanCrawler:
    """Scrapes cruise pricing data from Royal Caribbean's booking flow."""

    SUMMARY_SELECTORS: Dict[str, str] = {
        "itinerary_name": "[data-testid=itinerary-summary-drawer-name]",
        "leaving_from": "[data-testid=itinerary-summary-port]",
        "onboard": "[data-testid=itinerary-summary-ship]",
        "sail_start_date": "[data-testid=itinerary-summary-start-date]",
        "sail_end_date": "[data-testid=itinerary-summary-end-date]",
        "guest_summary": "[data-testid=navigation-card-rooms-and-guests-link]",
        "room_type": "[data-testid=navigation-card-room-type-link]",
        "room_subtype": "[data-testid=navigation-card-room-subtype-link]",
        "room_category": "[data-testid=room-category]",
        "cruise_fare": "[data-testid=pricing-cruise-fare]",
        "discounts": "[data-testid=pricing-discount]",
        "subtotal": "[data-testid=pricing-subtotal]",
        "taxes_and_fees": "[data-testid=pricing-taxes]",
        "total_price": "[data-testid=pricing-total]",
    }

    def __init__(
        self,
        target_url: str | None = None,
        headless: bool | None = None,
        timeout_ms: int | None = None,
        user_agent: str | None = None,
        locale: str | None = None,
    ) -> None:
        # settings.target_url is a pydantic HttpUrl; cast to plain str to avoid playwright JSON errors
        self.target_url = str(target_url or settings.target_url)
        self.headless = headless if headless is not None else settings.headless
        self.timeout_ms = timeout_ms or settings.request_timeout_ms
        self.user_agent = user_agent or settings.user_agent
        self.locale = locale or settings.locale

    def scrape(self) -> CruiseSnapshotCreate:
        """Execute a single crawl and return the structured snapshot."""

        scraped_at = datetime.now(timezone.utc)
        logger.info("Starting crawl for %s", self.target_url)

        raw_values: Dict[str, str | None] = {}

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                user_agent=self.user_agent,
                locale=self.locale,
                viewport={"width": 1280, "height": 720},
            )
            page = context.new_page()
            try:
                page.set_extra_http_headers(
                    {
                        "Accept-Language": "en-US,en;q=0.9",
                        "sec-ch-ua": '"Not:A-Brand";v="99", "Chromium";v="118"',
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": '"Windows"',
                    }
                )
                page.goto(self.target_url, wait_until="networkidle", timeout=self.timeout_ms)
                self._dismiss_banners(page)
                page.wait_for_selector(self.SUMMARY_SELECTORS["total_price"], timeout=self.timeout_ms)

                for key, selector in self.SUMMARY_SELECTORS.items():
                    raw_values[key] = self._safe_text(page, selector)
            finally:
                context.close()
                browser.close()

        snapshot = CruiseSnapshotCreate(
            scraped_at=scraped_at,
            itinerary_name=raw_values.get("itinerary_name"),
            leaving_from=raw_values.get("leaving_from"),
            onboard=raw_values.get("onboard"),
            sail_start_date=self._parse_date(raw_values.get("sail_start_date")),
            sail_end_date=self._parse_date(raw_values.get("sail_end_date")),
            guest_summary=raw_values.get("guest_summary"),
            room_type=raw_values.get("room_type"),
            room_subtype=raw_values.get("room_subtype"),
            room_category=raw_values.get("room_category"),
            cruise_fare=self._parse_money(raw_values.get("cruise_fare")),
            discounts=self._parse_money(raw_values.get("discounts")),
            subtotal=self._parse_money(raw_values.get("subtotal")),
            taxes_and_fees=self._parse_money(raw_values.get("taxes_and_fees")),
            total_price=self._parse_money(raw_values.get("total_price")),
            currency_code=self._parse_currency(raw_values.get("total_price")),
            url=self.target_url,
            raw_payload={"raw_text": raw_values},
        )

        logger.info("Finished crawl at %s", scraped_at.isoformat())
        return snapshot

    def _dismiss_banners(self, page) -> None:
        """Dismiss cookie or marketing banners that may block the view."""

        candidate_buttons = [
            "Accept All Cookies",
            "I Accept",
            "Close",
            "No thanks",
        ]
        for label in candidate_buttons:
            try:
                page.get_by_role("button", name=re.compile(label, re.IGNORECASE)).click(timeout=3000)
                logger.debug("Dismissed banner via %s", label)
                break
            except PlaywrightTimeoutError:
                continue
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.debug("Unable to dismiss banner %s: %s", label, exc)

    def _safe_text(self, page, selector: str) -> str | None:
        try:
            locator = page.locator(selector)
            return locator.first.inner_text(timeout=5000).strip()
        except PlaywrightTimeoutError:
            logger.warning("Selector %s not found", selector)
            return None
        except Exception as exc:  # pragma: no cover - best effort logging
            logger.warning("Failed to read selector %s: %s", selector, exc)
            return None

    @staticmethod
    def _parse_date(value: str | None) -> date | None:
        if not value:
            return None
        try:
            return date_parser.parse(value).date()
        except (ValueError, TypeError):
            logger.warning("Unable to parse date: %s", value)
            return None

    @staticmethod
    def _parse_currency(value: str | None) -> str | None:
        if not value:
            return None
        match = re.search(r"([A-Z]{3})", value.upper())
        return match.group(1) if match else "USD"

    @staticmethod
    def _parse_money(value: str | None) -> Decimal | None:
        if not value:
            return None
        cleaned = value.replace(",", "").replace("USD", "").strip()
        sign = -1 if cleaned.startswith("-") else 1
        cleaned = cleaned.replace("$", "").replace("-", "")
        try:
            return Decimal(cleaned) * sign
        except (ArithmeticError, ValueError, InvalidOperation):
            logger.warning("Unable to parse money value: %s", value)
            return None
