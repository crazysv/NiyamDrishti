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

    # Seed users with different roles
    async with async_session() as session:
        officer = User(
            id=uuid.uuid4(),
            email="officer@test.gov.in",
            password_hash=get_password_hash("password123"),
            full_name="Test Officer",
            role="officer",
            region="Delhi-North",
            is_active=True,
        )
        supervisor = User(
            id=uuid.uuid4(),
            email="supervisor@test.gov.in",
            password_hash=get_password_hash("password123"),
            full_name="Test Supervisor",
            role="supervisor",
            region="Delhi",
            is_active=True,
        )
        admin = User(
            id=uuid.uuid4(),
            email="admin@test.gov.in",
            password_hash=get_password_hash("password123"),
            full_name="Test Admin",
            role="admin",
            region="National",
            is_active=True,
        )
        inactive = User(
            id=uuid.uuid4(),
            email="inactive@test.gov.in",
            password_hash=get_password_hash("password123"),
            full_name="Inactive User",
            role="officer",
            region="Delhi",
            is_active=False,
        )
        session.add_all([officer, supervisor, admin, inactive])
        await session.commit()

    yield async_session

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_login_and_refresh_flow(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Login success
        resp = await ac.post("/api/v1/auth/login", data={"username": "officer@test.gov.in", "password": "password123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

        access_token = data["access_token"]
        refresh_token = data["refresh_token"]

        # 2. Login failure (wrong password)
        bad_resp = await ac.post("/api/v1/auth/login", data={"username": "officer@test.gov.in", "password": "wrong"})
        assert bad_resp.status_code == 401

        # 3. Login failure (inactive user)
        inact_resp = await ac.post(
            "/api/v1/auth/login", data={"username": "inactive@test.gov.in", "password": "password123"}
        )
        assert inact_resp.status_code == 400

        # 4. Refresh token success
        ref_resp = await ac.post(f"/api/v1/auth/refresh?refresh_token={refresh_token}")
        assert ref_resp.status_code == 200
        ref_data = ref_resp.json()
        assert "access_token" in ref_data

        # 5. GET /me success with Bearer token
        me_resp = await ac.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["email"] == "officer@test.gov.in"
        assert me_data["role"] == "officer"
        assert me_data["full_name"] == "Test Officer"

        # 6. GET /me failure without token
        me_bad = await ac.get("/api/v1/auth/me")
        assert me_bad.status_code == 401
