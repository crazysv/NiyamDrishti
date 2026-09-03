import json
import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.core.security import create_access_token, get_password_hash
from app.db.session import Base
from app.main import app
from app.models.base import ExtractedField, Inspection, InspectionImage, RulePack, User, Violation
from app.services.reporting.disclaimer import (
    MANDATORY_LEGAL_DISCLAIMER_TEXT,
    MANDATORY_LEGAL_DISCLAIMER_TITLE,
)
from app.services.rules import load_default_rule_pack

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_reporting_db():
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
    v1_id = uuid.uuid4()

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
            status="completed",
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
            storage_url="local://sample_rice.jpg",
            width_px=1200,
            height_px=1600,
            calibration_scale_mm_per_px=0.085,
            quality_check_passed=True,
            captured_at=datetime.now(timezone.utc),
        )
        session.add(image)

        # Extracted fields
        f1 = ExtractedField(
            id=f1_id,
            inspection_id=insp_id,
            source_image_id=img_id,
            field_type="net_quantity",
            raw_text="Net Wt: 1 kg",
            parsed_value="1kg",
            confidence=0.92,
            bounding_box={"x": 100, "y": 200, "w": 300, "h": 50},
            verdict="pass",
            reviewed_by_officer=True,
            officer_override_value="1 kg",
        )
        f2 = ExtractedField(
            id=f2_id,
            inspection_id=insp_id,
            source_image_id=img_id,
            field_type="mrp",
            raw_text="MRP Rs 180",
            parsed_value="180",
            confidence=0.78,
            bounding_box={"x": 100, "y": 300, "w": 250, "h": 40},
            verdict="fail",
            reviewed_by_officer=False,
        )
        session.add_all([f1, f2])

        # Violation
        v1 = Violation(
            id=v1_id,
            inspection_id=insp_id,
            extracted_field_id=f2_id,
            rule_id="mrp-mandatory-declaration",
            rule_pack_version="2026.02.01",
            description="MRP missing mandatory statutory qualifier '(inclusive of all taxes)'.",
            citation="LM(PC) Rule 6(1)(e)",
            severity="major",
        )
        session.add(v1)
        await session.commit()

    yield {
        "session": async_session,
        "inspection_id": insp_id,
        "officer_id": officer_id,
        "other_officer_id": other_officer_id,
        "supervisor_id": supervisor_id,
        "f1_id": f1_id,
        "f2_id": f2_id,
        "v1_id": v1_id,
    }

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_generate_pdf_report_and_unomittable_disclaimer(test_reporting_db):
    """Verify RPT-01 and RPT-02: PDF report generation embeds mandatory statutory disclaimer."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(test_reporting_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}
        insp_id = test_reporting_db["inspection_id"]

        resp = await ac.post(f"/api/v1/inspections/{insp_id}/report?format=pdf", headers=headers)
        assert resp.status_code == 201
        report_data = resp.json()

        assert report_data["inspection_id"] == str(insp_id)
        assert report_data["format"] == "pdf"
        assert report_data["storage_url"] is not None
        assert report_data["download_url"] is not None

        # Verify downloading the report file (RPT-03)
        file_resp = await ac.get(report_data["download_url"], headers=headers)
        assert file_resp.status_code == 200
        assert file_resp.headers["content-type"] == "application/pdf"
        assert file_resp.content.startswith(b"%PDF-")
        assert len(file_resp.content) > 500


@pytest.mark.asyncio
async def test_generate_editable_format_export(test_reporting_db):
    """Verify RPT-04: Editable format export contains structured data and mandatory legal disclaimer."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(test_reporting_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}
        insp_id = test_reporting_db["inspection_id"]

        resp = await ac.post(f"/api/v1/inspections/{insp_id}/report?format=editable", headers=headers)
        assert resp.status_code == 201
        report_data = resp.json()

        assert report_data["format"] == "editable"

        # Verify downloading editable file
        file_resp = await ac.get(report_data["download_url"], headers=headers)
        assert file_resp.status_code == 200
        assert "application/json" in file_resp.headers["content-type"]

        parsed_export = json.loads(file_resp.content)
        assert parsed_export["format"] == "editable"
        assert "inspection" in parsed_export
        assert len(parsed_export["declarations"]) == 2
        assert len(parsed_export["violations"]) == 1

        # Verify RPT-02: Mandatory Legal Disclaimer is un-omittable and present
        disclaimer = parsed_export["legal_disclaimer"]
        assert disclaimer["title"] == MANDATORY_LEGAL_DISCLAIMER_TITLE
        assert disclaimer["text"] == MANDATORY_LEGAL_DISCLAIMER_TEXT


@pytest.mark.asyncio
async def test_list_inspection_reports(test_reporting_db):
    """Verify listing generated reports for an inspection."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(test_reporting_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}
        insp_id = test_reporting_db["inspection_id"]

        # Generate both PDF and editable reports
        await ac.post(f"/api/v1/inspections/{insp_id}/report?format=pdf", headers=headers)
        await ac.post(f"/api/v1/inspections/{insp_id}/report?format=editable", headers=headers)

        list_resp = await ac.get(f"/api/v1/inspections/{insp_id}/reports", headers=headers)
        assert list_resp.status_code == 200
        reports = list_resp.json()
        assert len(reports) == 2
        formats = {r["format"] for r in reports}
        assert formats == {"pdf", "editable"}


@pytest.mark.asyncio
async def test_reporting_rbac_enforcement(test_reporting_db):
    """Verify unauthorized officers cannot generate or access reports of other officers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        other_token = create_access_token(test_reporting_db["other_officer_id"])
        headers = {"Authorization": f"Bearer {other_token}"}
        insp_id = test_reporting_db["inspection_id"]

        # Other officer should be forbidden (403)
        res = await ac.post(f"/api/v1/inspections/{insp_id}/report?format=pdf", headers=headers)
        assert res.status_code == 403

        # Supervisor CAN generate report
        sup_token = create_access_token(test_reporting_db["supervisor_id"])
        sup_headers = {"Authorization": f"Bearer {sup_token}"}
        sup_res = await ac.post(f"/api/v1/inspections/{insp_id}/report?format=pdf", headers=sup_headers)
        assert sup_res.status_code == 201
