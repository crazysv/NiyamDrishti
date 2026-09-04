import os
import time
from contextlib import asynccontextmanager

# Configure low-memory allocation strategies before Paddle/Deep Learning engines initialize
os.environ.setdefault("FLAGS_allocator_strategy", "naive_best_fit")
os.environ.setdefault("FLAGS_fraction_of_gpu_memory_to_use", "0.0")
os.environ.setdefault("FLAGS_eager_delete_tensor_gb", "0.0")

from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.metrics import get_latest_metrics
from app.core.middleware import ObservabilityMiddleware
from app.db.session import check_db_health, init_db

APP_START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="NiyamDrishti API",
    description="Legal Metrology label compliance inspection backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore

app.add_middleware(ObservabilityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    """Prometheus exposition endpoint for scraping system and domain metrics."""
    content, content_type = get_latest_metrics()
    return Response(content=content, media_type=content_type)


@app.get("/health", tags=["Monitoring"])
async def health(db: AsyncSession = Depends(deps.get_db)):
    """Comprehensive health check probe."""
    db_health = await check_db_health(db=db)
    uptime_seconds = round(time.time() - APP_START_TIME, 1)
    is_ok = db_health.get("status") == "connected"
    return {
        "status": "ok" if is_ok else "degraded",
        "env": settings.APP_ENV,
        "version": "0.1.0",
        "uptime_seconds": uptime_seconds,
        "database": db_health,
    }


@app.get("/health/live", tags=["Monitoring"])
async def liveness():
    """Liveness probe: returns HTTP 200 if process is running."""
    return {"status": "alive"}


@app.get("/health/ready", tags=["Monitoring"])
async def readiness(response: Response, db: AsyncSession = Depends(deps.get_db)):
    """Readiness probe: checks database and returns HTTP 503 if disconnected."""
    db_health = await check_db_health(db=db)
    if db_health.get("status") != "connected":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "database": db_health}
    return {"status": "ready", "database": db_health}
