"""
Integration tests for Bhashini API endpoints (E3-04, ADR-013).
Verifies languages listing, text translation, speech synthesis, and full report translation.
"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.core.security import create_access_token, get_password_hash
from app.db.session import Base
from app.main import app
from app.models.base import ExtractedField, Inspection, User, Violation

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def bhashini_test_db():
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    officer_id = uuid.uuid4()
    insp_id = uuid.uuid4()

    async with async_session() as session:
        officer = User(
            id=officer_id,
            email="bhashini_officer@gov.in",
            password_hash=get_password_hash("Secret123!"),
            full_name="Bhashini Officer",
            role="officer",
            is_active=True,
        )
        inspection = Inspection(
            id=insp_id,
            officer_id=officer_id,
            commodity_category="packaged_food",
            status="needs_review",
            rule_pack_version="2026.02.01",
            created_at=datetime.now(timezone.utc),
        )
        f_mrp = ExtractedField(
            id=uuid.uuid4(),
            inspection_id=insp_id,
            source_image_id=uuid.uuid4(),
            field_type="mrp",
            raw_text="MRP Rs. 200.00",
            parsed_value="Rs. 200.00",
            confidence=0.92,
            bounding_box={"x": 10, "y": 10, "w": 50, "h": 20},
            verdict="pass",
        )
        v = Violation(
            id=uuid.uuid4(),
            inspection_id=insp_id,
            extracted_field_id=f_mrp.id,
            rule_id="cross-match-ecommerce-mrp-inflation",
            rule_pack_version="2026.02.01",
            description="E-commerce listing price exceeds package MRP",
            citation="LM(PC) Rules 2011, Rule 18(2)",
            severity="critical",
        )
        session.add_all([officer, inspection, f_mrp, v])
        await session.commit()

    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[deps.get_db] = override_get_db
    yield {"officer_id": officer_id, "inspection_id": insp_id, "session": async_session}
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_supported_indic_languages(bhashini_test_db):
    """Verify GET /api/v1/bhashini/languages returns 12 Indic regional languages."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/bhashini/languages")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total"] == 12
        codes = [lang["code"] for lang in data["languages"]]
        assert "hi" in codes
        assert "mr" in codes
        assert "ta" in codes


@pytest.mark.asyncio
async def test_translate_text_endpoint(bhashini_test_db):
    """Verify POST /api/v1/bhashini/translate returns translated text."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(bhashini_test_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "text": "net_quantity",
            "source_language": "en",
            "target_language": "hi",
        }
        resp = await ac.post("/api/v1/bhashini/translate", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["source_language"] == "en"
        assert data["target_language"] == "hi"
        assert "शुद्ध मात्रा" in data["translated_text"]


@pytest.mark.asyncio
async def test_tts_speech_endpoint(bhashini_test_db):
    """Verify POST /api/v1/bhashini/tts synthesizes speech audio."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(bhashini_test_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "text": "विधिक मापविज्ञान निरीक्षण",
            "language": "hi",
            "gender": "female",
        }
        resp = await ac.post("/api/v1/bhashini/tts", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["language"] == "hi"
        assert data["audio_format"] == "wav"
        assert len(data["audio_content_base64"]) > 0


@pytest.mark.asyncio
async def test_translate_inspection_report_endpoint(bhashini_test_db):
    """Verify POST /api/v1/bhashini/inspections/{id}/translate returns full report in Hindi."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(bhashini_test_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}
        insp_id = bhashini_test_db["inspection_id"]

        resp = await ac.post(
            f"/api/v1/bhashini/inspections/{insp_id}/translate?target_language=hi",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["inspection_id"] == str(insp_id)
        assert data["target_language"] == "hi"
        assert data["target_language_name"] == "हिन्दी"
        assert len(data["fields"]) >= 1
        assert len(data["violations"]) >= 1
        assert "निरीक्षण परिणाम" in data["summary_narration"]
