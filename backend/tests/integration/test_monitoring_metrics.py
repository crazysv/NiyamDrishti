"""Integration tests for Prometheus metrics, correlation ID tracing, and health probes (E4-03)."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.core.metrics import (
    record_inspection_completed,
    record_ocr_duration,
    record_offline_sync,
    record_rule_evaluation_duration,
)
from app.db.session import Base
from app.main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[deps.get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint(test_db):
    """Verify /metrics returns 200 with Prometheus text exposition format and core metric keys."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        text = resp.text
        assert "niyamdrishti_http_requests_total" in text
        assert "niyamdrishti_http_request_duration_seconds" in text
        assert "niyamdrishti_active_requests" in text


@pytest.mark.asyncio
async def test_correlation_id_and_metrics_increment(test_db):
    """Verify X-Request-ID correlation tracking and metric increment on API calls."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Without client-provided X-Request-ID: should generate a UUID
        resp1 = await client.get("/health/live")
        assert resp1.status_code == 200
        req_id_1 = resp1.headers.get("X-Request-ID")
        assert req_id_1 is not None
        assert len(req_id_1) > 10

        # 2. With client-provided X-Request-ID: should preserve it
        custom_id = "test-corr-id-xyz-987"
        resp2 = await client.get("/health/live", headers={"X-Request-ID": custom_id})
        assert resp2.status_code == 200
        assert resp2.headers.get("X-Request-ID") == custom_id

        # 3. Check that /metrics reflects the calls
        metrics_resp = await client.get("/metrics")
        assert metrics_resp.status_code == 200
        assert 'endpoint="/health/live"' in metrics_resp.text
        assert 'status_code="200"' in metrics_resp.text


@pytest.mark.asyncio
async def test_route_normalization_avoids_cardinality_explosion(test_db):
    """Verify dynamic UUIDs in paths are parameterized to prevent metric label cardinality explosion."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        test_uuid = str(uuid.uuid4())
        # Call a non-existent inspection endpoint (will 401 or 404)
        resp = await client.get(f"/api/v1/inspections/{test_uuid}")
        assert resp.status_code in [401, 403, 404]

        # Verify metrics recorded normalized route format, not the raw UUID
        metrics_resp = await client.get("/metrics")
        assert metrics_resp.status_code == 200
        # The raw UUID must NOT appear as an endpoint label value
        assert f'endpoint="/api/v1/inspections/{test_uuid}"' not in metrics_resp.text


@pytest.mark.asyncio
async def test_health_probes(test_db):
    """Verify /health, /health/live, and /health/ready probes."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Liveness probe
        live_resp = await client.get("/health/live")
        assert live_resp.status_code == 200
        assert live_resp.json() == {"status": "alive"}

        # Readiness probe
        ready_resp = await client.get("/health/ready")
        assert ready_resp.status_code == 200
        assert ready_resp.json().get("status") == "ready"

        # General health probe
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        data = health_resp.json()
        assert data["status"] == "ok"
        assert "uptime_seconds" in data
        assert data["version"] == "0.1.0"
        assert "database" in data


@pytest.mark.asyncio
async def test_domain_metrics_recorders():
    """Verify domain metric recording helper functions execute safely and populate metrics."""
    record_ocr_duration(1.25, engine="paddleocr", status="success")
    record_rule_evaluation_duration(0.045, rule_pack_version="2026.02.01")
    record_inspection_completed(verdict="compliant", category="packaged_food", is_self_check=False)
    record_offline_sync(entity_type="inspection", status="synced", count=2)
    record_offline_sync(entity_type="image", status="conflict", count=1)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        text = resp.text
        assert "niyamdrishti_ocr_processing_duration_seconds" in text
        assert "niyamdrishti_rule_evaluation_duration_seconds" in text
        assert "niyamdrishti_inspections_total" in text
        assert "niyamdrishti_offline_sync_operations_total" in text
        assert 'overall_verdict="compliant"' in text
        assert 'commodity_category="packaged_food"' in text
        assert 'status="conflict"' in text
