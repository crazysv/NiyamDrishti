import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.session import Base
from app.models.base import AuditLog, ExtractedField, Inspection, RulePack, User
from app.services.rules import load_default_rule_pack

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def json_test_db():
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    officer_id = uuid.uuid4()
    async with async_session() as session:
        officer = User(
            id=officer_id,
            email="json_officer@gov.in",
            password_hash="hashed",
            full_name="JSON Test Officer",
            role="officer",
            region="Delhi",
            is_active=True,
        )
        session.add(officer)
        await session.commit()

    yield {
        "session": async_session,
        "officer_id": officer_id,
    }

    await engine.dispose()


@pytest.mark.asyncio
async def test_rule_pack_rules_json_roundtrip(json_test_db):
    """
    TEST-04: Test RulePack.rules_json JSON persistence, serialization, and deserialization.
    Verifies that nested rules dictionaries, thresholds, citations, and lists round-trip identically.
    """
    session_factory = json_test_db["session"]
    officer_id = json_test_db["officer_id"]
    default_pack = load_default_rule_pack()
    pack_dict = default_pack.model_dump(mode="json")

    pack_version = "2026.09.01"
    async with session_factory() as session:
        rp = RulePack(
            version=pack_version,
            effective_from=datetime(2026, 9, 1, tzinfo=timezone.utc),
            source_citation="LM(PC) Rules 2011 & Gazette Notification S.O. 2026",
            rules_json=pack_dict,
            is_active=True,
            created_by=officer_id,
        )
        session.add(rp)
        await session.commit()

    # Read back in clean session
    async with session_factory() as session:
        stmt = select(RulePack).where(RulePack.version == pack_version)
        res = await session.execute(stmt)
        loaded = res.scalar_one()

        assert isinstance(loaded.rules_json, dict)
        assert loaded.rules_json["rule_pack_version"] == pack_dict["rule_pack_version"]
        assert loaded.rules_json["source_citation"] == pack_dict["source_citation"]
        assert len(loaded.rules_json["rules"]) == len(pack_dict["rules"])

        # Check deep nested structure
        original_first_rule = pack_dict["rules"][0]
        loaded_first_rule = loaded.rules_json["rules"][0]
        assert loaded_first_rule["rule_id"] == original_first_rule["rule_id"]
        assert loaded_first_rule["citation"] == original_first_rule["citation"]
        assert loaded_first_rule["thresholds_mm"] == original_first_rule["thresholds_mm"]


@pytest.mark.asyncio
async def test_extracted_field_bounding_box_and_polygon_roundtrip(json_test_db):
    """
    TEST-04: Test ExtractedField.bounding_box JSON column with floats and 4-point polygon.
    """
    session_factory = json_test_db["session"]
    officer_id = json_test_db["officer_id"]

    insp_id = uuid.uuid4()
    field_id = uuid.uuid4()
    complex_bbox = {
        "x": 124.56,
        "y": 789.12,
        "w": 456.78,
        "h": 32.10,
        "polygon": [
            [124.56, 789.12],
            [581.34, 791.05],
            [580.98, 821.22],
            [124.20, 819.33],
        ],
        "scale_applied": 0.0845,
        "is_calibrated": True,
    }

    async with session_factory() as session:
        insp = Inspection(
            id=insp_id,
            officer_id=officer_id,
            commodity_category="packaged_food",
            status="draft",
            rule_pack_version="2026.02.01",
        )
        session.add(insp)

        img_id = uuid.uuid4()
        field = ExtractedField(
            id=field_id,
            inspection_id=insp_id,
            source_image_id=img_id,
            field_type="net_quantity",
            raw_text="Net Wt. 1 kg",
            parsed_value="1 kg",
            confidence=0.985,
            verdict="pass",
            bounding_box=complex_bbox,
        )
        session.add(field)
        await session.commit()

    # Read back in fresh session
    async with session_factory() as session:
        stmt = select(ExtractedField).where(ExtractedField.id == field_id)
        res = await session.execute(stmt)
        loaded_field = res.scalar_one()

        assert isinstance(loaded_field.bounding_box, dict)
        assert loaded_field.bounding_box["x"] == pytest.approx(124.56)
        assert loaded_field.bounding_box["y"] == pytest.approx(789.12)
        assert loaded_field.bounding_box["polygon"] == complex_bbox["polygon"]
        assert loaded_field.bounding_box["scale_applied"] == complex_bbox["scale_applied"]


@pytest.mark.asyncio
async def test_audit_log_nested_json_mutation_roundtrip(json_test_db):
    """
    TEST-04: Test AuditLog before_value and after_value round-trip with arbitrary nested types.
    """
    session_factory = json_test_db["session"]
    officer_id = json_test_db["officer_id"]
    log_id = uuid.uuid4()

    nested_payload = {
        "action": "override_mrp",
        "changed_fields": ["officer_override_value", "review_notes"],
        "previous": {"val": 450.0, "status": "fail", "nullable_prop": None},
        "updated": {"val": 420.0, "status": "pass", "tags": ["verified", "stamped"]},
        "timestamp_epoch": 1772582400,
        "is_audited": True,
    }

    async with session_factory() as session:
        log = AuditLog(
            id=log_id,
            actor_user_id=officer_id,
            action="field_corrected",
            entity_type="extracted_field",
            entity_id=str(uuid.uuid4()),
            before_value={"val": 450.0, "status": "fail"},
            after_value=nested_payload,
        )
        session.add(log)
        await session.commit()

    async with session_factory() as session:
        stmt = select(AuditLog).where(AuditLog.id == log_id)
        res = await session.execute(stmt)
        loaded_log = res.scalar_one()

        assert isinstance(loaded_log.after_value, dict)
        assert loaded_log.after_value == nested_payload
        assert loaded_log.after_value["updated"]["tags"] == ["verified", "stamped"]
        assert loaded_log.after_value["previous"]["nullable_prop"] is None
