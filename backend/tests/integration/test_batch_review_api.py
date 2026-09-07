import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.core.security import create_access_token, get_password_hash
from app.db.session import Base
from app.main import app
from app.models.base import ExtractedField, Inspection, InspectionImage, RulePack, User
from app.services.rules import load_default_rule_pack

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def batch_review_env():
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[deps.get_db] = override_get_db

    officer_id = uuid.uuid4()
    insp_id = uuid.uuid4()
    img_id = uuid.uuid4()
    f1_id = uuid.uuid4()
    f2_id = uuid.uuid4()
    f3_id = uuid.uuid4()

    async with async_session() as session:
        officer = User(
            id=officer_id,
            email="officer.batch@gov.in",
            password_hash=get_password_hash("Pass123!"),
            full_name="Inspector R. Sharma",
            role="officer",
            region="Delhi-Central",
            is_active=True,
        )
        session.add(officer)

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

        inspection = Inspection(
            id=insp_id,
            officer_id=officer_id,
            status="needs_review",
            commodity_category="packaged_food",
            rule_pack_version="2026.02.01",
            created_at=datetime.now(timezone.utc),
        )
        session.add(inspection)

        image = InspectionImage(
            id=img_id,
            inspection_id=insp_id,
            image_role="front_pdp",
            storage_url="local://sample_box.jpg",
            width_px=1200,
            height_px=1600,
            calibration_scale_mm_per_px=0.08,
            quality_check_passed=True,
            captured_at=datetime.now(timezone.utc),
        )
        session.add(image)

        f1 = ExtractedField(
            id=f1_id,
            inspection_id=insp_id,
            source_image_id=img_id,
            field_type="mrp",
            raw_text="MRP Rs 150.00",
            parsed_value="150.00",
            confidence=0.72,
            bounding_box={"x": 100, "y": 200, "w": 200, "h": 50},
            verdict="needs_review",
            reviewed_by_officer=False,
        )
        f2 = ExtractedField(
            id=f2_id,
            inspection_id=insp_id,
            source_image_id=img_id,
            field_type="net_quantity",
            raw_text="Net Wt: 500g",
            parsed_value="500 g",
            confidence=0.68,
            bounding_box={"x": 100, "y": 300, "w": 180, "h": 40},
            verdict="needs_review",
            reviewed_by_officer=False,
        )
        f3 = ExtractedField(
            id=f3_id,
            inspection_id=insp_id,
            source_image_id=img_id,
            field_type="commodity_name",
            raw_text="Cookies",
            parsed_value="Cookies",
            confidence=0.70,
            bounding_box={"x": 100, "y": 400, "w": 220, "h": 45},
            verdict="needs_review",
            reviewed_by_officer=False,
        )
        session.add_all([f1, f2, f3])
        await session.commit()

    token = create_access_token(officer_id)
    headers = {"Authorization": f"Bearer {token}"}

    yield {
        "insp_id": insp_id,
        "f1_id": f1_id,
        "f2_id": f2_id,
        "f3_id": f3_id,
        "headers": headers,
        "officer_name": "Inspector R. Sharma",
    }

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_batch_field_review_and_history_workflow(batch_review_env):
    data = batch_review_env
    insp_id = data["insp_id"]
    f1_id = data["f1_id"]
    f2_id = data["f2_id"]
    headers = data["headers"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Post Batch Review (Confirm MRP, Override Net Quantity)
        batch_payload = {
            "items": [
                {
                    "field_id": str(f1_id),
                    "action": "confirm",
                    "officer_notes": "Confirmed correct MRP",
                },
                {
                    "field_id": str(f2_id),
                    "action": "override",
                    "officer_override_value": "1 kg",
                    "officer_notes": "Corrected packaging quantity from photo",
                },
            ]
        }

        resp = await ac.post(
            f"/api/v1/inspections/{insp_id}/fields/batch-review",
            json=batch_payload,
            headers=headers,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["reviewed_count"] == 2
        assert len(result["audit_log_ids"]) == 2
        assert len(result["updated_fields"]) == 2

        # 2. Query Review History (E2-04)
        hist_resp = await ac.get(
            f"/api/v1/inspections/{insp_id}/review-history",
            headers=headers,
        )
        assert hist_resp.status_code == 200
        history = hist_resp.json()
        assert len(history) >= 2

        actions = [h["action"] for h in history]
        assert "CONFIRM_DECLARATION" in actions
        assert "OVERRIDE_DECLARATION" in actions
        assert history[0]["officer_name"] == data["officer_name"]
        assert history[0]["officer_role"] == "officer"
        assert history[0]["field_type"] in ("mrp", "net_quantity")
