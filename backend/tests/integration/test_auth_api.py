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

    # Seed user
    user_id = uuid.uuid4()
    async with async_session() as session:
        user = User(
            id=user_id,
            email="officer@test.gov.in",
            password_hash=get_password_hash("password123"),
            full_name="Officer Test",
            role="officer",
            region="Delhi",
            is_active=True,
        )
        session.add(user)
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

        refresh_token = data["refresh_token"]

        # 2. Login failure (wrong password)
        bad_resp = await ac.post("/api/v1/auth/login", data={"username": "officer@test.gov.in", "password": "wrong"})
        assert bad_resp.status_code == 401

        # 3. Refresh token success
        ref_resp = await ac.post(f"/api/v1/auth/refresh?refresh_token={refresh_token}")
        assert ref_resp.status_code == 200
        ref_data = ref_resp.json()
        assert "access_token" in ref_data
