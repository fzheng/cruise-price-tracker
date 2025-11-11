# Cruise Price Tracker

An automated Royal Caribbean watcher that periodically crawls the stateroom booking flow, stores every price breakdown in Postgres, and serves a tiny UI for a price-vs-time visualization.

## Features
- **Playwright crawler** tuned for the provided itinerary URL with bot-evasion headers and banner dismissal.
- **Postgres persistence** with a normalized snapshot table (timestamps, itinerary metadata, fare components, raw scrape payload).
- **FastAPI backend** exposing health, snapshot, chart, and manual crawl endpoints.
- **Interactive dashboard** (Chart.js) to visualize price movements, plus a "run crawl now" button.
- **Range control** to flip the price timeline between hourly, daily, and monthly views on the fly.
- **Scheduler** via APScheduler that reuses the crawler inside the API process at a configurable interval (default 60 min, drop to 30 min if you prefer).
- **Docker-first setup** (`Dockerfile` + `docker-compose.yml`) so Postgres and the app start together.

## Project layout
```
app/
  config.py              # Pydantic settings facade
  crawler/royal_caribbean.py  # Playwright-powered scraper
  database.py            # SQLAlchemy engine/session helpers
  models.py              # ORM models (CruisePriceSnapshot)
  scheduler.py           # APScheduler wrapper
  services/              # CRUD helpers around the snapshot table
  templates/index.html   # Chart.js dashboard
  main.py                # FastAPI entrypoint
```

## Quick start (Docker Compose)
```bash
# 1. Copy env defaults if desired
cp .env.example .env

# 2. Build and start everything (app + Postgres)
docker compose up --build
```
Visit http://localhost:8000 once the crawler completes an initial pass. The dashboard automatically refreshes every few minutes, and you can trigger a manual crawl with the button or via `POST /crawl-now`.
> Tip: the API waits for Postgres to finish booting, but the first crawl only starts after both containers print “Database connection available” and “Scheduler started…” in the logs.

## Web dashboard
- URL: http://localhost:8000 (when running locally) or the host/port you expose in Docker/production.
- The **Latest Snapshot** card shows itinerary metadata, fare breakdown, and the timestamp of the last crawl. Use the “Run crawl now” button to trigger the `/crawl-now` endpoint without leaving the page.
- The **Price vs. Time** chart plots total price so you can visually spot trends. Hover to see the full cruise-fare / discount / taxes breakdown, and use the **Hours / Days / Months** toggle to switch aggregation windows. Data refreshes every few minutes automatically.
- If no data appears yet, hit the button once or call `POST /crawl-now` with curl/Postman; the UI updates as soon as the API returns.

## Local development (without Docker)
```bash
python -m venv .venv
.\.venv\Scripts\activate        # PowerShell
pip install -r requirements.txt
# Start Postgres however you prefer, then export DATABASE_URL
set DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/cruise_prices
uvicorn app.main:app --reload
```
After the server starts, hit `POST /crawl-now` once to seed the database. Each run launches a short-lived Playwright Chromium instance (ensure `playwright install chromium` has been executed on the host once).

## Configuration
All options come from env vars (see `.env.example`):

| Variable | Description | Default |
| --- | --- | --- |
| `TARGET_URL` | Royal Caribbean booking URL to monitor | provided itinerary |
| `DATABASE_URL` | SQLAlchemy/Postgres URL | `postgresql+psycopg2://postgres:postgres@db:5432/cruise_prices` |
| `CRAWL_INTERVAL_MINUTES` | Scheduler cadence (recommend >=30 to avoid blocks) | `60` |
| `ENABLE_SCHEDULER` | Toggle background crawler | `true` |
| `PLAYWRIGHT_HEADLESS` | Run browser headless or visible | `true` |
| `REQUEST_TIMEOUT_MS` | Page load wait (ms) | `120000` |
| `CRAWLER_USER_AGENT` / `CRAWLER_LOCALE` | Headers to mimic a real browser | desktop Chrome |
| `SENDGRID_API_KEY` | API key for sending alert emails | *(none)* |
| `NOTIFICATION_FROM_EMAIL` | From-address shown on alert emails | `alerts@example.com` |

## API surface
| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Lightweight readiness info |
| `GET` | `/snapshots` | Paginated (limit query) snapshots ordered newest to oldest |
| `GET` | `/snapshots/latest` | Most recent snapshot (404 until first crawl) |
| `GET` | `/chart-data` | Time-series payload for the chart (limit query) |
| `GET` | `/notification` | Current alert email |
| `POST` | `/notification` | Save/update the alert email |
| `POST` | `/notification/test` | Send a test email to the saved address |
| `POST` | `/crawl-now` | Runs the crawler immediately, stores, and returns the snapshot |

## Database schema
`cruise_price_snapshots`
- metadata: itinerary name, origin, ship, sail dates, guests, room type/subtype/category
- monetary columns: cruise_fare, discounts, subtotal, taxes_and_fees, total_price, currency_code
- `raw_payload` JSONB preserves the untouched text scraped from the DOM
- `scraped_at` is timezone-aware (UTC)

Run `psql -d cruise_prices -c "\d+ cruise_price_snapshots"` after the service has bootstrapped to inspect the table.

## Operational notes
- The crawler waits for the pricing summary selectors and attempts to close cookie/marketing banners with a best-effort heuristic.
- Royal Caribbean occasionally deploys extra bot detection. If requests start returning the fallback "site is on vacation" splash, consider slowing `CRAWL_INTERVAL_MINUTES`, running the Docker container from a residential network, or refreshing the `CRAWLER_USER_AGENT` value.
- Scheduler lives inside the API process; if you scale to multiple replicas make sure only one has `ENABLE_SCHEDULER=true` to avoid duplicate scrapes.
- If you need to analyze the data outside this service, point any BI tool at the Postgres volume or export via `COPY` directly.

## Next ideas
1. Persist additional room availability rows instead of only the selected cabin.
2. Add anomaly detection/alerts (email/Slack when prices change by +/-X percent).
3. Move crawling into a separate worker container and keep the API stateless.
