"""
Integration tests for Manufacturer / Packer Self-Check Mode (E3-06, 01_PRD.md NG4, 06_SCHEMA.md).
Verifies:
1. Self-check creation, retrieval, and scorecard with remediation advice.
2. Structural data isolation: self-checks are NEVER included in official enforcement analytics or default inspection searches.
3. Manufacturer summary statistics.
"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.core.security import create_access_token, get_password_hash
from app.db.session import Base
from app.main import app
from app.models.base import ExtractedField, Inspection, User, Violation

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def self_check_test_db():
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    manufacturer_id = uuid.uuid4()
    officer_id = uuid.uuid4()
    supervisor_id = uuid.uuid4()

    async with async_session() as session:
        # Manufacturer user conducting self-checks
        mfr = User(
            id=manufacturer_id,
            email="qa@nestle-pack.com",
            password_hash=get_password_hash("Secret123!"),
            full_name="Packaging QA Lead",
            role="officer",
            region="Packaging Lab A",
            is_active=True,
        )
        # Enforcement Officer
        officer = User(
            id=officer_id,
            email="enf_officer@gov.in",
            password_hash=get_password_hash("Secret123!"),
            full_name="Enforcement Officer",
            role="officer",
            region="Delhi-North",
            is_active=True,
        )
        # Supervisor
        supervisor = User(
            id=supervisor_id,
            email="supervisor@gov.in",
            password_hash=get_password_hash("Secret123!"),
            full_name="Enforcement Supervisor",
            role="supervisor",
            region="Delhi-North",
            is_active=True,
        )
        session.add_all([mfr, officer, supervisor])
        await session.commit()

    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[deps.get_db] = override_get_db
    yield {
        "mfr_id": manufacturer_id,
        "officer_id": officer_id,
        "supervisor_id": supervisor_id,
        "async_session": async_session,
    }
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_and_list_self_checks(self_check_test_db):
    """Verify creating a self-check inspection and listing under self-check endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(self_check_test_db["mfr_id"])
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create self check
        resp = await ac.post(
            "/api/v1/self-check/inspections",
            json={
                "commodity_category": "packaged_food",
                "brand_name": "NutriCrunch",
                "product_name": "Almond Cookies 200g",
                "batch_or_lot_number": "LOT-2026-09",
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["is_self_check"] is True
        assert data["commodity_category"] == "packaged_food"
        insp_id = data["id"]

        # 2. List self checks
        list_resp = await ac.get("/api/v1/self-check/inspections", headers=headers)
        assert list_resp.status_code == 200
        items = list_resp.json()
        assert len(items) == 1
        assert items[0]["id"] == insp_id
        assert items[0]["is_self_check"] is True


@pytest.mark.asyncio
async def test_self_check_scorecard_and_remediation(self_check_test_db):
    """Verify scorecard generation and constructive remediation guidance."""
    transport = ASGITransport(app=app)
    mfr_id = self_check_test_db["mfr_id"]
    async_session = self_check_test_db["async_session"]

    insp_id = uuid.uuid4()
    field_id = uuid.uuid4()

    async with async_session() as session:
        insp = Inspection(
            id=insp_id,
            officer_id=mfr_id,
            commodity_category="packaged_food",
            rule_pack_version="2024.1",
            status="completed",
            is_self_check=True,
            captured_offline=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        field = ExtractedField(
            id=field_id,
            inspection_id=insp_id,
            source_image_id=uuid.uuid4(),
            field_type="mrp",
            raw_text="Rs. 99",
            parsed_value="99",
            confidence=0.95,
            bounding_box={"x": 10, "y": 10, "w": 50, "h": 20},
            verdict="fail",
            reviewed_by_officer=False,
            created_at=datetime.now(timezone.utc),
        )
        viol = Violation(
            id=uuid.uuid4(),
            inspection_id=insp_id,
            extracted_field_id=field_id,
            rule_id="RULE-005-MRP",
            rule_pack_version="2024.1",
            description="MRP is missing mandatory '(inclusive of all taxes)' declaration",
            citation="Rule 6(1)(e)",
            severity="major",
            created_at=datetime.now(timezone.utc),
        )
        session.add_all([insp, field, viol])
        await session.commit()

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(mfr_id)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await ac.get(f"/api/v1/self-check/inspections/{insp_id}/scorecard", headers=headers)
        assert resp.status_code == 200, resp.text
        card = resp.json()

        assert card["inspection_id"] == str(insp_id)
        assert card["overall_readiness"] == "ACTION_REQUIRED"
        assert card["total_declarations_checked"] == 1
        assert card["violation_count"] == 1
        assert card["compliant_count"] == 0
        assert card["readiness_percentage"] == 0.0
        assert len(card["remediations"]) == 1
        assert "inclusive of all taxes" in card["remediations"][0]["remedial_action"]
        assert "DOES NOT CONSTITUTE A FORMAL REGULATORY INSPECTION" in card["disclaimer"]


@pytest.mark.asyncio
async def test_self_check_structural_isolation_from_enforcement(self_check_test_db):
    """
    CRITICAL SPEC TEST (01_PRD.md NG4, 06_SCHEMA.md):
    Guarantee that self-check inspections are structurally isolated:
    1. Excluded from default enforcement search (GET /api/v1/inspections).
    2. Excluded from supervisory analytics summary (GET /api/v1/analytics/summary).
    3. Excluded from compliance trends (GET /api/v1/analytics/compliance-trends).
    4. Excluded from violation hotspots (GET /api/v1/analytics/violation-hotspots).
    """
    transport = ASGITransport(app=app)
    mfr_id = self_check_test_db["mfr_id"]
    officer_id = self_check_test_db["officer_id"]
    supervisor_id = self_check_test_db["supervisor_id"]
    async_session = self_check_test_db["async_session"]

    async with async_session() as session:
        # 1. Official Enforcement Inspection (completed, 0 violations -> compliant)
        official_insp = Inspection(
            id=uuid.uuid4(),
            officer_id=officer_id,
            commodity_category="edible_oil",
            rule_pack_version="2024.1",
            status="completed",
            is_self_check=False,
            captured_offline=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        # 2. Manufacturer Self-Check (completed, 2 violations -> should NOT contaminate enforcement stats)
        self_check_insp = Inspection(
            id=uuid.uuid4(),
            officer_id=mfr_id,
            commodity_category="packaged_food",
            rule_pack_version="2024.1",
            status="completed",
            is_self_check=True,
            captured_offline=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self_viol = Violation(
            id=uuid.uuid4(),
            inspection_id=self_check_insp.id,
            rule_id="RULE-SELF-MOCK",
            rule_pack_version="2024.1",
            description="Self-check test deficiency",
            citation="Rule 6(1)(a)",
            severity="critical",
            created_at=datetime.now(timezone.utc),
        )
        session.add_all([official_insp, self_check_insp, self_viol])
        await session.commit()

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        sup_token = create_access_token(supervisor_id)
        sup_headers = {"Authorization": f"Bearer {sup_token}"}

        # 1. Enforcement Search: Default must only return official inspection (is_self_check=False)
        search_resp = await ac.get("/api/v1/inspections", headers=sup_headers)
        assert search_resp.status_code == 200
        search_data = search_resp.json()
        assert search_data["total"] == 1
        assert search_data["items"][0]["id"] == str(official_insp.id)
        assert search_data["items"][0]["is_self_check"] is False

        # 2. Analytics Summary: Must show 1 total inspection, 100% compliance rate, 0 violations!
        # If self-check leaked, total_inspections would be 2 and compliance rate would drop!
        summary_resp = await ac.get("/api/v1/analytics/summary", headers=sup_headers)
        assert summary_resp.status_code == 200
        stats = summary_resp.json()
        assert stats["total_inspections"] == 1
        assert stats["compliant_inspections"] == 1
        assert stats["violation_inspections"] == 0
        assert stats["overall_compliance_rate"] == 100.0
        assert stats["total_violations"] == 0
        assert stats["critical_violations"] == 0

        # 3. Violation Hotspots: Must NOT list RULE-SELF-MOCK
        hotspots_resp = await ac.get("/api/v1/analytics/violation-hotspots", headers=sup_headers)
        assert hotspots_resp.status_code == 200
        hotspots = hotspots_resp.json()
        rule_ids = [r["rule_id"] for r in hotspots["by_rule"]]
        assert "RULE-SELF-MOCK" not in rule_ids


@pytest.mark.asyncio
async def test_self_check_summary_stats(self_check_test_db):
    """Verify aggregate summary statistics for the manufacturer portal."""
    transport = ASGITransport(app=app)
    mfr_id = self_check_test_db["mfr_id"]
    async_session = self_check_test_db["async_session"]

    async with async_session() as session:
        # 1 compliant self-check
        sc1 = Inspection(
            id=uuid.uuid4(),
            officer_id=mfr_id,
            commodity_category="beverages",
            rule_pack_version="2024.1",
            status="completed",
            is_self_check=True,
            captured_offline=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        # 1 non-compliant self-check
        sc2 = Inspection(
            id=uuid.uuid4(),
            officer_id=mfr_id,
            commodity_category="beverages",
            rule_pack_version="2024.1",
            status="completed",
            is_self_check=True,
            captured_offline=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        viol = Violation(
            id=uuid.uuid4(),
            inspection_id=sc2.id,
            rule_id="RULE-NET-QTY",
            rule_pack_version="2024.1",
            description="Net quantity font size below threshold",
            citation="Rule 7",
            severity="minor",
            created_at=datetime.now(timezone.utc),
        )
        session.add_all([sc1, sc2, viol])
        await session.commit()

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(mfr_id)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await ac.get("/api/v1/self-check/summary", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_self_checks"] == 2
        assert data["market_ready_count"] == 1
        assert data["action_required_count"] == 1
        assert data["first_pass_rate"] == 50.0
        assert len(data["common_deficiencies"]) == 1
        assert data["common_deficiencies"][0]["rule_id"] == "RULE-NET-QTY"
