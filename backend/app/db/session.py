from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    """Provide a database session for the duration of a request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def check_database_connection() -> None:
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))
