import uuid

import pytest
from pydantic import ValidationError

from app.services.rules import (
    RuleEngine,
    load_default_rule_pack,
)
from app.services.rules.schemas import RuleDefinition


def test_default_rule_pack_schema_valid():
    """Verify v1 core rule pack matches RulePackSchema (RULE-01, RULE-02, RULE-03)."""
    pack = load_default_rule_pack()
    assert pack.rule_pack_version == "2026.02.01"
    assert pack.effective_from.isoformat() == "2026-02-01"
    assert len(pack.rules) >= 9

    # Check MRP rule presence
    mrp_rule = next(r for r in pack.rules if r.rule_id == "declaration-present-mrp")
    assert mrp_rule.field == "mrp"
    assert mrp_rule.severity == "critical"
    assert "Rule 6" in (mrp_rule.citation or "")

    # Check font-size PDP rule (RULE-03)
    font_rule = next(r for r in pack.rules if r.rule_id == "font-size-pdp-net-quantity")
    assert font_rule.type == "font_height_by_pdp_area"
    assert font_rule.requires_calibration is True
    assert font_rule.thresholds_mm is not None
    assert font_rule.thresholds_mm["50"] == 1.0

    # Check category rule: pan masala RSP
    pm_rule = next(r for r in pack.rules if r.rule_id == "pan-masala-rsp")
    assert "pan_masala" in pm_rule.applies_to
    assert pm_rule.field == "retail_sale_price"


def test_rule_definition_validation_errors():
    """Test schema validation errors on invalid rule definitions (RULE-01)."""
    # field_required missing field
    with pytest.raises(ValidationError):
        RuleDefinition(
            rule_id="invalid-req",
            applies_to=["all"],
            type="field_required",
            field=None,
        )

    # font_height missing thresholds
    with pytest.raises(ValidationError):
        RuleDefinition(
            rule_id="invalid-font",
            applies_to=["all"],
            type="font_height_by_pdp_area",
            field="net_quantity",
            thresholds_mm=None,
        )


def test_rule_engine_field_required_pass_and_fail():
    """Test standard field presence checks (RULE-04)."""
    engine = RuleEngine()
    pack = load_default_rule_pack()

    # Case 1: All required declarations are present
    mock_fields = [
        {
            "id": uuid.uuid4(),
            "field_type": "mrp",
            "raw_text": "MRP: 99.00",
            "confidence": 0.95,
            "bounding_box": {"h": 40},
        },
        {
            "id": uuid.uuid4(),
            "field_type": "net_quantity",
            "raw_text": "Net: 500g",
            "confidence": 0.90,
            "bounding_box": {"h": 35},
        },
        {
            "id": uuid.uuid4(),
            "field_type": "manufacturer_address",
            "raw_text": "Mfg by ABC Ltd, Delhi - 110001",
            "confidence": 0.88,
            "bounding_box": {"h": 50},
        },
        {
            "id": uuid.uuid4(),
            "field_type": "mfg_date",
            "raw_text": "Mfg: 03/2026",
            "confidence": 0.92,
            "bounding_box": {"h": 30},
        },
        {
            "id": uuid.uuid4(),
            "field_type": "consumer_care",
            "raw_text": "customercare@abc.com",
            "confidence": 0.94,
            "bounding_box": {"h": 30},
        },
        {
            "id": uuid.uuid4(),
            "field_type": "country_of_origin",
            "raw_text": "Made in India",
            "confidence": 0.96,
            "bounding_box": {"h": 28},
        },
        {
            "id": uuid.uuid4(),
            "field_type": "commodity_name",
            "raw_text": "Roasted Almonds",
            "confidence": 0.91,
            "bounding_box": {"h": 45},
        },
    ]

    images = [{"image_role": "front_pdp", "width_px": 1000, "height_px": 1500, "calibration_scale_mm_per_px": 0.08}]

    summary = engine.evaluate_rules(
        fields=mock_fields,
        images=images,
        commodity_category="packaged_food",
        rule_pack=pack,
    )

    # All 7 mandatory declarations are present and calibrated font height is evaluated
    mrp_res = next(r for r in summary.results if r.rule_id == "declaration-present-mrp")
    assert mrp_res.verdict == "pass"

    # Pan masala RSP rule should not apply to packaged_food
    assert not any(r.rule_id == "pan-masala-rsp" for r in summary.results)


