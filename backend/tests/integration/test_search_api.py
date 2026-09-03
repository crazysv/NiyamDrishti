import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.core.security import create_access_token, get_password_hash
from app.db.session import Base
from app.main import app
from app.models.base import ExtractedField, Inspection, InspectionImage, RulePack, User, Violation
from app.services.rules import load_default_rule_pack

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_search_db():
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

    now = datetime.now(timezone.utc)

    async with async_session() as session:
        # 1. Users
        officer1 = User(
            id=officer1_id,
            email="officer1@gov.in",
            password_hash=get_password_hash("Pass123!"),
            full_name="Officer Ramesh",
            role="officer",
            region="Delhi-North",
            is_active=True,
        )
        officer2 = User(
            id=officer2_id,
            email="officer2@gov.in",
            password_hash=get_password_hash("Pass123!"),
            full_name="Officer Suresh",
            role="officer",
            region="Mumbai-Central",
            is_active=True,
        )
        supervisor = User(
            id=supervisor_id,
            email="supervisor@gov.in",
            password_hash=get_password_hash("Pass123!"),
            full_name="Supervisor Gupta",
            role="supervisor",
            region="Central",
            is_active=True,
        )
        session.add_all([officer1, officer2, supervisor])

        # 2. Rule Pack
        default_pack = load_default_rule_pack()
        rule_pack = RulePack(
            version="2026.02.01",
            effective_from=datetime(2026, 2, 1, tzinfo=timezone.utc),
            source_citation="LM(PC) Rules 2011",
            rules_json=default_pack.model_dump(mode="json"),
            is_active=True,
            created_by=officer1_id,
        )
        session.add(rule_pack)

        # 3. Inspections
        # Insp 1: Officer 1, Packaged Food, Completed, Has Violation (MRP), Delhi-North
        insp1 = Inspection(
            id=insp1_id,
            officer_id=officer1_id,
            status="completed",
            commodity_category="packaged_food",
            rule_pack_version="2026.02.01",
            region="Delhi-North",
            created_at=now - timedelta(days=2),
        )
        # Insp 2: Officer 1, Electronics, Needs Review, No Violation, Delhi-North
        insp2 = Inspection(
            id=insp2_id,
            officer_id=officer1_id,
            status="needs_review",
            commodity_category="electronics",
            rule_pack_version="2026.02.01",
            region="Delhi-North",
            created_at=now - timedelta(days=1),
        )
        # Insp 3: Officer 2, Packaged Food, Completed, No Violation, Mumbai-Central
        insp3 = Inspection(
            id=insp3_id,
            officer_id=officer2_id,
            status="completed",
            commodity_category="packaged_food",
            rule_pack_version="2026.02.01",
            region="Mumbai-Central",
            created_at=now,
        )
        session.add_all([insp1, insp2, insp3])

        # 4. Images
        img1 = InspectionImage(
            id=uuid.uuid4(),
            inspection_id=insp1_id,
            image_role="front_pdp",
            storage_url="local://sample1.jpg",
            width_px=1200,
            height_px=1600,
            captured_at=now,
        )
        session.add(img1)

        # 5. Extracted Fields
        f1 = ExtractedField(
            id=uuid.uuid4(),
            inspection_id=insp1_id,
            source_image_id=img1.id,
            field_type="commodity_name",
            raw_text="Basmati Premium Rice",
            parsed_value="Basmati Rice",
            confidence=0.96,
            bounding_box={"x": 50, "y": 50, "w": 200, "h": 40},
            verdict="pass",
            reviewed_by_officer=True,
        )
        session.add(f1)

        # 6. Violation for Insp 1
        v1 = Violation(
            id=uuid.uuid4(),
            inspection_id=insp1_id,
            extracted_field_id=f1.id,
            rule_id="mrp-missing-inclusive-taxes",
            rule_pack_version="2026.02.01",
            description="MRP is missing mandatory statutory inclusive of taxes declaration.",
            citation="LM(PC) Rule 6(1)(e)",
            severity="major",
        )
        session.add(v1)

        await session.commit()

    yield {
        "session": async_session,
        "officer1_id": officer1_id,
        "officer2_id": officer2_id,
        "supervisor_id": supervisor_id,
        "insp1_id": insp1_id,
        "insp2_id": insp2_id,
        "insp3_id": insp3_id,
    }

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_officer_scoped_search(test_search_db):
    """Verify regular officers only receive their own inspections (SRCH-01 RBAC)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token1 = create_access_token(test_search_db["officer1_id"])
        headers1 = {"Authorization": f"Bearer {token1}"}

        resp = await ac.get("/api/v1/inspections", headers=headers1)
        assert resp.status_code == 200
        data = resp.json()

        assert data["total"] == 2
        returned_ids = {item["id"] for item in data["items"]}
        assert str(test_search_db["insp1_id"]) in returned_ids
        assert str(test_search_db["insp2_id"]) in returned_ids
        assert str(test_search_db["insp3_id"]) not in returned_ids


@pytest.mark.asyncio
async def test_supervisor_search_and_filters(test_search_db):
    """Verify supervisors can search across all officers with multi-parameter filtering (SRCH-01)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        sup_token = create_access_token(test_search_db["supervisor_id"])
        headers = {"Authorization": f"Bearer {sup_token}"}

        # 1. Total across all officers
        resp_all = await ac.get("/api/v1/inspections", headers=headers)
        assert resp_all.status_code == 200
        assert resp_all.json()["total"] == 3

        # 2. Filter by status
        resp_status = await ac.get("/api/v1/inspections?status=needs_review", headers=headers)
        assert resp_status.status_code == 200
        data_status = resp_status.json()
        assert data_status["total"] == 1
        assert data_status["items"][0]["id"] == str(test_search_db["insp2_id"])

        # 3. Filter by region
        resp_region = await ac.get("/api/v1/inspections?region=Mumbai", headers=headers)
        assert resp_region.status_code == 200
        assert resp_region.json()["total"] == 1
        assert resp_region.json()["items"][0]["id"] == str(test_search_db["insp3_id"])

        # 4. Filter by commodity category
        resp_cat = await ac.get("/api/v1/inspections?commodity_category=packaged_food", headers=headers)
        assert resp_cat.status_code == 200
        assert resp_cat.json()["total"] == 2

        # 5. Filter by presence of violations
        resp_viols = await ac.get("/api/v1/inspections?has_violations=true", headers=headers)
        assert resp_viols.status_code == 200
        data_viols = resp_viols.json()
        assert data_viols["total"] == 1
        assert data_viols["items"][0]["id"] == str(test_search_db["insp1_id"])
        assert data_viols["items"][0]["violations_count"] == 1
        assert data_viols["items"][0]["overall_verdict"] == "non_compliant"

        # 6. Filter by violation type substring
        resp_viol_type = await ac.get("/api/v1/inspections?violation_type=mrp", headers=headers)
        assert resp_viol_type.status_code == 200
        assert resp_viol_type.json()["total"] == 1

        # 7. Filter by product query in extracted fields
        resp_prod = await ac.get("/api/v1/inspections?product_query=Basmati", headers=headers)
        assert resp_prod.status_code == 200
        assert resp_prod.json()["total"] == 1
        assert resp_prod.json()["items"][0]["id"] == str(test_search_db["insp1_id"])
