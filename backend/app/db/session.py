"""
Database session — SQLAlchemy async engine.
Uses SQLite for local dev/offline, PostgreSQL (Neon) in production (STOR-02).
Switch is done purely via DATABASE_URL in .env — no code change required.
"""

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


def normalize_database_url(raw_url: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """
    Normalizes database connection strings for SQLAlchemy async engine (STOR-02).
    - Converts postgres:// and postgresql:// to postgresql+asyncpg://
    - Configures Neon serverless connection pool parameters (pool_pre_ping, pool_recycle)
    - Sets up SQLite check_same_thread=False for local dev/offline
    """
    if not raw_url:
        raw_url = "sqlite+aiosqlite:///./niyamdrishti.db"

    # Handle SQLite
    if "sqlite" in raw_url:
        return (
            raw_url,
            {"connect_args": {"check_same_thread": False}},
            {},
        )

    # Handle PostgreSQL / Neon
    parsed = urlparse(raw_url)
    scheme = parsed.scheme

    if scheme in ("postgres", "postgresql", "postgresql+psycopg2"):
        scheme = "postgresql+asyncpg"

    # Filter out query params not supported directly by asyncpg in URL
    query_params = dict(parse_qsl(parsed.query))
    connect_args: dict[str, Any] = {}

    if "sslmode" in query_params:
        # asyncpg prefers ssl parameter in connect_args
        mode = query_params.pop("sslmode")
        if mode in ("require", "verify-ca", "verify-full"):
            connect_args["ssl"] = True

    # asyncpg does not support channel_binding query parameter
    query_params.pop("channel_binding", None)

    new_query = urlencode(query_params)
    normalized_url = urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

    # Neon serverless pool settings:
    # pool_pre_ping: vital for Neon scale-to-zero idle connection drops
    # pool_recycle: 300s matches Neon 5min compute idle timeout
    engine_kwargs: dict[str, Any] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 10,
        "max_overflow": 20,
        "connect_args": connect_args,
    }

    return normalized_url, engine_kwargs, connect_args


DB_URL, ENGINE_KWARGS, _ = normalize_database_url(settings.DATABASE_URL)

engine = create_async_engine(
    DB_URL,
    echo=settings.APP_ENV == "development",
    **ENGINE_KWARGS,
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


async def check_db_health() -> dict[str, Any]:
    """Checks database connection liveness with retry for serverless wake-up (STOR-02)."""
    last_exc = None
    for _ in range(2):
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            return {
                "status": "connected",
                "dialect": engine.dialect.name,
                "is_serverless_ready": True,
            }
        except Exception as exc:
            last_exc = exc
    return {
        "status": "error",
        "dialect": engine.dialect.name,
        "error": str(last_exc),
    }
