import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.core.security import create_access_token, get_password_hash
from app.db.session import Base
from app.main import app
from app.models.base import ExtractedField, Inspection, InspectionImage, RulePack, User, Violation
from app.services.rules import load_default_rule_pack

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_evidence_db():
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[deps.get_db] = override_get_db

    officer_id = uuid.uuid4()

    async with async_session() as session:
        officer = User(
            id=officer_id,
            email="inspector.singh@gov.in",
            password_hash=get_password_hash("InspectPass123!"),
            full_name="Insp. K. Singh",
            role="officer",
            region="Delhi-West",
            is_active=True,
        )
        session.add(officer)

        # Active rule pack
        default_pack = load_default_rule_pack()
        rule_pack = RulePack(
            version="2026.02.01",
            effective_from=datetime(2026, 2, 1, tzinfo=timezone.utc),
            source_citation="LM(PC) Rules 2011",
            rules_json=default_pack.model_dump(mode="json"),
            is_active=True,
            created_by=officer_id,
        )
        session.add(rule_pack)

        # Inspection
        insp_id = uuid.uuid4()
        inspection = Inspection(
            id=insp_id,
            officer_id=officer_id,
            status="draft",
            commodity_category="packaged_food",
            rule_pack_version="2026.02.01",
            created_at=datetime.now(timezone.utc),
        )
        session.add(inspection)

        # Front PDP image with optical calibration scale (0.08 mm/px)
        img_id = uuid.uuid4()
        image = InspectionImage(
            id=img_id,
            inspection_id=insp_id,
            image_role="front_pdp",
            storage_url="local://sample_basmati.jpg",
            width_px=1000,
            height_px=1500,
            calibration_scale_mm_per_px=0.08,
            quality_check_passed=True,
            captured_at=datetime.now(timezone.utc),
        )
        session.add(image)

        # Extracted fields: MRP (E01), Net Quantity (E02), Date of Mfg (E03 with review)
        f1 = ExtractedField(
            id=uuid.uuid4(),
            inspection_id=insp_id,
            source_image_id=img_id,
            field_type="mrp",
            raw_text="MRP: ₹125.00 (Incl. of all taxes)",
            parsed_value="125.00",
            confidence=0.94,
            bounding_box={"x": 260, "y": 465, "w": 220, "h": 75},
            verdict="pass",
            reviewed_by_officer=False,
        )
        f2 = ExtractedField(
            id=uuid.uuid4(),
            inspection_id=insp_id,
            source_image_id=img_id,
            field_type="net_quantity",
            raw_text="Net Qty: 1 kg",
            parsed_value="1 kg",
            confidence=0.97,
            bounding_box={"x": 260, "y": 570, "w": 280, "h": 75},
            verdict="pass",
            reviewed_by_officer=False,
        )
        f3 = ExtractedField(
            id=uuid.uuid4(),
            inspection_id=insp_id,
            source_image_id=img_id,
            field_type="mfg_date",
            raw_text="15 OCT 2023",
            parsed_value="10/2023",
            confidence=0.78,
            bounding_box={"x": 260, "y": 660, "w": 420, "h": 90},
            verdict="needs_review",
            reviewed_by_officer=False,
        )
        session.add_all([f1, f2, f3])
        await session.commit()

    yield {"session": async_session, "inspection_id": insp_id, "officer_id": officer_id}

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_inspection_evidence_mapping(test_evidence_db):
    """Verify EVID-01 visual evidence mapping structure and normalized bounding boxes."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(test_evidence_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}
        insp_id = test_evidence_db["inspection_id"]

        # First evaluate to populate violations (EVID-02)
        eval_resp = await ac.post(f"/api/v1/inspections/{insp_id}/evaluate", headers=headers)
        assert eval_resp.status_code == 200

        # Call GET /api/v1/inspections/{id}/evidence (EVID-01)
        resp = await ac.get(f"/api/v1/inspections/{insp_id}/evidence", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["inspection_id"] == str(insp_id)
        assert data["officer_name"] == "Insp. K. Singh"
        assert data["rule_pack_version"] == "2026.02.01"
        assert data["primary_image_dimensions"]["width"] == 1000
        assert data["primary_image_dimensions"]["height"] == 1500

        # Check evidence items
        items = data["items"]
        assert len(items) == 3

        # E01: MRP
        e01 = items[0]
        assert e01["item_id"] == "E01"
        assert e01["field_type"] == "mrp"
        assert e01["field_label"] == "MRP"
        assert e01["verdict"] == "pass"
        # Check normalized percentage coordinates for Stitch overlay: x=260/1000 = 26%, y=465/1500 = 31%
        bbox = e01["bounding_box"]
        assert bbox["left_pct"] == 26.0
        assert bbox["top_pct"] == 31.0
        assert bbox["width_pct"] == 22.0
        assert bbox["height_pct"] == 5.0

        # E02: Net Quantity with calibrated font height
        e02 = items[1]
        assert e02["item_id"] == "E02"
        assert e02["is_calibrated"] is True
        assert e02["measured_dimension"] is not None
        assert e02["measured_dimension"]["scale_mm_per_px"] == 0.08
        # h=75px * 0.08 = 6.0mm
        assert e02["measured_dimension"]["height_mm"] == 6.0

        # E03: Mfg Date with review requirement
        e03 = items[2]
        assert e03["item_id"] == "E03"
        assert e03["verdict"] == "needs_review"

        # Check stats
        stats = data["stats"]
        assert stats["total"] == 3
        assert stats["passed"] == 2
        assert stats["review"] == 1


@pytest.mark.asyncio
async def test_violations_persisted_in_db(test_evidence_db):
    """Verify EVID-02 violations table population."""
    async with test_evidence_db["session"]() as session:
        insp_id = test_evidence_db["inspection_id"]
        # Prior to evaluation, verify violations can be populated via POST /evaluate
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            token = create_access_token(test_evidence_db["officer_id"])
            await ac.post(f"/api/v1/inspections/{insp_id}/evaluate", headers={"Authorization": f"Bearer {token}"})

        # Query violations directly from database
        stmt = select(Violation).where(Violation.inspection_id == insp_id)
        violations = list((await session.execute(stmt)).scalars().all())
        assert len(violations) > 0
        # Missing manufacturer address or missing consumer care is flagged as critical/major
        v_rules = [v.rule_id for v in violations]
        assert "declaration-present-manufacturer-address" in v_rules
        assert "declaration-present-consumer-care" in v_rules
