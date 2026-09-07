"""
Integration tests for E-Commerce Listing Image Ingestion (E3-01, STOR-01, 06_SCHEMA.md).
Verifies the ingestion, storage, retrieval, and validation of ecommerce_listing image roles.
"""

import base64
import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.core.security import create_access_token, get_password_hash
from app.db.session import Base
from app.main import app
from app.models.base import ExtractedField, Inspection, InspectionImage, User

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

# 1x1 transparent PNG data URL
TINY_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
TINY_PNG_DATA_URL = f"data:image/png;base64,{TINY_PNG_B64}"


@pytest.fixture
async def ecom_test_db():
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

    async with async_session() as session:
        officer = User(
            id=officer_id,
            email="ecom_officer@test.gov.in",
            password_hash=get_password_hash("password123"),
            full_name="Officer ECom",
            role="officer",
            region="Delhi-North",
            is_active=True,
        )
        inspection = Inspection(
            id=insp_id,
            officer_id=officer_id,
            status="draft",
            commodity_category="packaged_food",
            rule_pack_version="2026.02.01",
            captured_offline=False,
        )
        session.add_all([officer, inspection])
        await session.commit()

    yield {
        "session": async_session,
        "officer_id": officer_id,
        "inspection_id": insp_id,
    }

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_ecommerce_listing_json_data_url_ingestion(ecom_test_db):
    """Verify uploading an ecommerce_listing image via JSON data URL (E3-01)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(ecom_test_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}
        insp_id = ecom_test_db["inspection_id"]

        payload = {
            "image_role": "ecommerce_listing",
            "data_url": TINY_PNG_DATA_URL,
            "width_px": 1080,
            "height_px": 1920,
            "quality_check_passed": True,
        }

        resp = await ac.post(
            f"/api/v1/inspections/{insp_id}/images",
            json=payload,
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()

        assert data["image_role"] == "ecommerce_listing"
        assert data["inspection_id"] == str(insp_id)
        assert data["width_px"] == 1080
        assert data["height_px"] == 1920
        assert data["quality_check_passed"] is True
        assert (
            data["storage_url"].startswith("/uploads")
            or data["storage_url"].startswith("local://")
            or "http" in data["storage_url"]
        )


@pytest.mark.asyncio
async def test_ecommerce_listing_multipart_upload_ingestion(ecom_test_db):
    """Verify uploading an ecommerce_listing image via multipart form-data (E3-01)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(ecom_test_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}
        insp_id = ecom_test_db["inspection_id"]

        raw_bytes = base64.b64decode(TINY_PNG_B64)
        files = {
            "file": ("amazon_product_listing.png", raw_bytes, "image/png"),
        }
        data = {
            "image_role": "ecommerce_listing",
            "width_px": "1200",
            "height_px": "1600",
            "quality_check_passed": "true",
        }

        resp = await ac.post(
            f"/api/v1/inspections/{insp_id}/images",
            data=data,
            files=files,
            headers=headers,
        )
        assert resp.status_code == 201
        res = resp.json()

        assert res["image_role"] == "ecommerce_listing"
        assert res["inspection_id"] == str(insp_id)


@pytest.mark.asyncio
async def test_ecommerce_listing_retrieval_in_inspection(ecom_test_db):
    """Verify that fetching an inspection reflects uploaded ecommerce_listing images in evidence/images list."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(ecom_test_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}
        insp_id = ecom_test_db["inspection_id"]

        # Ingest PDP and E-Commerce Listing images
        await ac.post(
            f"/api/v1/inspections/{insp_id}/images",
            json={"image_role": "front_pdp", "data_url": TINY_PNG_DATA_URL},
            headers=headers,
        )
        await ac.post(
            f"/api/v1/inspections/{insp_id}/images",
            json={"image_role": "ecommerce_listing", "data_url": TINY_PNG_DATA_URL},
            headers=headers,
        )

        resp = await ac.get(f"/api/v1/inspections/{insp_id}", headers=headers)
        assert resp.status_code == 200
        insp_data = resp.json()

        assert len(insp_data["images"]) == 2
        roles = [img["image_role"] for img in insp_data["images"]]
        assert "front_pdp" in roles
        assert "ecommerce_listing" in roles


@pytest.mark.asyncio
async def test_invalid_image_role_rejected(ecom_test_db):
    """Verify that an unsupported image_role is rejected with a 400 Bad Request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(ecom_test_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}
        insp_id = ecom_test_db["inspection_id"]

        resp = await ac.post(
            f"/api/v1/inspections/{insp_id}/images",
            json={"image_role": "invalid_random_role", "data_url": TINY_PNG_DATA_URL},
            headers=headers,
        )
        assert resp.status_code in [400, 422]


@pytest.mark.asyncio
async def test_ecommerce_cross_match_api_endpoint(ecom_test_db):
    """Verify GET /api/v1/inspections/{id}/cross-match reports discrepancies (E3-02)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(ecom_test_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}
        insp_id = ecom_test_db["inspection_id"]

        # Seed physical PDP and e-commerce listing images & fields
        pdp_img_id = uuid.uuid4()
        ecom_img_id = uuid.uuid4()

        async with ecom_test_db["session"]() as session:
            img_pdp = InspectionImage(
                id=pdp_img_id,
                inspection_id=insp_id,
                image_role="front_pdp",
                storage_url="/uploads/pdp.png",
                quality_check_passed=True,
                captured_at=datetime.now(timezone.utc),
            )
            img_ecom = InspectionImage(
                id=ecom_img_id,
                inspection_id=insp_id,
                image_role="ecommerce_listing",
                storage_url="/uploads/ecom.png",
                quality_check_passed=True,
                captured_at=datetime.now(timezone.utc),
            )
            f_pdp = ExtractedField(
                id=uuid.uuid4(),
                inspection_id=insp_id,
                source_image_id=pdp_img_id,
                field_type="net_quantity",
                raw_text="Net Wt: 450 g",
                parsed_value="450 g",
                confidence=0.92,
                bounding_box={"x": 10, "y": 10, "w": 50, "h": 20},
                verdict="pass",
            )
            f_ecom = ExtractedField(
                id=uuid.uuid4(),
                inspection_id=insp_id,
                source_image_id=ecom_img_id,
                field_type="net_quantity",
                raw_text="Pack (500 g)",
                parsed_value="500 g",
                confidence=0.95,
                bounding_box={"x": 10, "y": 10, "w": 50, "h": 20},
                verdict="pass",
            )
            session.add_all([img_pdp, img_ecom, f_pdp, f_ecom])
            await session.commit()

        resp = await ac.get(f"/api/v1/inspections/{insp_id}/cross-match", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["inspection_id"] == str(insp_id)
        assert data["is_consistent"] is False
        assert len(data["discrepancies"]) >= 1

        qty_disc = next(d for d in data["discrepancies"] if d["field_type"] == "net_quantity")
        assert qty_disc["discrepancy_type"] == "ecommerce_net_quantity_mismatch"
        assert qty_disc["severity"] == "critical"
        assert "Rule 6(10)" in qty_disc["citation"]
