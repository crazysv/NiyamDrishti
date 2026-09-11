import uuid
from datetime import datetime, timezone

from app.api.v1.endpoints.inspections import _violation_requires_officer_review
from app.schemas.inspection import ViolationRead


def _violation(description: str, severity: str = "major") -> ViolationRead:
    return ViolationRead(
        id=uuid.uuid4(),
        inspection_id=uuid.uuid4(),
        extracted_field_id=uuid.uuid4(),
        rule_id="font-size-pdp-net-quantity",
        rule_pack_version="2026.02.01",
        description=description,
        citation="Rule 7",
        severity=severity,
        created_at=datetime.now(timezone.utc),
    )


def test_uncalibrated_font_check_is_review_not_failure():
    violation = _violation("Font height evaluated via uncalibrated PDP ratio. Optical calibration reference missing.")

    assert _violation_requires_officer_review(violation) is True


def test_confirmed_font_shortfall_remains_a_failure():
    violation = _violation("Font height of 0.80mm is below the required minimum 1.0mm for PDP area 40.0cm².")

    assert _violation_requires_officer_review(violation) is False
