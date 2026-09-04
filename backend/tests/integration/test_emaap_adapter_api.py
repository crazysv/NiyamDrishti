"""Integration tests for the National Legal Metrology eMaap Portal Adapter API (E4-05, ADR-020)."""

import hashlib
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.core.security import get_password_hash
from app.db.session import Base
from app.main import app
from app.models.base import AuditLog, ExtractedField, Inspection, InspectionImage, User, Violation

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


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
            email="inspector.patel@metrology.gov.in",
            password_hash=get_password_hash("secure123"),
            full_name="Inspector Ramesh Patel",
            role="officer",
            region="Gujarat-Ahmedabad",
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
async def test_emaap_adapter_status(test_client_and_db):
    """Verify adapter status reporting and operational mode."""
    client, _, _ = test_client_and_db

    resp = await client.get("/api/v1/integrations/emaap/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_enabled"] is True
    assert data["is_sandbox"] is True
    assert "registration_verification" in data["supported_operations"]
    assert "enforcement_docket_submission" in data["supported_operations"]


@pytest.mark.asyncio
async def test_emaap_registration_verification(test_client_and_db):
    """Verify manufacturer/packer LMPC registration lookup across active, expired, and missing entities."""
    client, _, _ = test_client_and_db

    # 1. Active registration lookup
    active_resp = await client.post(
        "/api/v1/integrations/emaap/verify-registration",
        json={"registration_number": "REG-LMPC-2023-DL-0012"},
    )
    assert active_resp.status_code == 200
    active_data = active_resp.json()
    assert active_data["is_registered"] is True
    assert active_data["status"] == "ACTIVE"
    assert active_data["entity_name"] == "Hindustan Unilever Limited"
    assert "packaged_food" in active_data["authorized_commodity_categories"]

    # 2. Expired registration lookup
    expired_resp = await client.post(
        "/api/v1/integrations/emaap/verify-registration",
        json={"registration_number": "REG-LMPC-2020-DL-9941"},
    )
    assert expired_resp.status_code == 200
    expired_data = expired_resp.json()
    assert expired_data["is_registered"] is True
    assert expired_data["status"] == "EXPIRED"
    assert expired_data["entity_name"] == "Old Mill Spices Private Limited"

    # 3. Unknown registration number lookup
    unknown_resp = await client.post(
        "/api/v1/integrations/emaap/verify-registration",
        json={"registration_number": "REG-NONEXISTENT-9999"},
    )
    assert unknown_resp.status_code == 200
    unknown_data = unknown_resp.json()
    assert unknown_data["is_registered"] is False
    assert unknown_data["status"] == "NOT_FOUND"

    # 4. Fuzzy company name fallback search
    name_resp = await client.post(
        "/api/v1/integrations/emaap/verify-registration",
        json={"registration_number": "UNKNOWN", "company_name": "Parle Products"},
    )
    assert name_resp.status_code == 200
    name_data = name_resp.json()
    assert name_data["is_registered"] is True
    assert name_data["status"] == "ACTIVE"
    assert "Parle Products" in name_data["entity_name"]


@pytest.mark.asyncio
async def test_emaap_enforcement_docket_submission(test_client_and_db):
    """Verify filing a finalized non-compliant inspection case file and evidence dossier into eMaap."""
    client, session_factory, officer_id = test_client_and_db

    # 1. Create inspection
    create_resp = await client.post(
        "/api/v1/inspections",
        json={"commodity_category": "packaged_food", "region": "Gujarat-Ahmedabad"},
    )
    assert create_resp.status_code == 201
    insp_id = create_resp.json()["id"]

    # 2. Upload image with cryptographic hash
    dummy_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"TEST_BYTES" * 10
    files = {"file": ("front.jpg", dummy_jpeg, "image/jpeg")}
    data = {"image_role": "front_pdp", "quality_check_passed": "true"}
    img_resp = await client.post(f"/api/v1/inspections/{insp_id}/images", data=data, files=files)
    assert img_resp.status_code == 201
    img_id = img_resp.json()["id"]

    # 3. Add extracted field and violation in DB
    async with session_factory() as session:
        field = ExtractedField(
            id=uuid.uuid4(),
            inspection_id=uuid.UUID(insp_id),
            source_image_id=uuid.UUID(img_id),
            field_type="mrp",
            raw_text="MRP 120 (Altered)",
            parsed_value="120.00",
            confidence=0.95,
            bounding_box={"x": 10, "y": 20, "w": 100, "h": 40},
            verdict="fail",
            reviewed_by_officer=True,
        )
        session.add(field)

        violation = Violation(
            id=uuid.uuid4(),
            inspection_id=uuid.UUID(insp_id),
            extracted_field_id=field.id,
            rule_id="LM_RULE_18_2_ALTERED_PRICE",
            rule_pack_version="1.0.0",
            severity="critical",
            description="MRP altered by adhesive sticker exceeding maximum retail price declaration",
        )
        session.add(violation)
        await session.commit()

    # 4. Submit enforcement docket to eMaap
    docket_resp = await client.post(
        f"/api/v1/integrations/emaap/dockets/{insp_id}",
        json={
            "officer_notes": "Seized 24 packs with forged MRP stickers during market raid.",
            "priority": "URGENT",
        },
    )
    assert docket_resp.status_code == 200
    docket_data = docket_resp.json()
    assert "EMAAP-ENF-" in docket_data["docket_id"]
    assert docket_data["inspection_id"] == insp_id
    assert docket_data["status"] == "ACKNOWLEDGED"
    assert docket_data["violations_count"] == 1
    assert docket_data["photographs_count"] == 1
    assert "https://emaap.gov.in/enforcement/dockets/" in docket_data["portal_tracking_url"]
    assert docket_data["evidence_chain_hash"] is not None

    # 5. Verify audit log entry was created
    async with session_factory() as session:
        logs = await session.execute(
            AuditLog.__table__.select().where(
                AuditLog.action == "emaap_docket_submitted",
                AuditLog.entity_id == insp_id,
            )
        )
        log_rows = logs.fetchall()
        assert len(log_rows) == 1
        log_entry = log_rows[0]
        assert log_entry.after_value["docket_id"] == docket_data["docket_id"]
        assert log_entry.after_value["status"] == "ACKNOWLEDGED"
        assert log_entry.after_value["evidence_chain_hash"] == docket_data["evidence_chain_hash"]
        assert log_entry.entry_hash is not None
        assert len(log_entry.entry_hash) == 64  # SHA-256 hex digest
