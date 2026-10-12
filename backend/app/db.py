"""SQLAlchemy engine/session. PostgreSQL stores users, encrypted Gemini keys and documents.
Tables are created by Alembic migrations (`alembic upgrade head`), not by the app."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # drop dead connections (DB restarts, idle timeouts) instead of erroring
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()