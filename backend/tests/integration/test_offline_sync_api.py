import base64
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.core.security import get_password_hash
from app.db.session import Base
from app.main import app
from app.models.base import Inspection, User

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

    officer_id = uuid.uuid4()
    async with async_session() as session:
        officer = User(
            id=officer_id,
            email="field_officer@test.gov.in",
            password_hash=get_password_hash("password123"),
            full_name="Field Officer Sharma",
            role="officer",
            region="Delhi-Central",
            is_active=True,
        )
        session.add(officer)
        await session.commit()

    yield async_session

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_idempotent_inspection_creation(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_resp = await ac.post(
            "/api/v1/auth/login",
            data={"username": "field_officer@test.gov.in", "password": "password123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        client_nonce = f"offline_insp_{uuid.uuid4().hex[:10]}"
        payload = {
            "client_id": client_nonce,
            "commodity_category": "packaged_spices",
            "captured_offline": True,
        }

        # First creation
        resp1 = await ac.post("/api/v1/inspections", json=payload, headers=headers)
        assert resp1.status_code == 201
        data1 = resp1.json()
        assert data1["client_id"] == client_nonce
        insp_id = data1["id"]

        # Second creation with identical client_id / Idempotency-Key
        resp2 = await ac.post("/api/v1/inspections", json=payload, headers=headers)
        assert resp2.status_code in (200, 201)
        data2 = resp2.json()
        assert data2["id"] == insp_id
        assert data2["client_id"] == client_nonce


@pytest.mark.asyncio
async def test_idempotent_image_upload(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_resp = await ac.post(
            "/api/v1/auth/login",
            data={"username": "field_officer@test.gov.in", "password": "password123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        create_resp = await ac.post(
            "/api/v1/inspections", json={"commodity_category": "packaged_spices"}, headers=headers
        )
        insp_id = create_resp.json()["id"]

        dummy_b64 = base64.b64encode(b"test image bytes for offline idempotency").decode("utf-8")
        data_url = f"data:image/jpeg;base64,{dummy_b64}"
        img_client_id = f"img_client_{uuid.uuid4().hex[:8]}"

        img_payload = {
            "client_id": img_client_id,
            "image_role": "front_pdp",
            "data_url": data_url,
            "quality_check_passed": True,
        }

        # First upload
        up1 = await ac.post(f"/api/v1/inspections/{insp_id}/images", json=img_payload, headers=headers)
        assert up1.status_code == 201
        up1_data = up1.json()
        assert up1_data["client_id"] == img_client_id
        img_id = up1_data["id"]

        # Duplicate upload attempt with identical client_id
        up2 = await ac.post(f"/api/v1/inspections/{insp_id}/images", json=img_payload, headers=headers)
        assert up2.status_code in (200, 201)
        up2_data = up2.json()
        assert up2_data["id"] == img_id
        assert up2_data["client_id"] == img_client_id


@pytest.mark.asyncio
async def test_conflict_on_finalized_inspection(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_resp = await ac.post(
            "/api/v1/auth/login",
            data={"username": "field_officer@test.gov.in", "password": "password123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        create_resp = await ac.post("/api/v1/inspections", json={"commodity_category": "general"}, headers=headers)
        insp_id = create_resp.json()["id"]

        # Transition inspection directly to completed
        async with test_db() as session:
            insp = await session.get(Inspection, uuid.UUID(insp_id))
            insp.status = "completed"
            await session.commit()

        # Attempt to upload image to completed inspection
        dummy_b64 = base64.b64encode(b"conflict test bytes").decode("utf-8")
        img_payload = {
            "image_role": "back_panel",
            "data_url": f"data:image/jpeg;base64,{dummy_b64}",
        }
        resp = await ac.post(f"/api/v1/inspections/{insp_id}/images", json=img_payload, headers=headers)
        assert resp.status_code == 409
        err_detail = resp.json()["detail"]
        assert err_detail["code"] == "INSPECTION_FINALIZED"
        assert err_detail["suggested_resolution"] == "server_authoritative"


@pytest.mark.asyncio
async def test_batch_offline_sync_endpoint(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_resp = await ac.post(
            "/api/v1/auth/login",
            data={"username": "field_officer@test.gov.in", "password": "password123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        dummy_b64 = base64.b64encode(b"batch sync photo data").decode("utf-8")
        data_url = f"data:image/jpeg;base64,{dummy_b64}"

        client_id_1 = f"batch_insp_{uuid.uuid4().hex[:8]}"
        sync_payload = {
            "inspections": [
                {
                    "client_id": client_id_1,
                    "commodity_category": "packaged_food",
                    "captured_offline": True,
                    "images": [
                        {
                            "client_id": f"img_{uuid.uuid4().hex[:8]}",
                            "image_role": "front_pdp",
                            "data_url": data_url,
                            "quality_check_passed": True,
                            "width_px": 800,
                            "height_px": 1200,
                        },
                        {
                            "client_id": f"img_{uuid.uuid4().hex[:8]}",
                            "image_role": "back_panel",
                            "data_url": data_url,
                            "quality_check_passed": True,
                            "width_px": 800,
                            "height_px": 1200,
                        },
                    ],
                }
            ]
        }

        # Execute batch sync
        sync_resp = await ac.post("/api/v1/inspections/sync", json=sync_payload, headers=headers)
        assert sync_resp.status_code == 200
        sync_data = sync_resp.json()
        assert sync_data["total"] == 1
        assert sync_data["successful"] == 1
        assert sync_data["conflicted"] == 0
        res = sync_data["results"][0]
        assert res["success"] is True
        assert res["images_synced"] == 2
        assert res["images_skipped"] == 0
        assert res["inspection_id"] is not None

        # Re-syncing the same inspection should skip existing images idempotently
        resync_resp = await ac.post("/api/v1/inspections/sync", json=sync_payload, headers=headers)
        assert resync_resp.status_code == 200
        resync_data = resync_resp.json()
        assert resync_data["successful"] == 1
        res2 = resync_data["results"][0]
        assert res2["images_synced"] == 0
        assert res2["images_skipped"] == 2
