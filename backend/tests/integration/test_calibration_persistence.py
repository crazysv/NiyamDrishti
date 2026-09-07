import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import get_password_hash
from app.db.session import Base
from app.models.base import Inspection, InspectionImage, User
from app.services.calibration import CalibrationResult, OpticalCalibrationService

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
async def test_persist_calibration_scale_on_inspection_image(test_session: AsyncSession):
    """Verify persistence of derived mm-per-pixel scale on inspection_images table (CAL-02)."""
    user = User(
        id=uuid.uuid4(),
        email="calib_officer@gov.in",
        password_hash=get_password_hash("Secret123!"),
        full_name="Officer Calibration",
        role="officer",
        region="Delhi-West",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()

    inspection = Inspection(
        id=uuid.uuid4(),
        officer_id=user.id,
        commodity_category="general",
        status="processing",
        rule_pack_version="2026.02.01",
    )
    test_session.add(inspection)
    await test_session.commit()

    image = InspectionImage(
        id=uuid.uuid4(),
        inspection_id=inspection.id,
        image_role="front_pdp",
        storage_url="local://images/ean13_sample.jpg",
        width_px=1200,
        height_px=1600,
        quality_check_passed=True,
        captured_at=datetime.now(timezone.utc),
        calibration_scale_mm_per_px=None,
    )
    test_session.add(image)
    await test_session.commit()

    # Derived calibration result
    calib = CalibrationResult(
        is_calibrated=True,
        scale_mm_per_px=0.0754,
        barcode_type="EAN-13",
        barcode_data="8901234567890",
        barcode_width_px=494.56,
        nominal_width_mm=37.29,
        method="barcode_ean13",
    )

    service = OpticalCalibrationService()
    await service.persist_calibration(
        db=test_session,
        image_id=image.id,
        calibration=calib,
    )

    # Verify updated record
    result = await test_session.execute(select(InspectionImage).where(InspectionImage.id == image.id))
    persisted_image = result.scalar_one()

    assert persisted_image.calibration_scale_mm_per_px is not None
    assert pytest.approx(float(persisted_image.calibration_scale_mm_per_px), 0.0001) == 0.0754
