"""SQLite database configuration for the Signal Clone API."""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.settings import database_file

DATABASE_PATH = database_file()
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # required for SQLite + FastAPI
)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """SQLite does not enforce foreign keys unless PRAGMA is enabled per connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models."""


def init_db() -> None:
    """Create all tables if they do not already exist."""
    from app import models  # noqa: F401 — register models on Base.metadata

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and close it when the request is done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
