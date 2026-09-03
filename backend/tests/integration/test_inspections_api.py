import base64
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.core.security import get_password_hash
from app.db.session import Base
from app.main import app
from app.models.base import User

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

    # Seed users
    officer_id = uuid.uuid4()
    other_officer_id = uuid.uuid4()

    async with async_session() as session:
        officer = User(
            id=officer_id,
            email="officer1@test.gov.in",
            password_hash=get_password_hash("password123"),
            full_name="Officer One",
            role="officer",
            region="Delhi-North",
            is_active=True,
        )
        other_officer = User(
            id=other_officer_id,
            email="officer2@test.gov.in",
            password_hash=get_password_hash("password123"),
            full_name="Officer Two",
            role="officer",
            region="Mumbai-South",
            is_active=True,
        )
        session.add_all([officer, other_officer])
        await session.commit()

    yield async_session

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_inspection_create_and_upload_images(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Login as Officer 1
        login_resp = await ac.post(
            "/api/v1/auth/login",
            data={"username": "officer1@test.gov.in", "password": "password123"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. POST /api/v1/inspections
        create_payload = {
            "commodity_category": "packaged_food",
            "captured_offline": False,
            "is_self_check": False,
        }
        create_resp = await ac.post("/api/v1/inspections", json=create_payload, headers=headers)
        assert create_resp.status_code == 201
        insp_data = create_resp.json()
        assert "id" in insp_data
        assert insp_data["status"] == "draft"
        assert insp_data["commodity_category"] == "packaged_food"
        assert insp_data["rule_pack_version"] == "2026.02.01"
        assert insp_data["images"] == []

        inspection_id = insp_data["id"]

        # 3. POST /api/v1/inspections/{id}/images via JSON Data URL (Front PDP)
        dummy_base64 = base64.b64encode(b"dummy image bytes for testing").decode("utf-8")
        data_url = f"data:image/jpeg;base64,{dummy_base64}"

        img_payload = {
            "image_role": "front_pdp",
            "data_url": data_url,
            "quality_check_passed": True,
            "width_px": 1080,
            "height_px": 1440,
        }

        upload_resp = await ac.post(
            f"/api/v1/inspections/{inspection_id}/images",
            json=img_payload,
            headers=headers,
        )
        assert upload_resp.status_code == 201
        img_data = upload_resp.json()
        assert img_data["image_role"] == "front_pdp"
        assert img_data["quality_check_passed"] is True
        assert "/uploads/" in img_data["storage_url"]
        assert img_data["width_px"] == 1080

        # 4. POST /api/v1/inspections/{id}/images via multipart file upload (Back Panel)
        files = {"file": ("back_panel.jpg", b"fake binary back panel content", "image/jpeg")}
        form_data = {"image_role": "back_panel"}

        upload_file_resp = await ac.post(
            f"/api/v1/inspections/{inspection_id}/images",
            files=files,
            data=form_data,
            headers=headers,
        )
        assert upload_file_resp.status_code == 201
        back_img_data = upload_file_resp.json()
        assert back_img_data["image_role"] == "back_panel"

        # 5. GET /api/v1/inspections/{id}
        get_resp = await ac.get(f"/api/v1/inspections/{inspection_id}", headers=headers)
        assert get_resp.status_code == 200
        full_insp = get_resp.json()
        assert len(full_insp["images"]) == 2

        # 6. Negative test: Invalid image role
        bad_role_payload = {
            "image_role": "random_unsupported_role",
            "data_url": data_url,
        }
        bad_resp = await ac.post(
            f"/api/v1/inspections/{inspection_id}/images",
            json=bad_role_payload,
            headers=headers,
        )
        assert bad_resp.status_code == 400

        # 7. Authorization test: Officer 2 cannot view Officer 1's inspection
        login_resp_2 = await ac.post(
            "/api/v1/auth/login",
            data={"username": "officer2@test.gov.in", "password": "password123"},
        )
        token2 = login_resp_2.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        unauth_resp = await ac.get(f"/api/v1/inspections/{inspection_id}", headers=headers2)
        assert unauth_resp.status_code == 403
