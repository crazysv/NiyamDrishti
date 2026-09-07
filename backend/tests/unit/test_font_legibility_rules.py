import uuid

from app.services.rules.engine import RuleEngine
from app.services.rules.schemas import RuleDefinition


def test_standard_pdp_font_height_evaluation():
    engine = RuleEngine()

    rule = RuleDefinition(
        rule_id="font-size-pdp-net-quantity",
        applies_to=["all"],
        type="font_height_by_pdp_area",
        field="net_quantity",
        thresholds_mm={"50": 1.0, "100": 1.5, "500": 2.0, "2500": 4.0, "gt_2500": 6.0},
        citation="Rule 7 Table 1",
        severity="major",
        requires_calibration=True,
    )

    # 1. Calibrated scale: 0.1 mm/px. Bounding box height: 25px -> 2.5 mm.
    # PDP: 1000px x 1000px -> 100mm x 100mm = 100 cm² PDP area.
    # For PDP 100 cm², required is 1.5 mm. 2.5 mm >= 1.5 mm -> pass!
    field_map = {
        "net_quantity": {
            "id": uuid.uuid4(),
            "bounding_box": {"x": 10, "y": 10, "w": 100, "h": 25},
            "confidence": 0.95,
            "verdict": "pass",
        }
    }

    res = engine._evaluate_font_height(
        rule=rule,
        field_map=field_map,
        calib_scale=0.1,
        pdp_width_px=1000,
        pdp_height_px=1000,
    )
    assert res.verdict == "pass"
    assert res.is_calibrated is True

    # 2. Insufficient height: 12px -> 1.2 mm < 1.5 mm required -> fail!
    field_map_fail = {
        "net_quantity": {
            "id": uuid.uuid4(),
            "bounding_box": {"x": 10, "y": 10, "w": 100, "h": 12},
            "confidence": 0.95,
            "verdict": "pass",
        }
    }
    res_fail = engine._evaluate_font_height(
        rule=rule,
        field_map=field_map_fail,
        calib_scale=0.1,
        pdp_width_px=1000,
        pdp_height_px=1000,
    )
    assert res_fail.verdict == "fail"


def test_blown_embossed_elevated_font_height():
    engine = RuleEngine()

    rule = RuleDefinition(
        rule_id="font-size-blown-embossed",
        applies_to=["blown_glass"],
        type="font_height_blown_embossed",
        field="net_quantity",
        thresholds_mm={"50": 2.0, "100": 3.0, "500": 4.0, "2500": 6.0, "gt_2500": 8.0},
        citation="Rule 7(1) Proviso",
        severity="major",
        requires_calibration=True,
    )

    # PDP: 100 cm². Blown threshold requires 3.0 mm (standard only requires 1.5 mm).
    # Field height 25px * 0.1 mm/px = 2.5 mm.
    # Meets standard (2.5 >= 1.5) BUT fails blown/embossed (2.5 < 3.0)!
    field_map = {
        "net_quantity": {
            "id": uuid.uuid4(),
            "bounding_box": {"x": 10, "y": 10, "w": 100, "h": 25},
            "confidence": 0.95,
            "verdict": "pass",
        }
    }

    res = engine._evaluate_font_height(
        rule=rule,
        field_map=field_map,
        calib_scale=0.1,
        pdp_width_px=1000,
        pdp_height_px=1000,
    )
    assert res.verdict == "fail"
    assert "below the required minimum 3.0mm" in res.description

    # Field height 35px * 0.1 mm/px = 3.5 mm >= 3.0 mm -> pass!
    field_map["net_quantity"]["bounding_box"]["h"] = 35
    res_pass = engine._evaluate_font_height(
        rule=rule,
        field_map=field_map,
        calib_scale=0.1,
        pdp_width_px=1000,
        pdp_height_px=1000,
    )
    assert res_pass.verdict == "pass"


def test_legibility_contrast_check():
    engine = RuleEngine()

    rule = RuleDefinition(
        rule_id="legibility-prominence-contrast",
        applies_to=["all"],
        type="legibility_contrast",
        field="mrp",
        citation="Rule 9(1)",
        severity="major",
    )

    # 1. High contrast / high confidence -> pass
    good_field = {
        "mrp": {
            "id": uuid.uuid4(),
            "bounding_box": {"x": 10, "y": 10, "w": 50, "h": 20},
            "confidence": 0.88,
        }
    }
    assert engine._evaluate_legibility_contrast(rule, good_field).verdict == "pass"

    # 2. Poor contrast / low confidence (< 0.70) -> needs_review
    low_field = {
        "mrp": {
            "id": uuid.uuid4(),
            "bounding_box": {"x": 10, "y": 10, "w": 50, "h": 20},
            "confidence": 0.55,
        }
    }
    res_low = engine._evaluate_legibility_contrast(rule, low_field)
    assert res_low.verdict == "needs_review"
    assert "poor contrast" in res_low.description


def test_uncalibrated_font_height_safety():
    engine = RuleEngine()

    rule = RuleDefinition(
        rule_id="font-size-pdp-net-quantity",
        applies_to=["all"],
        type="font_height_by_pdp_area",
        field="net_quantity",
        thresholds_mm={"50": 1.0, "100": 1.5, "500": 2.0, "2500": 4.0, "gt_2500": 6.0},
        citation="Rule 7",
        severity="major",
        requires_calibration=True,
    )

    field_map = {
        "net_quantity": {
            "id": uuid.uuid4(),
            "bounding_box": {"x": 10, "y": 10, "w": 100, "h": 25},
            "confidence": 0.95,
        }
    }

    # calib_scale is None -> must evaluate to needs_review with is_calibrated=False
    res = engine._evaluate_font_height(
        rule=rule,
        field_map=field_map,
        calib_scale=None,
        pdp_width_px=1000,
        pdp_height_px=1000,
    )
    assert res.verdict == "needs_review"
    assert res.is_calibrated is False
    assert "Uncalibrated measurement" in res.warning
