"""
Integration tests for Batch / Warehouse Scanning Mode API (E3-05, MASTER_CONTENT.md §10.13).
Verifies warehouse session creation, rapid SKU intake, session completion, and manifest generation.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.core.security import create_access_token, get_password_hash
from app.db.session import Base
from app.main import app
from app.models.base import Inspection, User, Violation

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def batch_test_db():
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    officer_id = uuid.uuid4()

    async with async_session() as session:
        officer = User(
            id=officer_id,
            email="warehouse_officer@gov.in",
            password_hash=get_password_hash("Secret123!"),
            full_name="Warehouse Officer",
            role="officer",
            region="North Zone",
            is_active=True,
        )
        session.add(officer)
        await session.commit()

    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[deps.get_db] = override_get_db
    yield {"officer_id": officer_id, "session": async_session}
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_and_list_batch_session(batch_test_db):
    """Verify creating a warehouse batch session and listing it with metrics."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(batch_test_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "session_name": "Blinkit Fulfillment Center Raid 04",
            "premises_name": "Blinkit DC Okhla",
            "premises_address": "Plot 14, Okhla Phase 3, New Delhi",
            "region": "Delhi",
            "notes": "Targeting edible oils and packaged confectionery",
        }

        resp = await ac.post("/api/v1/batches", json=payload, headers=headers)
        assert resp.status_code == 201
        data = resp.json()

        assert data["session_name"] == "Blinkit Fulfillment Center Raid 04"
        assert data["status"] == "active"
        assert data["total_skus_scanned"] == 0
        batch_id = data["id"]

        # List batches
        list_resp = await ac.get("/api/v1/batches", headers=headers)
        assert list_resp.status_code == 200
        batches = list_resp.json()
        assert len(batches) >= 1
        assert any(b["id"] == batch_id for b in batches)


@pytest.mark.asyncio
async def test_rapid_sku_intake_and_manifest_generation(batch_test_db):
    """Verify rapid multi-SKU creation within a batch and generating the warehouse audit manifest."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        token = create_access_token(batch_test_db["officer_id"])
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create batch session
        b_resp = await ac.post(
            "/api/v1/batches",
            json={"session_name": "BigBasket Hub Audit"},
            headers=headers,
        )
        batch_id = b_resp.json()["id"]

        # 2. Rapidly add 2 SKUs to the batch session
        sku1_resp = await ac.post(
            f"/api/v1/batches/{batch_id}/inspections",
            json={"commodity_category": "packaged_food", "rule_pack_version": "2026.02.01"},
            headers=headers,
        )
        assert sku1_resp.status_code == 201
        sku1_id = sku1_resp.json()["id"]

        sku2_resp = await ac.post(
            f"/api/v1/batches/{batch_id}/inspections",
            json={"commodity_category": "edible_oil", "rule_pack_version": "2026.02.01"},
            headers=headers,
        )
        assert sku2_resp.status_code == 201
        sku2_id = sku2_resp.json()["id"]

        # 3. Simulate processing: SKU 1 passes, SKU 2 has an altered MRP sticker violation
        async with batch_test_db["session"]() as session:
            # Update SKU 1 to completed (compliant)
            await session.execute(
                Inspection.__table__.update().where(Inspection.id == uuid.UUID(sku1_id)).values(status="completed")
            )

            # Update SKU 2 to completed (non-compliant with violation)
            await session.execute(
                Inspection.__table__.update().where(Inspection.id == uuid.UUID(sku2_id)).values(status="completed")
            )
            v = Violation(
                id=uuid.uuid4(),
                inspection_id=uuid.UUID(sku2_id),
                rule_id="cross-match-mrp-sticker-increase",
                rule_pack_version="2026.02.01",
                description="Altered sticker price exceeds original MRP",
                citation="LM(PC) Rules 2011, Rule 18(2)",
                severity="critical",
            )
            session.add(v)
            await session.commit()

        # 4. Fetch detailed batch view
        detail_resp = await ac.get(f"/api/v1/batches/{batch_id}", headers=headers)
        assert detail_resp.status_code == 200
        detail = detail_resp.json()

        assert detail["total_skus_scanned"] == 2
        assert detail["compliant_count"] == 1
        assert detail["non_compliant_count"] == 1
        assert detail["compliance_rate_pct"] == 50.0
        assert len(detail["items"]) == 2

        # 5. Complete the batch session
        complete_resp = await ac.post(f"/api/v1/batches/{batch_id}/complete", headers=headers)
        assert complete_resp.status_code == 200
        assert complete_resp.json()["status"] == "completed"
        assert complete_resp.json()["completed_at"] is not None

        # 6. Fetch warehouse audit manifest
        manifest_resp = await ac.get(f"/api/v1/batches/{batch_id}/manifest", headers=headers)
        assert manifest_resp.status_code == 200
        manifest = manifest_resp.json()

        assert manifest["session_id"] == batch_id
        assert manifest["total_skus"] == 2
        assert manifest["compliant_skus"] == 1
        assert manifest["non_compliant_skus"] == 1
        assert manifest["total_violations"] == 1
        assert "cross-match-mrp-sticker-increase" in manifest["violations_by_rule"]
        assert len(manifest["items"]) == 2
