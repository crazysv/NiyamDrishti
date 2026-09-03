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
async def test_review_db():
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[deps.get_db] = override_get_db

    officer_id = uuid.uuid4()
    other_officer_id = uuid.uuid4()
    supervisor_id = uuid.uuid4()
    insp_id = uuid.uuid4()
    img_id = uuid.uuid4()
    f1_id = uuid.uuid4()
    f2_id = uuid.uuid4()
    f3_id = uuid.uuid4()

    async with async_session() as session:
        # Create users
        officer = User(
            id=officer_id,
            email="officer.verma@gov.in",
            password_hash=get_password_hash("Pass123!"),
            full_name="Officer Verma",
            role="officer",
            region="Delhi-North",
            is_active=True,
        )
        other_officer = User(
            id=other_officer_id,
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
            full_name="Sup. Patel",
            role="supervisor",
            region="Delhi",
            is_active=True,
        )
        session.add_all([officer, other_officer, supervisor])

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
        inspection = Inspection(
            id=insp_id,
            officer_id=officer_id,
            status="needs_review",
            commodity_category="packaged_food",
            rule_pack_version="2026.02.01",
            created_at=datetime.now(timezone.utc),
        )
        session.add(inspection)

        # Image
        image = InspectionImage(
            id=img_id,
            inspection_id=insp_id,
            image_role="front_pdp",
            storage_url="local://sample_tea.jpg",
            width_px=1000,
            height_px=1500,
            calibration_scale_mm_per_px=0.09,
            quality_check_passed=True,
            captured_at=datetime.now(timezone.utc),
        )
        session.add(image)

        # Field 1: High confidence MRP (0.95) -> Pass
        f1 = ExtractedField(
            id=f1_id,
            inspection_id=insp_id,
            source_image_id=img_id,
            field_type="mrp",
            raw_text="MRP Rs 250.00 (Incl. of all taxes)",
            parsed_value="250.00",
            confidence=0.95,
            bounding_box={"x": 200, "y": 300, "w": 250, "h": 60},
            verdict="pass",
            reviewed_by_officer=False,
        )
        # Field 2: Low confidence Net Quantity (0.75 < 0.85 threshold) -> Needs Review (REV-01)
        f2 = ExtractedField(
            id=f2_id,
            inspection_id=insp_id,
            source_image_id=img_id,
            field_type="net_quantity",
            raw_text="Net Wt: 500 g",
            parsed_value="500g",
            confidence=0.75,
            bounding_box={"x": 200, "y": 400, "w": 200, "h": 50},
            verdict="needs_review",
            reviewed_by_officer=False,
        )
        # Field 3: Ambiguous format Commodity Name -> Needs Review
        f3 = ExtractedField(
            id=f3_id,
            inspection_id=insp_id,
            source_image_id=img_id,
            field_type="commodity_name",
            raw_text="PREMIUM CTC LEAF",
            parsed_value="Tea",
            confidence=0.88,
            bounding_box={"x": 200, "y": 200, "w": 400, "h": 80},
            verdict="needs_review",
            reviewed_by_officer=False,
        )
        session.add_all([f1, f2, f3])
        await session.commit()

    yield {
        "session": async_session,
        "inspection_id": insp_id,
        "officer_id": officer_id,
        "other_officer_id": other_officer_id,
        "supervisor_id": supervisor_id,
        "f1_id": f1_id,
        "f2_id": f2_id,
        "f3_id": f3_id,
    }

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_review_queue_routing_and_retrieval(test_review_db):
    """Verify REV-01 review queue surfacing fields with low confidence (< 85%) or format ambiguity."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(test_review_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}
        insp_id = test_review_db["inspection_id"]

        resp = await ac.get(f"/api/v1/inspections/{insp_id}/review-queue", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["inspection_id"] == str(insp_id)
        assert data["total_fields"] == 3
        # f2 (confidence 75%) and f3 (verdict needs_review) are pending review
        assert data["pending_review_count"] == 2
        assert data["completed_review_count"] == 0

        # Verify items
        items = data["items"]
        f2_item = next(i for i in items if i["field_id"] == str(test_review_db["f2_id"]))
        assert f2_item["field_type"] == "net_quantity"
        assert f2_item["confidence"] == 0.75
        assert "75%" in f2_item["flag_reason"]
        assert "85%" in f2_item["flag_reason"]

        f3_item = next(i for i in items if i["field_id"] == str(test_review_db["f3_id"]))
        assert f3_item["field_type"] == "commodity_name"
        assert f3_item["verdict"] == "needs_review"


@pytest.mark.asyncio
async def test_review_override_confirm_action(test_review_db):
    """Verify REV-02 action='confirm' marks field reviewed and verdict='pass'."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(test_review_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}
        insp_id = test_review_db["inspection_id"]
        f2_id = test_review_db["f2_id"]

        payload = {
            "action": "confirm",
            "review_notes": "Visually verified on label: net quantity is 500g.",
        }

        patch_resp = await ac.patch(
            f"/api/v1/inspections/{insp_id}/fields/{f2_id}",
            json=payload,
            headers=headers,
        )
        assert patch_resp.status_code == 200
        res_data = patch_resp.json()

        assert res_data["field"]["id"] == str(f2_id)
        assert res_data["field"]["verdict"] == "pass"
        assert res_data["field"]["reviewed_by_officer"] is True
        assert res_data["field"]["officer_override_value"] is None
        assert "confirmed" in res_data["message"].lower()
        assert res_data["audit_log_id"] is not None


