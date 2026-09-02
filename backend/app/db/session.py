"""
Database session — SQLAlchemy async engine.
Uses SQLite for local dev/offline, PostgreSQL (Neon) in production.
Switch is done purely via DATABASE_URL in .env — no code change required.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",
    # SQLite needs check_same_thread=False; for Postgres this kwarg is ignored
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


async def init_db() -> None:
    """Create all tables on startup (dev only — prod uses Alembic migrations)."""
    from app.models import inspection, rule_pack, user  # noqa: F401 — registers models

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        yield session
