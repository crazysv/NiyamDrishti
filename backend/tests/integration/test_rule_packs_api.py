import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.core.security import create_access_token, get_password_hash
from app.db.session import Base
from app.main import app
from app.models.base import AuditLog, ExtractedField, RulePack, User, Violation
from app.services.rules import load_default_rule_pack

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

    admin_id = uuid.uuid4()
    officer_id = uuid.uuid4()

    async with async_session() as session:
        admin = User(
            id=admin_id,
            email="admin@gov.in",
            password_hash=get_password_hash("AdminPass123!"),
            full_name="Department Administrator",
            role="admin",
            region="National-HQ",
            is_active=True,
        )
        officer = User(
            id=officer_id,
            email="officer@gov.in",
            password_hash=get_password_hash("OfficerPass123!"),
            full_name="Field Officer",
            role="officer",
            region="Delhi-North",
            is_active=True,
        )
        session.add_all([admin, officer])

        # Seed initial active rule pack
        default_pack = load_default_rule_pack()
        seed_pack = RulePack(
            version=default_pack.rule_pack_version,
            effective_from=datetime.combine(default_pack.effective_from, datetime.min.time(), tzinfo=timezone.utc),
            effective_to=None,
            source_citation=default_pack.source_citation,
            rules_json=default_pack.model_dump(mode="json"),
            is_active=True,
            created_by=admin_id,
        )
        session.add(seed_pack)
        await session.commit()

    yield {"session": async_session, "admin_id": admin_id, "officer_id": officer_id}

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_list_and_get_active_rule_packs(test_db):
    """Test GET /rule-packs and GET /rule-packs/active (RULE-05)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(test_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}

        # 1. GET /api/v1/rule-packs
        list_res = await ac.get("/api/v1/rule-packs", headers=headers)
        assert list_res.status_code == 200
        packs = list_res.json()
        assert len(packs) == 1
        assert packs[0]["version"] == "2026.02.01"
        assert packs[0]["is_active"] is True
        assert packs[0]["rule_count"] >= 9

        # 2. GET /api/v1/rule-packs/active
        active_res = await ac.get("/api/v1/rule-packs/active", headers=headers)
        assert active_res.status_code == 200
        active_pack = active_res.json()
        assert active_pack["version"] == "2026.02.01"
        assert "rules" in active_pack["rules_json"]


@pytest.mark.asyncio
async def test_create_and_activate_rule_pack_admin(test_db):
    """Test admin rule pack upload and activation with audit logging (RULE-01, RULE-06)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin_token = create_access_token(test_db["admin_id"])
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        officer_token = create_access_token(test_db["officer_id"])
        officer_headers = {"Authorization": f"Bearer {officer_token}"}

        # 1. Officer cannot upload new rule pack (403)
        new_pack_payload = {
            "version": "2026.05.01",
            "effective_from": "2026-05-01T00:00:00Z",
            "effective_to": None,
            "source_citation": "LM(PC) Third Amendment Rules, 2026",
            "rules_json": {
                "rule_pack_version": "2026.05.01",
                "effective_from": "2026-05-01",
                "effective_to": None,
                "source_citation": "LM(PC) Third Amendment Rules, 2026",
                "rules": [
                    {
                        "rule_id": "declaration-present-mrp",
                        "applies_to": ["all"],
                        "type": "field_required",
                        "field": "mrp",
                        "severity": "critical",
                    }
                ],
            },
        }

        officer_upload = await ac.post("/api/v1/rule-packs", json=new_pack_payload, headers=officer_headers)
        assert officer_upload.status_code == 403

        # 2. Admin uploads with invalid schema (422)
        bad_payload = dict(new_pack_payload)
        bad_payload["rules_json"] = {"rule_pack_version": "2026.05.01", "rules": []}  # min_length=1 required
        bad_upload = await ac.post("/api/v1/rule-packs", json=bad_payload, headers=admin_headers)
        assert bad_upload.status_code == 422

        # 3. Admin uploads successfully (201)
        good_upload = await ac.post("/api/v1/rule-packs", json=new_pack_payload, headers=admin_headers)
        assert good_upload.status_code == 201
        created_pack = good_upload.json()
        assert created_pack["version"] == "2026.05.01"
        assert created_pack["is_active"] is False

        # 4. Activate new rule pack via POST /rule-packs/{version}/activate
        activate_res = await ac.post("/api/v1/rule-packs/2026.05.01/activate", headers=admin_headers)
        assert activate_res.status_code == 200
        assert activate_res.json()["is_active"] is True

        # Verify previous active pack was deactivated
        old_pack_res = await ac.get("/api/v1/rule-packs/2026.02.01", headers=admin_headers)
        assert old_pack_res.json()["is_active"] is False

        # Verify audit logs created
        async with test_db["session"]() as session:
            stmt = select(AuditLog).where(AuditLog.entity_type == "rule_pack")
            logs = list((await session.execute(stmt)).scalars().all())
            actions = [entry.action for entry in logs]
            assert "rule_pack_created" in actions
            assert "rule_pack_activated" in actions


@pytest.mark.asyncio
async def test_freeze_rule_pack_version_and_evaluate(test_db):
    """Verify RULE-07 freeze on creation and evaluation against frozen version."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(test_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create inspection when active rule pack is 2026.02.01
        create_resp = await ac.post(
            "/api/v1/inspections",
            json={"commodity_category": "packaged_food", "captured_offline": False},
            headers=headers,
        )
        assert create_resp.status_code == 201
        inspection_id = create_resp.json()["id"]
        assert create_resp.json()["rule_pack_version"] == "2026.02.01"

        # 2. Add some extracted fields to inspection
        async with test_db["session"]() as session:
            f1 = ExtractedField(
                id=uuid.uuid4(),
                inspection_id=uuid.UUID(inspection_id),
                source_image_id=uuid.uuid4(),
                field_type="mrp",
                raw_text="MRP: 50.00",
                parsed_value="50.00",
                confidence=0.95,
                bounding_box={"x": 10, "y": 10, "w": 50, "h": 20},
                verdict="pass",
                reviewed_by_officer=False,
            )
            # Net quantity is missing
            session.add(f1)
            await session.commit()

        # 3. Evaluate inspection via POST /api/v1/inspections/{id}/evaluate
        eval_resp = await ac.post(f"/api/v1/inspections/{inspection_id}/evaluate", headers=headers)
        assert eval_resp.status_code == 200
        eval_data = eval_resp.json()
        assert eval_data["rule_pack_version"] == "2026.02.01"
        assert eval_data["overall_status"] == "fail"  # because net_quantity and others are missing
        assert len(eval_data["violations"]) > 0

        # Verify violations persisted in database
        async with test_db["session"]() as session:
            v_stmt = select(Violation).where(Violation.inspection_id == uuid.UUID(inspection_id))
            violations = list((await session.execute(v_stmt)).scalars().all())
            assert len(violations) > 0
            # Net quantity missing violation
            net_qty_v = next((v for v in violations if v.rule_id == "declaration-present-net-quantity"), None)
            assert net_qty_v is not None
            assert net_qty_v.severity == "critical"

        # 4. Check GET /api/v1/inspections/{id} includes violations
        get_resp = await ac.get(f"/api/v1/inspections/{inspection_id}", headers=headers)
        assert get_resp.status_code == 200
        assert len(get_resp.json()["violations"]) > 0