@pytest.mark.asyncio
async def test_review_override_correct_action(test_review_db):
    """Verify REV-02 action='correct' updates officer_override_value and triggers audit log (REV-03)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(test_review_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}
        insp_id = test_review_db["inspection_id"]
        f3_id = test_review_db["f3_id"]

        # 1. Validation test: action 'correct' without override value must fail with 400
        fail_resp = await ac.patch(
            f"/api/v1/inspections/{insp_id}/fields/{f3_id}",
            json={"action": "correct", "officer_override_value": ""},
            headers=headers,
        )
        assert fail_resp.status_code == 400
        assert "required" in fail_resp.json()["detail"].lower()

        # 2. Valid correction: provide corrected commodity name
        valid_payload = {
            "action": "correct",
            "officer_override_value": "Black Tea (CTC Leaf)",
            "review_notes": "Corrected ambiguous label OCR text to standardized commodity declaration.",
        }
        patch_resp = await ac.patch(
            f"/api/v1/inspections/{insp_id}/fields/{f3_id}",
            json=valid_payload,
            headers=headers,
        )
        assert patch_resp.status_code == 200
        data = patch_resp.json()

        assert data["field"]["reviewed_by_officer"] is True
        assert data["field"]["verdict"] == "pass"
        assert data["field"]["officer_override_value"] == "Black Tea (CTC Leaf)"
        assert "Black Tea" in data["message"]


@pytest.mark.asyncio
async def test_review_override_mark_not_applicable(test_review_db):
    """Verify REV-02 action='mark_not_applicable' sets verdict to 'not_applicable'."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(test_review_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}
        insp_id = test_review_db["inspection_id"]
        f3_id = test_review_db["f3_id"]

        patch_resp = await ac.patch(
            f"/api/v1/inspections/{insp_id}/fields/{f3_id}",
            json={"action": "mark_not_applicable", "review_notes": "Exempt commodity variant"},
            headers=headers,
        )
        assert patch_resp.status_code == 200
        data = patch_resp.json()
        assert data["field"]["verdict"] == "not_applicable"
        assert data["field"]["reviewed_by_officer"] is True


@pytest.mark.asyncio
async def test_immutable_audit_log_persisted_and_retrieved(test_review_db):
    """Verify REV-03: audit_logs table contains before/after state, and GET /audit-logs returns chain."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(test_review_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}
        insp_id = test_review_db["inspection_id"]
        f2_id = test_review_db["f2_id"]

        # Perform override
        override_payload = {
            "action": "correct",
            "officer_override_value": "500 g",
            "review_notes": "Added space between magnitude and unit per Rule 9(1).",
        }
        patch_res = await ac.patch(
            f"/api/v1/inspections/{insp_id}/fields/{f2_id}",
            json=override_payload,
            headers=headers,
        )
        assert patch_res.status_code == 200
        audit_id = patch_res.json()["audit_log_id"]

        # Verify audit logs endpoint
        log_resp = await ac.get(f"/api/v1/inspections/{insp_id}/audit-logs", headers=headers)
        assert log_resp.status_code == 200
        logs = log_resp.json()
        assert len(logs) >= 1

        target_log = next(log_item for log_item in logs if log_item["id"] == audit_id)
        assert target_log["action"] == "field_correct"
        assert target_log["entity_type"] == "extracted_field"
        assert target_log["entity_id"] == str(f2_id)
        assert target_log["actor_user_id"] == str(test_review_db["officer_id"])

        # Check before/after values
        before = target_log["before_value"]
        after = target_log["after_value"]
        assert before["verdict"] == "needs_review"
        assert before["reviewed_by_officer"] is False
        assert after["verdict"] == "pass"
        assert after["reviewed_by_officer"] is True
        assert after["officer_override_value"] == "500 g"
        assert after["review_notes"] == "Added space between magnitude and unit per Rule 9(1)."


@pytest.mark.asyncio
async def test_review_authorization_and_isolation(test_review_db):
    """Verify unauthorized officers cannot review other officers' inspections (RBAC)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        other_token = create_access_token(test_review_db["other_officer_id"])
        headers = {"Authorization": f"Bearer {other_token}"}
        insp_id = test_review_db["inspection_id"]
        f2_id = test_review_db["f2_id"]

        # Other officer should be forbidden (403)
        res = await ac.patch(
            f"/api/v1/inspections/{insp_id}/fields/{f2_id}",
            json={"action": "confirm"},
            headers=headers,
        )
        assert res.status_code == 403

        # Supervisor CAN review (authorized override)
        sup_token = create_access_token(test_review_db["supervisor_id"])
        sup_headers = {"Authorization": f"Bearer {sup_token}"}
        sup_res = await ac.patch(
            f"/api/v1/inspections/{insp_id}/fields/{f2_id}",
            json={"action": "confirm"},
            headers=sup_headers,
        )
        assert sup_res.status_code == 200
