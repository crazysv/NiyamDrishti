import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.core.security import create_access_token, get_password_hash
from app.db.session import Base
from app.main import app
from app.models.base import AuditLog, Inspection, User, Violation

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def analytics_test_db():
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[deps.get_db] = override_get_db

    officer1_id = uuid.uuid4()
    officer2_id = uuid.uuid4()
    supervisor_id = uuid.uuid4()

    insp1_id = uuid.uuid4()
    insp2_id = uuid.uuid4()
    insp3_id = uuid.uuid4()

    async with async_session() as session:
        # Users
        officer1 = User(
            id=officer1_id,
            email="officer.verma@gov.in",
            password_hash=get_password_hash("Pass123!"),
            full_name="Officer Verma",
            role="officer",
            region="Delhi-North",
            is_active=True,
        )
        officer2 = User(
            id=officer2_id,
            email="officer.sharma@gov.in",
            password_hash=get_password_hash("Pass123!"),
            full_name="Officer Sharma",
            role="officer",
            region="Delhi-South",
            is_active=True,
        )
        supervisor = User(
            id=supervisor_id,
            email="supervisor.patel@gov.in",
            password_hash=get_password_hash("Pass123!"),
            full_name="Supervisor Patel",
            role="supervisor",
            region="Delhi",
            is_active=True,
        )
        session.add_all([officer1, officer2, supervisor])

        # Inspections
        # 1. Completed without violations (Compliant)
        i1 = Inspection(
            id=insp1_id,
            officer_id=officer1_id,
            status="completed",
            commodity_category="packaged_food",
            rule_pack_version="2026.02.01",
            created_at=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
        )
        # 2. Completed with violations (Non-compliant)
        i2 = Inspection(
            id=insp2_id,
            officer_id=officer1_id,
            status="completed",
            commodity_category="packaged_food",
            rule_pack_version="2026.02.01",
            created_at=datetime(2026, 9, 1, 14, 0, tzinfo=timezone.utc),
        )
        # 3. Needs review
        i3 = Inspection(
            id=insp3_id,
            officer_id=officer2_id,
            status="needs_review",
            commodity_category="cosmetics",
            rule_pack_version="2026.02.01",
            created_at=datetime(2026, 9, 2, 11, 0, tzinfo=timezone.utc),
        )
        session.add_all([i1, i2, i3])

        # Violations on insp2
        v1 = Violation(
            id=uuid.uuid4(),
            inspection_id=insp2_id,
            rule_id="font-size-pdp",
            rule_pack_version="2026.02.01",
            description="Font height below 4.0mm",
            citation="Rule 7(1) Table 1",
            severity="major",
        )
        v2 = Violation(
            id=uuid.uuid4(),
            inspection_id=insp2_id,
            rule_id="mrp_altered_sticker",
            rule_pack_version="2026.02.01",
            description="MRP altered by adhesive sticker",
            citation="Rule 18(2)",
            severity="critical",
        )
        session.add_all([v1, v2])

        # Audit log for officer1
        al = AuditLog(
            id=uuid.uuid4(),
            actor_user_id=officer1_id,
            action="CONFIRM_DECLARATION",
            entity_type="extracted_field",
            entity_id=str(uuid.uuid4()),
            created_at=datetime(2026, 9, 1, 10, 5, tzinfo=timezone.utc),
        )
        session.add(al)

        await session.commit()

    officer_token = create_access_token(officer1_id)
    supervisor_token = create_access_token(supervisor_id)

    yield {
        "officer_headers": {"Authorization": f"Bearer {officer_token}"},
        "supervisor_headers": {"Authorization": f"Bearer {supervisor_token}"},
        "officer1_id": officer1_id,
        "officer2_id": officer2_id,
        "supervisor_id": supervisor_id,
    }

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_analytics_summary_api(analytics_test_db):
    headers = analytics_test_db["supervisor_headers"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/analytics/summary", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_inspections"] == 3
        assert data["completed_inspections"] == 2
        assert data["needs_review_inspections"] == 1
        assert data["compliant_inspections"] == 1
        assert data["violation_inspections"] == 1
        assert data["overall_compliance_rate"] == 50.0
        assert data["total_violations"] == 2
        assert data["critical_violations"] == 1
        assert data["major_violations"] == 1
        assert data["total_audit_overrides"] == 1
        assert data["active_officers_count"] >= 2


@pytest.mark.asyncio
async def test_analytics_compliance_trends_api(analytics_test_db):
    headers = analytics_test_db["supervisor_headers"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/analytics/compliance-trends", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        points = data["points"]
        assert len(points) >= 1
        day1 = next((p for p in points if p["date"] == "2026-09-01"), None)
        assert day1 is not None
        assert day1["total_inspections"] == 2
        assert day1["compliant_count"] == 1
        assert day1["violation_count"] == 1
        assert day1["compliance_rate"] == 50.0


@pytest.mark.asyncio
async def test_analytics_violation_hotspots_api(analytics_test_db):
    headers = analytics_test_db["supervisor_headers"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/analytics/violation-hotspots", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        rules = data["by_rule"]
        assert len(rules) >= 2
        rule_ids = [r["rule_id"] for r in rules]
        assert "font-size-pdp" in rule_ids
        assert "mrp_altered_sticker" in rule_ids

        categories = data["by_category"]
        assert any(c["commodity_category"] == "packaged_food" for c in categories)


@pytest.mark.asyncio
async def test_analytics_officer_throughput_api(analytics_test_db):
    supervisor_headers = analytics_test_db["supervisor_headers"]
    officer_headers = analytics_test_db["officer_headers"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Officer role should receive 403 Forbidden
        forbidden_resp = await ac.get("/api/v1/analytics/officer-throughput", headers=officer_headers)
        assert forbidden_resp.status_code == 403

        # Supervisor role should receive 200 OK with full throughput stats
        resp = await ac.get("/api/v1/analytics/officer-throughput", headers=supervisor_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_active_officers"] >= 2
        officers = data["officers"]
        off1 = next((o for o in officers if o["email"] == "officer.verma@gov.in"), None)
        assert off1 is not None
        assert off1["total_inspections"] == 2
        assert off1["completed_inspections"] == 2
        assert off1["human_overrides_count"] == 1
