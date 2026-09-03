"""
Unit tests for confidence threshold tuning (E2-08, REV-01, ADR-012).
Verifies that per-field tuned thresholds correctly guide automated pass vs needs_review routing.
"""

import uuid
from app.core.config import get_field_confidence_threshold, settings
from app.services.rules import RuleEngine, load_default_rule_pack


def test_field_confidence_threshold_mapping():
    """Verify calibrated field-specific thresholds match ADR-012 pilot specs."""
    assert get_field_confidence_threshold("mrp") == 0.82
    assert get_field_confidence_threshold("net_quantity") == 0.80
    assert get_field_confidence_threshold("date_of_manufacture") == 0.80
    assert get_field_confidence_threshold("manufacturer_address") == 0.78
    assert get_field_confidence_threshold("consumer_care") == 0.80
    assert get_field_confidence_threshold("country_of_origin") == 0.85
    assert get_field_confidence_threshold("dimensions_and_count") == 0.80
    assert get_field_confidence_threshold("importer_packer") == 0.78
    assert get_field_confidence_threshold("retail_sale_price") == 0.85


def test_threshold_normalization_and_fallback():
    """Verify case-insensitivity, hyphen normalization, and unlisted fallbacks."""
    assert get_field_confidence_threshold("NET-QUANTITY") == 0.80
    assert get_field_confidence_threshold("Manufacturer_Address") == 0.78
    assert get_field_confidence_threshold("retail-sale-price") == 0.85
    # Unlisted field should fallback to global baseline
    assert get_field_confidence_threshold("unknown_custom_declaration") == settings.REVIEW_CONFIDENCE_THRESHOLD
    assert get_field_confidence_threshold(None) == settings.REVIEW_CONFIDENCE_THRESHOLD


def test_rule_engine_net_quantity_tuned_routing():
    """
    Verify net_quantity evaluated at 0.81 confidence passes, whereas under 0.80 routes to needs_review.
    With old flat 0.85 threshold, 0.81 would have produced a false review-queue routing.
    """
    engine = RuleEngine()
    pack = load_default_rule_pack()

    # 1. Net quantity at 0.81 confidence (above tuned 0.80) -> PASS
    field_pass = [
        {
            "id": uuid.uuid4(),
            "field_type": "net_quantity",
            "raw_text": "Net Wt: 5 kg",
            "confidence": 0.81,
            "bounding_box": {"h": 40},
            "verdict": "pass",
        }
    ]
    summary_pass = engine.evaluate_rules(
        fields=field_pass,
        images=[],
        commodity_category="packaged_food",
        rule_pack=pack,
    )
    nq_pass = next(r for r in summary_pass.results if r.rule_id == "declaration-present-net-quantity")
    assert nq_pass.verdict == "pass"

    # 2. Net quantity at 0.78 confidence (below tuned 0.80) -> NEEDS_REVIEW
    field_review = [
        {
            "id": uuid.uuid4(),
            "field_type": "net_quantity",
            "raw_text": "Net Wt: 5 kg",
            "confidence": 0.78,
            "bounding_box": {"h": 40},
            "verdict": "pass",
        }
    ]
    summary_review = engine.evaluate_rules(
        fields=field_review,
        images=[],
        commodity_category="packaged_food",
        rule_pack=pack,
    )
    nq_review = next(r for r in summary_review.results if r.rule_id == "declaration-present-net-quantity")
    assert nq_review.verdict == "needs_review"
    assert "below required 80%" in nq_review.description


def test_rule_engine_address_and_origin_tuned_routing():
    """
    Verify manufacturer_address at 0.79 passes (tuned 0.78) while country_of_origin at 0.82 routes to review (tuned 0.85).
    """
    engine = RuleEngine()
    pack = load_default_rule_pack()

    fields = [
        {
            "id": uuid.uuid4(),
            "field_type": "manufacturer_address",
            "raw_text": "Himalayan Foods Ltd, Sector 18, Gurugram - 122001",
            "confidence": 0.79,
            "bounding_box": {"h": 50},
            "verdict": "pass",
        },
        {
            "id": uuid.uuid4(),
            "field_type": "country_of_origin",
            "raw_text": "Country of Origin: India",
            "confidence": 0.82,  # Below strict 0.85 threshold
            "bounding_box": {"h": 30},
            "verdict": "pass",
        },
    ]

    summary = engine.evaluate_rules(
        fields=fields,
        images=[],
        commodity_category="packaged_food",
        rule_pack=pack,
    )

    addr_res = next(r for r in summary.results if r.rule_id == "declaration-present-manufacturer-address")
    assert addr_res.verdict == "pass"

    origin_res = next(r for r in summary.results if r.rule_id == "declaration-present-country-of-origin")
    assert origin_res.verdict == "needs_review"
    assert "below required 85%" in origin_res.description
