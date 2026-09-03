import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import get_password_hash
from app.db.session import Base
from app.main import app
from app.models.base import User


@pytest.fixture
async def sso_test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Pre-seed a standard password user to test backward compatibility
    existing_user_id = uuid.uuid4()
    async with async_session() as session:
        user = User(
            id=existing_user_id,
            email="regular.officer@example.com",
            password_hash=get_password_hash("StandardPassword123!"),
            full_name="Regular Officer",
            role="officer",
            region="DL",
            is_active=True,
        )
        session.add(user)
        await session.commit()

    from app.api import deps

    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[deps.get_db] = override_get_db

    yield {
        "engine": engine,
        "async_session": async_session,
        "existing_user_id": existing_user_id,
    }

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_sso_status_and_mode_detection(sso_test_db):
    """
    Verifies that the SSO gateway reports status and defaults to sandbox mode
    when live NIC MeriPehchan credentials are not supplied in .env.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/auth/sso/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True
        assert data["mode"] == "sandbox"
        assert "MeriPehchan" in data["provider_name"]
        assert data["client_id_configured"] is False


@pytest.mark.asyncio
async def test_sso_sandbox_personas_and_init(sso_test_db):
    """
    Verifies that /auth/sso/init initiates OIDC flow with CSRF state,
    and /auth/sso/sandbox lists pre-configured Legal Metrology officer personas.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Test SSO Init
        init_resp = await ac.get("/api/v1/auth/sso/init")
        assert init_resp.status_code == 200
        init_data = init_resp.json()
        assert init_data["is_sandbox"] is True
        assert "state" in init_data
        assert "/api/v1/auth/sso/sandbox" in init_data["authorization_url"]

        # 2. Test Personas Listing
        personas_resp = await ac.get("/api/v1/auth/sso/sandbox")
        assert personas_resp.status_code == 200
        personas = personas_resp.json()
        assert len(personas) >= 3

        ids = [p["id"] for p in personas]
        assert "officer_suresh" in ids
        assert "supervisor_priya" in ids
        assert "admin_rajesh" in ids


@pytest.mark.asyncio
async def test_sso_end_to_end_officer_login_and_jit_provisioning(sso_test_db):
    """
    E4-01 Full Flow Test:
    1. Initiate SSO to receive CSRF state.
    2. Authorize via Jan Parichay sandbox persona (Inspector Suresh Sharma).
    3. Complete OIDC callback token exchange.
    4. Assert JIT user provisioning and application JWT token issuance.
    5. Verify accessing authenticated /auth/me endpoint with the SSO bearer token.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Step 1: Initiate SSO
        init_res = await ac.get("/api/v1/auth/sso/init")
        state = init_res.json()["state"]

        # Step 2: Authorize Sandbox Persona
        auth_res = await ac.post(
            "/api/v1/auth/sso/sandbox/authorize",
            json={"persona_id": "officer_suresh", "state": state},
        )
        assert auth_res.status_code == 200
        auth_data = auth_res.json()
        code = auth_data["code"]
        assert code.startswith("SANDBOX-JANPARICHAY-")

        # Step 3: Callback token exchange
        callback_res = await ac.post(
            "/api/v1/auth/sso/callback",
            json={"code": code, "state": state},
        )
        assert callback_res.status_code == 200
        token_data = callback_res.json()

        assert "access_token" in token_data
        assert "refresh_token" in token_data
        assert token_data["token_type"] == "bearer"
        assert token_data["user"]["email"] == "suresh.sharma@gov.in"
        assert token_data["user"]["full_name"] == "Suresh Sharma"
        assert token_data["user"]["role"] == "officer"
        assert token_data["user"]["region"] == "DL"
        assert token_data["claims"]["parichay_id"] == "PARICHAY-DL-LM-1049"

        # Step 4: Verify authentication via Bearer token on /auth/me
        headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        me_res = await ac.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["email"] == "suresh.sharma@gov.in"
        assert me_data["role"] == "officer"


@pytest.mark.asyncio
async def test_sso_supervisor_role_mapping_and_rbac_elevation(sso_test_db):
    """
    Verifies that authenticating with a supervisory government designation
    (e.g., Deputy Controller Priya Verma) correctly maps to role='supervisor'.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        init_res = await ac.get("/api/v1/auth/sso/init")
        state = init_res.json()["state"]

        auth_res = await ac.post(
            "/api/v1/auth/sso/sandbox/authorize",
            json={"persona_id": "supervisor_priya", "state": state},
        )
        code = auth_res.json()["code"]

        callback_res = await ac.post(
            "/api/v1/auth/sso/callback",
            json={"code": code, "state": state},
        )
        assert callback_res.status_code == 200
        user_data = callback_res.json()["user"]
        assert user_data["email"] == "priya.verma@nic.in"
        assert user_data["role"] == "supervisor"
        assert user_data["region"] == "MH"


@pytest.mark.asyncio
async def test_sso_security_csrf_protection_and_invalid_codes(sso_test_db):
    """
    Security verification:
    1. Reject callback with CSRF state mismatch.
    2. Reject callback with invalid or expired authorization codes.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        init_res = await ac.get("/api/v1/auth/sso/init")
        state = init_res.json()["state"]

        auth_res = await ac.post(
            "/api/v1/auth/sso/sandbox/authorize",
            json={"persona_id": "admin_rajesh", "state": state},
        )
        code = auth_res.json()["code"]

        # 1. State mismatch attempt (attacker forging callback)
        mismatch_res = await ac.post(
            "/api/v1/auth/sso/callback",
            json={"code": code, "state": "tampered-csrf-state"},
        )
        assert mismatch_res.status_code == 400
        assert "state mismatch" in mismatch_res.json()["detail"].lower()

        # 2. Replay attempt or invalid code
        invalid_res = await ac.post(
            "/api/v1/auth/sso/callback",
            json={"code": "FORGED-CODE-123", "state": state},
        )
        assert invalid_res.status_code == 400
        assert "invalid or expired" in invalid_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_backward_compatibility_with_standard_password_auth(sso_test_db):
    """
    Guarantees that adding Government SSO does not break existing password-based
    authentication (/api/v1/auth/login) for local development or legacy users.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_res = await ac.post(
            "/api/v1/auth/login",
            data={"username": "regular.officer@example.com", "password": "StandardPassword123!"},
        )
        assert login_res.status_code == 200
        tokens = login_res.json()
        assert "access_token" in tokens
        assert tokens["token_type"] == "bearer"
