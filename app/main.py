from __future__ import annotations

import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.requests import Request

from .config import settings
from .database import Base, engine, get_db, wait_for_db
from .crawler.royal_caribbean import RoyalCaribbeanCrawler
from .scheduler import scheduler
from .schemas import ChartPoint, CruiseSnapshot
from .services import snapshot_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.on_event("startup")
def on_startup() -> None:
    """Create database tables and start background scheduler."""

    logger.info("Creating database tables (if needed)")
    wait_for_db()
    Base.metadata.create_all(bind=engine)
    scheduler.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    scheduler.shutdown()


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    context = {
        "request": request,
        "app_name": settings.app_name,
        "crawl_interval": settings.crawl_interval_minutes,
    }
    return TEMPLATES.TemplateResponse("index.html", context)


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str | bool | None]:
    latest = snapshot_service.get_latest_snapshot(db)
    return {
        "status": "ok",
        "latest_snapshot": latest.scraped_at.isoformat() if latest else None,
        "has_snapshot": latest is not None,
    }


@app.get("/snapshots", response_model=list[CruiseSnapshot])
def list_snapshots(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[CruiseSnapshot]:
    return snapshot_service.get_snapshots(db, limit)


@app.get("/snapshots/latest", response_model=CruiseSnapshot)
def latest_snapshot(db: Session = Depends(get_db)) -> CruiseSnapshot:
    snapshot = snapshot_service.get_latest_snapshot(db)
    if not snapshot:
        raise HTTPException(status_code=404, detail="No snapshots found")
    return snapshot


WINDOW_OPTIONS = {"hours", "days", "months"}


@app.get("/chart-data", response_model=list[ChartPoint])
def chart_data(
    limit: int = Query(default=240, ge=10, le=2000),
    window: str = Query(default="hours"),
    db: Session = Depends(get_db),
) -> list[ChartPoint]:
    normalized = window.lower()
    if normalized not in WINDOW_OPTIONS:
        raise HTTPException(status_code=400, detail="Invalid window. Use hours, days, or months.")
    return snapshot_service.get_chart_points(db, limit, normalized)


@app.post("/crawl-now", response_model=CruiseSnapshot, status_code=status.HTTP_201_CREATED)
def crawl_now(db: Session = Depends(get_db)) -> CruiseSnapshot:
    crawler = RoyalCaribbeanCrawler()
    snapshot = snapshot_service.create_snapshot(db, crawler.scrape())
    return snapshot


__all__ = ["app"]
