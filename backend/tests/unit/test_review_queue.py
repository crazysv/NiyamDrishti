import uuid

from app.services.rules import RuleEngine, load_default_rule_pack


def test_confidence_threshold_routing_in_rule_engine():
    """Verify REV-01: RuleEngine dispatches needs_review when confidence < 0.85."""
    engine = RuleEngine()
    pack = load_default_rule_pack()

    # Provide all mandatory fields, with only MRP having confidence 0.80 (< 0.85)
    mock_fields = [
        {
            "id": uuid.uuid4(),
            "field_type": "mrp",
            "raw_text": "MRP 150.00",
            "confidence": 0.80,
            "bounding_box": {"h": 30},
            "verdict": "pass",
            "reviewed_by_officer": False,
        },
        {
            "id": uuid.uuid4(),
            "field_type": "net_quantity",
            "raw_text": "500g",
            "confidence": 0.95,
            "bounding_box": {"h": 30},
            "verdict": "pass",
            "reviewed_by_officer": False,
        },
        {
            "id": uuid.uuid4(),
            "field_type": "manufacturer_address",
            "raw_text": "Mfg by ABC Ltd, Delhi 110001",
            "confidence": 0.92,
            "bounding_box": {"h": 30},
            "verdict": "pass",
            "reviewed_by_officer": False,
        },
        {
            "id": uuid.uuid4(),
            "field_type": "mfg_date",
            "raw_text": "01/2026",
            "confidence": 0.94,
            "bounding_box": {"h": 30},
            "verdict": "pass",
            "reviewed_by_officer": False,
        },
        {
            "id": uuid.uuid4(),
            "field_type": "consumer_care",
            "raw_text": "care@abc.com",
            "confidence": 0.96,
            "bounding_box": {"h": 30},
            "verdict": "pass",
            "reviewed_by_officer": False,
        },
        {
            "id": uuid.uuid4(),
            "field_type": "country_of_origin",
            "raw_text": "India",
            "confidence": 0.97,
            "bounding_box": {"h": 30},
            "verdict": "pass",
            "reviewed_by_officer": False,
        },
        {
            "id": uuid.uuid4(),
            "field_type": "commodity_name",
            "raw_text": "Tea",
            "confidence": 0.91,
            "bounding_box": {"h": 30},
            "verdict": "pass",
            "reviewed_by_officer": False,
        },
    ]

    images = [{"image_role": "front_pdp", "width_px": 1000, "height_px": 1000, "calibration_scale_mm_per_px": 0.1}]

    summary = engine.evaluate_rules(
        fields=mock_fields,
        images=images,
        commodity_category="packaged_food",
        rule_pack=pack,
    )

    mrp_res = next(r for r in summary.results if r.rule_id == "declaration-present-mrp")
    assert mrp_res.verdict == "needs_review"
    assert "below required" in mrp_res.description or "confidence" in mrp_res.description
    assert summary.overall_status == "needs_review"


def test_officer_override_takes_precedence_over_confidence():
    """Verify REV-02: Officer review confirmation/override produces 'pass' even if original confidence was low."""
    engine = RuleEngine()
    pack = load_default_rule_pack()

    reviewed_field = {
        "id": uuid.uuid4(),
        "field_type": "mrp",
        "raw_text": "MRP 150.00",
        "confidence": 0.65,  # Low OCR confidence
        "bounding_box": {"h": 30},
        "verdict": "pass",
        "reviewed_by_officer": True,
        "officer_override_value": "150.00",
    }

    summary = engine.evaluate_rules(
        fields=[reviewed_field],
        images=[],
        rule_pack=pack,
    )

    mrp_res = next(r for r in summary.results if r.rule_id == "declaration-present-mrp")
    assert mrp_res.verdict == "pass"
    assert "verified by officer" in mrp_res.description.lower() or "confirmed by officer" in mrp_res.description.lower()


def test_officer_mark_not_applicable_exempts_declaration():
    """Verify REV-02: Officer marking not_applicable evaluates to pass without violation."""
    engine = RuleEngine()
    pack = load_default_rule_pack()

    na_field = {
        "id": uuid.uuid4(),
        "field_type": "retail_sale_price",
        "raw_text": None,
        "confidence": 1.0,
        "bounding_box": {},
        "verdict": "not_applicable",
        "reviewed_by_officer": True,
        "officer_override_value": None,
    }

    summary = engine.evaluate_rules(
        fields=[na_field],
        images=[],
        commodity_category="pan_masala",
        rule_pack=pack,
    )

    pm_res = next(r for r in summary.results if r.rule_id == "pan-masala-rsp")
    assert pm_res.verdict == "pass"
    assert "not applicable" in pm_res.description.lower()
