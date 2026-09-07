"""Security and evidentiary integrity tests for audit logs and evidence chain of custody (E4-04)."""

import hashlib
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.core.security import get_password_hash
from app.db.session import Base
from app.main import app
from app.models.base import AuditLog, InspectionImage, User

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_session():
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def test_client_and_db():
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    officer_id = uuid.uuid4()
    async with async_session() as session:
        officer = User(
            id=officer_id,
            email="legal_officer@metrology.gov.in",
            password_hash=get_password_hash("secure123"),
            full_name="Inspector Rajesh Kumar",
            role="officer",
            region="North-Delhi",
            is_active=True,
        )
        session.add(officer)
        await session.commit()

    async def override_get_db():
        async with async_session() as session:
            yield session

    async def override_get_user():
        async with async_session() as session:
            res = await session.get(User, officer_id)
            return res

    app.dependency_overrides[deps.get_db] = override_get_db
    app.dependency_overrides[deps.get_current_active_user] = override_get_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, async_session, officer_id

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_audit_log_immutability_enforcement(test_session: AsyncSession):
    """Verify that UPDATE and DELETE on audit_logs are forbidden by law via SQLAlchemy event listeners."""
    officer_id = uuid.uuid4()
    log_id = uuid.uuid4()
    log = AuditLog(
        id=log_id,
        actor_user_id=officer_id,
        action="field_override",
        entity_type="extracted_field",
        entity_id=str(uuid.uuid4()),
        before_value={"raw_text": "MRP 100"},
        after_value={"parsed_value": "100.00"},
    )
    test_session.add(log)
    await test_session.commit()

    # 1. Automatic cryptographic hash must be computed
    fresh_log = await test_session.get(AuditLog, log_id)
    assert fresh_log is not None
    assert fresh_log.entry_hash is not None
    assert len(fresh_log.entry_hash) == 64

    # 2. Attempting to UPDATE an audit record must raise PermissionError
    fresh_log.action = "tampered_action"
    with pytest.raises(PermissionError) as exc_info:
        await test_session.commit()
    assert "legally immutable" in str(exc_info.value)
    await test_session.rollback()

    # 3. Attempting to DELETE an audit record must raise PermissionError
    log_to_delete = await test_session.get(AuditLog, log_id)
    assert log_to_delete is not None
    await test_session.delete(log_to_delete)
    with pytest.raises(PermissionError) as exc_info_del:
        await test_session.commit()
    assert "legally immutable" in str(exc_info_del.value)


@pytest.mark.asyncio
async def test_evidence_verification_and_section_65b_certificate(test_client_and_db):
    """Verify end-to-end evidence chain verification and Section 65B/BSA 63 certificate generation."""
    client, session_factory, officer_id = test_client_and_db

    # 1. Create inspection
    create_resp = await client.post(
        "/api/v1/inspections",
        json={
            "commodity_category": "packaged_food",
            "region": "North-Delhi",
        },
    )
    assert create_resp.status_code == 201
    insp_id = create_resp.json()["id"]

    # 2. Upload image with binary payload
    dummy_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00" + b"A" * 100
    expected_hash = hashlib.sha256(dummy_jpeg).hexdigest()

    files = {"file": ("front_label.jpg", dummy_jpeg, "image/jpeg")}
    data = {
        "image_role": "front_pdp",
        "quality_check_passed": "true",
        "width_px": "1920",
        "height_px": "1080",
    }
    img_resp = await client.post(f"/api/v1/inspections/{insp_id}/images", data=data, files=files)
    assert img_resp.status_code == 201
    img_data = img_resp.json()
    assert img_data["sha256_hash"] == expected_hash

    # 3. Add an audit log override for the inspection
    async with session_factory() as session:
        audit_item = AuditLog(
            id=uuid.uuid4(),
            actor_user_id=officer_id,
            action="field_verified",
            entity_type="inspection",
            entity_id=insp_id,
            before_value=None,
            after_value={"status": "needs_review"},
        )
        session.add(audit_item)
        await session.commit()

    # 4. Verify evidence chain endpoint
    verify_resp = await client.get(f"/api/v1/inspections/{insp_id}/evidence/verify")
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["overall_status"] == "VERIFIED"
    assert verify_data["is_tamper_free"] is True
    assert verify_data["images_verified"] == 1
    assert verify_data["images_compromised"] == 0
    assert verify_data["audit_chain_intact"] is True
    assert verify_data["evidence_chain_hash"] is not None

    # 5. Generate Section 65B / BSA 63 certificate endpoint
    cert_resp = await client.get(f"/api/v1/inspections/{insp_id}/evidence/certificate")
    assert cert_resp.status_code == 200
    cert_data = cert_resp.json()
    assert cert_data["inspection_id"] == insp_id
    assert "SECTION 63 BSA" in cert_data["title"]
    assert cert_data["officer_name"] == "Inspector Rajesh Kumar"
    assert len(cert_data["photographic_schedule"]) == 1
    assert cert_data["photographic_schedule"][0]["sha256_fingerprint"] == expected_hash
    assert cert_data["photographic_schedule"][0]["integrity_verdict"] == "verified"
    assert "ordinary course of my official regulatory duties" in cert_data["statutory_attestation"]


@pytest.mark.asyncio
async def test_tamper_detection_in_evidence_chain(test_client_and_db):
    """Verify that corrupting or tampering with an image hash triggers COMPROMISED status."""
    client, session_factory, officer_id = test_client_and_db

    # Create inspection
    create_resp = await client.post(
        "/api/v1/inspections",
        json={"commodity_category": "electronics"},
    )
    insp_id = create_resp.json()["id"]

    # Upload image
    files = {"file": ("panel.jpg", b"valid_image_bytes_content_123", "image/jpeg")}
    img_resp = await client.post(
        f"/api/v1/inspections/{insp_id}/images",
        data={"image_role": "back_panel", "quality_check_passed": "true"},
        files=files,
    )
    assert img_resp.status_code == 201
    img_id = img_resp.json()["id"]

    # Tamper with the image record directly in the DB
    async with session_factory() as session:
        img = await session.get(InspectionImage, uuid.UUID(img_id))
        assert img is not None
        img.sha256_hash = "0000000000000000000000000000000000000000000000000000000000000000"
        await session.commit()

    # Call verify endpoint: must flag COMPROMISED
    verify_resp = await client.get(f"/api/v1/inspections/{insp_id}/evidence/verify")
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["overall_status"] == "COMPROMISED"
    assert verify_data["is_tamper_free"] is False
    assert verify_data["images_compromised"] >= 1
