import io
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image, ImageDraw
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.core.security import create_access_token, get_password_hash
from app.db.session import Base
from app.main import app
from app.models.base import RulePack, User
from app.services.ocr.schemas import BoundingBox, OCRLine, OCRResult
from app.services.reporting.disclaimer import MANDATORY_LEGAL_DISCLAIMER_TITLE
from app.services.rules import load_default_rule_pack

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


def create_mock_label_image() -> bytes:
    """Create a realistic packaged food label image."""
    img = Image.new("RGB", (1200, 1600), color=(245, 245, 240))
    draw = ImageDraw.Draw(img)

    # Draw simulated label border
    draw.rectangle([(50, 50), (1150, 1550)], outline=(40, 40, 40), width=6)
    # Draw reference circle (for calibration)
    draw.ellipse([(100, 100), (250, 250)], fill=(20, 20, 20))

    # Text declarations
    draw.text((100, 300), "HIMALAYAN PREMIUM BASMATI RICE", fill=(10, 10, 10))
    draw.text((100, 450), "NET QUANTITY: 5 kg", fill=(10, 10, 10))
    draw.text((100, 600), "MRP Rs. 350.00 (INCL. OF ALL TAXES)", fill=(10, 10, 10))
    draw.text((100, 750), "MFD: 01/2026", fill=(10, 10, 10))
    draw.text((100, 900), "MANUFACTURED BY: Himalayan Foods Ltd, Delhi - 110001", fill=(10, 10, 10))
    draw.text((100, 1050), "CONSUMER CARE: support@himalayan.in, 1800-111-222", fill=(10, 10, 10))
    draw.text((100, 1200), "COUNTRY OF ORIGIN: INDIA", fill=(10, 10, 10))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


