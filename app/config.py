from functools import lru_cache
from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_TARGET_URL = (
    "https://www.royalcaribbean.com/room-selection/room-location?groupId=UT04PCN-4069341576"
    "&packageCode=UT4BH269&sailDate=2026-02-16&country=USA&selectedCurrencyCode=USD"
    "&shipCode=UT&cabinClassType=BALCONY&roomIndex=0&r0a=2&r0c=2&r0b=n&r0r=n&r0s=n"
    "&r0q=n&r0t=n&r0d=BALCONY&r0D=y&rgVisited=true&r0C=y&r0e=D&r0f=3D&r0J=n"
)


class Settings(BaseSettings):
    """Application configuration sourced from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="Cruise Price Tracker")
    target_url: HttpUrl = Field(default=DEFAULT_TARGET_URL, validation_alias="TARGET_URL")
    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@db:5432/cruise_prices",
        validation_alias="DATABASE_URL",
    )
    crawl_interval_minutes: int = Field(default=60, ge=5, le=1440, validation_alias="CRAWL_INTERVAL_MINUTES")
    scheduler_timezone: str = Field(default="UTC", validation_alias="SCHEDULER_TIMEZONE")
    headless: bool = Field(default=True, validation_alias="PLAYWRIGHT_HEADLESS")
    request_timeout_ms: int = Field(default=120000, validation_alias="REQUEST_TIMEOUT_MS")
    user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        validation_alias="CRAWLER_USER_AGENT",
    )
    locale: str = Field(default="en-US", validation_alias="CRAWLER_LOCALE")
    enable_scheduler: bool = Field(default=True, validation_alias="ENABLE_SCHEDULER")
    sendgrid_api_key: str | None = Field(default=None, validation_alias="SENDGRID_API_KEY")
    notification_from_email: str = Field(
        default="alerts@example.com", validation_alias="NOTIFICATION_FROM_EMAIL"
    )


@lru_cache
def get_settings() -> "Settings":
    """Return a cached Settings instance."""

    return Settings()


settings = get_settings()
