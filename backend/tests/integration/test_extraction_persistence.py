import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import get_password_hash
from app.db.session import Base
from app.models.base import ExtractedField, Inspection, InspectionImage, User
from app.services.extraction import DeclarationExtractionService, ExtractedDeclaration

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


@pytest.mark.asyncio
async def test_save_extracted_fields_persistence(test_session: AsyncSession):
    """Verify database persistence of ExtractedDeclaration items into extracted_fields table (EXT-01)."""
    # Create test user
    user = User(
        id=uuid.uuid4(),
        email="extractor_officer@gov.in",
        password_hash=get_password_hash("Secret123!"),
        full_name="Officer Extraction",
        role="officer",
        region="Delhi-Central",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()

    # Create test inspection
    inspection = Inspection(
        id=uuid.uuid4(),
        officer_id=user.id,
        commodity_category="food",
        status="processing",
        rule_pack_version="2026.02.01",
    )
    test_session.add(inspection)
    await test_session.commit()

    from datetime import datetime, timezone

    # Create test inspection image
    image = InspectionImage(
        id=uuid.uuid4(),
        inspection_id=inspection.id,
        image_role="front_pdp",
        storage_url="local://images/sample_label.jpg",
        width_px=800,
        height_px=600,
        quality_check_passed=True,
        captured_at=datetime.now(timezone.utc),
    )
    test_session.add(image)
    await test_session.commit()

    # Prepare declarations
    declarations = [
        ExtractedDeclaration(
            field_type="mrp",
            raw_text="MRP Rs. 150.00 (Incl. of all taxes)",
            parsed_value='{"amount": 150.0, "currency": "INR", "inclusive_of_all_taxes": true}',
            confidence=0.95,
            bounding_box={"x": 50.0, "y": 100.0, "w": 200.0, "h": 30.0},
            source_image_id=str(image.id),
            verdict="pass",
        ),
        ExtractedDeclaration(
            field_type="net_quantity",
            raw_text="Net Weight: 500 g",
            parsed_value='{"value": 500.0, "unit": "g"}',
            confidence=0.93,
            bounding_box={"x": 50.0, "y": 140.0, "w": 180.0, "h": 25.0},
            source_image_id=str(image.id),
            verdict="pass",
        ),
    ]

    service = DeclarationExtractionService()
    saved = await service.save_extracted_fields(
        db=test_session,
        inspection_id=inspection.id,
        declarations=declarations,
    )

    assert len(saved) == 2

    # Query from DB to verify persistence and relations
    result = await test_session.execute(select(ExtractedField).where(ExtractedField.inspection_id == inspection.id))
    db_fields = result.scalars().all()
    assert len(db_fields) == 2

    field_types = {f.field_type for f in db_fields}
    assert field_types == {"mrp", "net_quantity"}

    mrp_field = next(f for f in db_fields if f.field_type == "mrp")
    assert float(mrp_field.confidence) == 0.95
    assert mrp_field.verdict == "pass"
    assert mrp_field.bounding_box["x"] == 50.0
    assert mrp_field.source_image_id == image.id