def test_rule_engine_category_scoping():
    """Pan masala RSP rule triggers when commodity_category is pan_masala."""
    engine = RuleEngine()
    pack = load_default_rule_pack()

    mock_fields = [
        {"id": uuid.uuid4(), "field_type": "mrp", "raw_text": "MRP 10", "confidence": 0.95, "bounding_box": {"h": 30}},
    ]

    summary = engine.evaluate_rules(
        fields=mock_fields,
        images=[],
        commodity_category="pan_masala",
        rule_pack=pack,
    )

    # pan-masala-rsp rule must be evaluated and fail because retail_sale_price is missing
    pm_res = next(r for r in summary.results if r.rule_id == "pan-masala-rsp")
    assert pm_res.verdict == "fail"
    assert summary.overall_status == "fail"


def test_rule_engine_font_height_calibrated():
    """Calibrated font height check against PDP area brackets (RULE-03)."""
    engine = RuleEngine()
    pack = load_default_rule_pack()

    # Image: 1000x1000px, scale=0.1 mm/px -> PDP dimensions: 100mm x 100mm -> Area = 100 cm²
    # Threshold for 100 cm² is 1.5 mm
    # Net quantity font height: 25px * 0.1 mm/px = 2.5 mm -> >= 1.5 mm -> PASS
    mock_fields_pass = [
        {
            "id": uuid.uuid4(),
            "field_type": "net_quantity",
            "raw_text": "500g",
            "confidence": 0.95,
            "bounding_box": {"h": 25},
        },
        {"id": uuid.uuid4(), "field_type": "mrp", "raw_text": "100", "confidence": 0.95, "bounding_box": {"h": 30}},
    ]
    images = [{"image_role": "front_pdp", "width_px": 1000, "height_px": 1000, "calibration_scale_mm_per_px": 0.1}]

    summary_pass = engine.evaluate_rules(fields=mock_fields_pass, images=images, rule_pack=pack)
    font_res_pass = next(r for r in summary_pass.results if r.rule_id == "font-size-pdp-net-quantity")
    assert font_res_pass.verdict == "pass"
    assert font_res_pass.is_calibrated is True

    # Sub-test Fail: Font height 10px * 0.1 mm/px = 1.0 mm < 1.5 mm -> FAIL
    mock_fields_fail = [
        {
            "id": uuid.uuid4(),
            "field_type": "net_quantity",
            "raw_text": "500g",
            "confidence": 0.95,
            "bounding_box": {"h": 10},
        },
        {"id": uuid.uuid4(), "field_type": "mrp", "raw_text": "100", "confidence": 0.95, "bounding_box": {"h": 30}},
    ]
    summary_fail = engine.evaluate_rules(fields=mock_fields_fail, images=images, rule_pack=pack)
    font_res_fail = next(r for r in summary_fail.results if r.rule_id == "font-size-pdp-net-quantity")
    assert font_res_fail.verdict == "fail"
    assert "below the required minimum" in font_res_fail.description


def test_rule_engine_font_height_uncalibrated_fallback():
    """Uncalibrated fallback path flags needs_review without asserting false precision (CAL-03, RULE-03)."""
    engine = RuleEngine()
    pack = load_default_rule_pack()

    mock_fields = [
        {
            "id": uuid.uuid4(),
            "field_type": "net_quantity",
            "raw_text": "500g",
            "confidence": 0.95,
            "bounding_box": {"h": 25},
        },
        {"id": uuid.uuid4(), "field_type": "mrp", "raw_text": "100", "confidence": 0.95, "bounding_box": {"h": 30}},
    ]
    # No calibration scale
    images = [{"image_role": "front_pdp", "width_px": 1000, "height_px": 1500, "calibration_scale_mm_per_px": None}]

    summary = engine.evaluate_rules(fields=mock_fields, images=images, rule_pack=pack)
    font_res = next(r for r in summary.results if r.rule_id == "font-size-pdp-net-quantity")
    assert font_res.verdict == "needs_review"
    assert font_res.is_calibrated is False
    assert font_res.warning is not None
    assert "uncalibrated" in font_res.warning.lower()