@pytest.fixture
async def e2e_test_db():
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
            email="field_officer@legalmetrology.gov.in",
            password_hash=get_password_hash("Inspect2026!"),
            full_name="Inspector Rajesh Kumar",
            role="officer",
            region="Delhi-Central",
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
        await session.commit()

    yield {
        "session": async_session,
        "officer_id": officer_id,
    }

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_full_pipeline_capture_to_report(e2e_test_db):
    """
    TEST-02: Complete pipeline integration test on sample packaging photo:
    Capture -> Image Upload -> Process (OCR + Extraction + Rules) -> Evidence Viewer -> Report Generation.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(e2e_test_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}

        # Step 1: Create Inspection (POST /api/v1/inspections)
        create_resp = await ac.post(
            "/api/v1/inspections",
            headers=headers,
            json={
                "commodity_category": "packaged_food",
                "is_self_check": False,
                "captured_offline": False,
            },
        )
        assert create_resp.status_code == 201, create_resp.text
        inspection_data = create_resp.json()
        inspection_id = inspection_data["id"]
        assert inspection_data["status"] == "draft"

        # Step 2: Upload Packaging Image (POST /api/v1/inspections/{id}/images)
        image_bytes = create_mock_label_image()
        files = {
            "file": ("front_pdp.jpg", image_bytes, "image/jpeg"),
        }
        data = {
            "image_role": "front_pdp",
        }
        upload_resp = await ac.post(
            f"/api/v1/inspections/{inspection_id}/images",
            headers=headers,
            files=files,
            data=data,
        )
        assert upload_resp.status_code == 201, upload_resp.text
        img_data = upload_resp.json()
        assert img_data["image_role"] == "front_pdp"

        # Step 3: Trigger Pipeline Processing (POST /api/v1/inspections/{id}/process)
        mock_ocr = OCRResult(
            source_image_id=str(img_data["id"]),
            engine_used="test-mock",
            lines=[
                OCRLine(text="HIMALAYAN PREMIUM BASMATI RICE", confidence=0.98, bounding_box=BoundingBox(x=100, y=300, w=600, h=50), source_image_id=str(img_data["id"])),
                OCRLine(text="NET QUANTITY: 5 kg", confidence=0.97, bounding_box=BoundingBox(x=100, y=450, w=400, h=40), source_image_id=str(img_data["id"])),
                OCRLine(text="MRP Rs. 350.00 (INCL. OF ALL TAXES)", confidence=0.99, bounding_box=BoundingBox(x=100, y=600, w=650, h=40), source_image_id=str(img_data["id"])),
                OCRLine(text="MFD: 01/2026", confidence=0.95, bounding_box=BoundingBox(x=100, y=750, w=300, h=40), source_image_id=str(img_data["id"])),
                OCRLine(text="MANUFACTURED BY: Himalayan Foods Ltd, Delhi - 110001", confidence=0.94, bounding_box=BoundingBox(x=100, y=900, w=800, h=40), source_image_id=str(img_data["id"])),
                OCRLine(text="CONSUMER CARE: support@himalayan.in, 1800-111-222", confidence=0.96, bounding_box=BoundingBox(x=100, y=1050, w=750, h=40), source_image_id=str(img_data["id"])),
                OCRLine(text="COUNTRY OF ORIGIN: INDIA", confidence=0.98, bounding_box=BoundingBox(x=100, y=1200, w=450, h=40), source_image_id=str(img_data["id"])),
            ],
            full_text="HIMALAYAN PREMIUM BASMATI RICE\nNET QUANTITY: 5 kg\nMRP Rs. 350.00 (INCL. OF ALL TAXES)\nMFD: 01/2026\nMANUFACTURED BY: Himalayan Foods Ltd, Delhi - 110001\nCONSUMER CARE: support@himalayan.in, 1800-111-222\nCOUNTRY OF ORIGIN: INDIA",
            average_confidence=0.97,
        )

        with patch("app.services.ocr.service.OCRService.process_image", return_value=mock_ocr):
            process_resp = await ac.post(
                f"/api/v1/inspections/{inspection_id}/process",
                headers=headers,
            )
            assert process_resp.status_code == 200, process_resp.text
            proc_data = process_resp.json()
            assert isinstance(proc_data, list)
            assert len(proc_data) >= 5

        # Step 4: Verify Evidence Mapping (GET /api/v1/inspections/{id}/evidence)
        evid_resp = await ac.get(
            f"/api/v1/inspections/{inspection_id}/evidence",
            headers=headers,
        )
        assert evid_resp.status_code == 200, evid_resp.text
        evidence = evid_resp.json()
        assert evidence["inspection_id"] == inspection_id
        assert len(evidence["items"]) >= 5
        # Every item must have bounding_box and confidence
        for item in evidence["items"]:
            assert "bounding_box" in item
            assert "confidence" in item
            assert item["confidence"] > 0.0

        # Step 5: Generate Compliance Report (POST /api/v1/inspections/{id}/report)
        report_resp = await ac.post(
            f"/api/v1/inspections/{inspection_id}/report",
            headers=headers,
            json={"format": "pdf"},
        )
        assert report_resp.status_code == 201, report_resp.text
        report_data = report_resp.json()
        assert report_data["format"] == "pdf"
        report_id = report_data["id"]

        # Step 6: Download Report and Verify Statutory Integrity (GET /api/v1/inspections/{id}/reports/{report_id}/file)
        file_resp = await ac.get(
            f"/api/v1/inspections/{inspection_id}/reports/{report_id}/file",
            headers=headers,
        )
        assert file_resp.status_code == 200, file_resp.text
        pdf_bytes = file_resp.content
        assert len(pdf_bytes) > 500
        assert pdf_bytes.startswith(b"%PDF")

        # Step 7: Generate and Verify Editable Report (JSON) with Legal Disclaimer
        editable_resp = await ac.post(
            f"/api/v1/inspections/{inspection_id}/report",
            headers=headers,
            json={"format": "editable"},
        )
        assert editable_resp.status_code == 201
        editable_data = editable_resp.json()
        edit_file_resp = await ac.get(
            f"/api/v1/inspections/{inspection_id}/reports/{editable_data['id']}/file",
            headers=headers,
        )
        assert edit_file_resp.status_code == 200
        export_json = edit_file_resp.json()
        assert MANDATORY_LEGAL_DISCLAIMER_TITLE in export_json["legal_disclaimer"]["title"]
        assert export_json["officer"]["full_name"] == "Inspector Rajesh Kumar"
