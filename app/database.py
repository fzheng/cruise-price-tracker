from contextlib import contextmanager
import logging
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for ORM models."""


engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db():
    """FastAPI dependency that yields a database session."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def wait_for_db(max_attempts: int = 15, delay_seconds: int = 2) -> None:
    """Poll the database until it accepts connections."""

    attempt = 1
    while attempt <= max_attempts:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.info("Database connection available")
            return
        except OperationalError:
            logger.info("Database unavailable (attempt %s/%s); retrying in %ss", attempt, max_attempts, delay_seconds)
            time.sleep(delay_seconds)
            attempt += 1
    raise RuntimeError("Database not available after waiting for readiness")
