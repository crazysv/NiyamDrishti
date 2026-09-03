import uuid
from datetime import datetime, timezone

from app.models.base import ExtractedField, InspectionImage
from app.services.cross_matching.service import MultiImageCrossMatchingService


def make_image(inspection_id: uuid.UUID, role: str) -> InspectionImage:
    return InspectionImage(
        id=uuid.uuid4(),
        inspection_id=inspection_id,
        image_role=role,
        storage_url=f"r2://bucket/{role}.jpg",
        captured_at=datetime.now(timezone.utc),
    )


def make_field(
    inspection_id: uuid.UUID,
    source_img_id: uuid.UUID,
    field_type: str,
    raw: str,
    parsed: str,
) -> ExtractedField:
    return ExtractedField(
        id=uuid.uuid4(),
        inspection_id=inspection_id,
        source_image_id=source_img_id,
        field_type=field_type,
        raw_text=raw,
        parsed_value=parsed,
        confidence=0.95,
        bounding_box={"x": 10, "y": 20, "w": 100, "h": 30},
        verdict="pass",
    )


def test_cross_match_detects_illegal_mrp_sticker_inflation():
    service = MultiImageCrossMatchingService()
    insp_id = uuid.uuid4()

    img_base = make_image(insp_id, "front_pdp")
    img_sticker = make_image(insp_id, "sticker")

    f_base = make_field(insp_id, img_base.id, "mrp", "MRP Rs. 100.00", "Rs. 100.00")
    f_sticker = make_field(insp_id, img_sticker.id, "mrp", "MRP Rs. 135.00", "Rs. 135.00")

    report = service.analyze_cross_image_consistency(
        inspection_id=insp_id,
        images=[img_base, img_sticker],
        fields=[f_base, f_sticker],
    )

    assert report.is_consistent is False
    assert len(report.discrepancies) == 1
    disc = report.discrepancies[0]
    assert disc.discrepancy_type == "mrp_altered_sticker"
    assert disc.severity == "critical"
    assert "Rule 18(2)" in disc.citation
    assert "135.00" in disc.description and "100.00" in disc.description

    # Test conversion to persistent database Violation
    violations = service.to_violations(insp_id, "2026.02.01", report.discrepancies)
    assert len(violations) == 1
    assert violations[0].rule_id == "cross-match-mrp-sticker-increase"
    assert violations[0].severity == "critical"


def test_cross_match_consistent_panels():
    service = MultiImageCrossMatchingService()
    insp_id = uuid.uuid4()

    img_front = make_image(insp_id, "front_pdp")
    img_back = make_image(insp_id, "back_panel")

    fields = [
        make_field(insp_id, img_front.id, "mrp", "MRP Rs. 250.00", "Rs. 250.00"),
        make_field(insp_id, img_back.id, "mrp", "MRP Rs. 250.00 (Incl. of all taxes)", "Rs. 250.00"),
        make_field(insp_id, img_front.id, "net_quantity", "Net Wt: 1 kg", "1 kg"),
        make_field(insp_id, img_back.id, "net_quantity", "Net Quantity: 1 kg", "1 kg"),
    ]

    report = service.analyze_cross_image_consistency(
        inspection_id=insp_id,
        images=[img_front, img_back],
        fields=fields,
    )

    assert report.is_consistent is True
    assert len(report.discrepancies) == 0
    assert "mrp" in report.consistent_fields
    assert "net_quantity" in report.consistent_fields


def test_cross_match_net_quantity_mismatch():
    service = MultiImageCrossMatchingService()
    insp_id = uuid.uuid4()

    img_front = make_image(insp_id, "front_pdp")
    img_back = make_image(insp_id, "back_panel")

    fields = [
        make_field(insp_id, img_front.id, "net_quantity", "500 g", "500 g"),
        make_field(insp_id, img_back.id, "net_quantity", "450 g", "450 g"),
    ]

    report = service.analyze_cross_image_consistency(
        inspection_id=insp_id,
        images=[img_front, img_back],
        fields=fields,
    )

    assert report.is_consistent is False
    assert len(report.discrepancies) == 1
    assert report.discrepancies[0].discrepancy_type == "net_quantity_mismatch"
    assert report.discrepancies[0].severity == "major"
    assert "500 g" in report.discrepancies[0].description
    assert "450 g" in report.discrepancies[0].description


def test_cross_match_ecommerce_net_quantity_mismatch():
    """Verify physical package (450g) vs e-commerce listing (500g) flags critical mismatch (E3-02, Rule 6(10))."""
    service = MultiImageCrossMatchingService()
    insp_id = uuid.uuid4()

    img_physical = make_image(insp_id, "front_pdp")
    img_ecom = make_image(insp_id, "ecommerce_listing")

    fields = [
        make_field(insp_id, img_physical.id, "net_quantity", "Net Wt: 450 g", "450 g"),
        make_field(insp_id, img_ecom.id, "net_quantity", "Pack of 1 (500 g)", "500 g"),
    ]

    report = service.analyze_cross_image_consistency(
        inspection_id=insp_id,
        images=[img_physical, img_ecom],
        fields=fields,
    )

    assert report.is_consistent is False
    assert len(report.discrepancies) == 1
    disc = report.discrepancies[0]
    assert disc.discrepancy_type == "ecommerce_net_quantity_mismatch"
    assert disc.severity == "critical"
    assert "Rule 6(10)" in disc.citation
    assert "450 g" in disc.description and "500 g" in disc.description

    # Verify violation generation
    violations = service.to_violations(insp_id, "2026.02.01", report.discrepancies)
    assert len(violations) == 1
    assert violations[0].rule_id == "cross-match-ecommerce-net-quantity-mismatch"
    assert violations[0].severity == "critical"


def test_cross_match_ecommerce_mrp_overcharging():
    """Verify e-commerce listed price exceeding physical package printed MRP flags critical violation (E3-02, Rule 18(2))."""
    service = MultiImageCrossMatchingService()
    insp_id = uuid.uuid4()

    img_physical = make_image(insp_id, "front_pdp")
    img_ecom = make_image(insp_id, "ecommerce_listing")

    fields = [
        make_field(insp_id, img_physical.id, "mrp", "MRP Rs. 150.00", "Rs. 150.00"),
        make_field(insp_id, img_ecom.id, "mrp", "Price: Rs. 185.00", "Rs. 185.00"),
    ]

    report = service.analyze_cross_image_consistency(
        inspection_id=insp_id,
        images=[img_physical, img_ecom],
        fields=fields,
    )

    assert report.is_consistent is False
    assert len(report.discrepancies) == 1
    disc = report.discrepancies[0]
    assert disc.discrepancy_type == "ecommerce_mrp_inflation"
    assert disc.severity == "critical"
    assert "Rule 18(2)" in disc.citation
    assert "185.00" in disc.description and "150.00" in disc.description


def test_cross_match_ecommerce_origin_mismatch():
    """Verify e-commerce listing claiming India when physical package declares China (E3-02, Rule 6(10) & 6(1)(n))."""
    service = MultiImageCrossMatchingService()
    insp_id = uuid.uuid4()

    img_physical = make_image(insp_id, "back_panel")
    img_ecom = make_image(insp_id, "ecommerce_listing")

    fields = [
        make_field(insp_id, img_physical.id, "country_of_origin", "Made in China", "China"),
        make_field(insp_id, img_ecom.id, "country_of_origin", "Country of Origin: India", "India"),
    ]

    report = service.analyze_cross_image_consistency(
        inspection_id=insp_id,
        images=[img_physical, img_ecom],
        fields=fields,
    )

    assert report.is_consistent is False
    assert len(report.discrepancies) == 1
    disc = report.discrepancies[0]
    assert disc.discrepancy_type == "ecommerce_origin_mismatch"
    assert disc.severity == "major"
    assert "China" in disc.description and "India" in disc.description


def test_cross_match_ecommerce_consistent():
    """Verify physical package matching e-commerce listing cleanly passes with 0 discrepancies."""
    service = MultiImageCrossMatchingService()
    insp_id = uuid.uuid4()

    img_physical = make_image(insp_id, "front_pdp")
    img_ecom = make_image(insp_id, "ecommerce_listing")

    fields = [
        make_field(insp_id, img_physical.id, "net_quantity", "Net Wt: 1 kg", "1 kg"),
        make_field(insp_id, img_ecom.id, "net_quantity", "Quantity: 1 kg", "1 kg"),
        make_field(insp_id, img_physical.id, "mrp", "MRP Rs. 299.00", "Rs. 299.00"),
        make_field(insp_id, img_ecom.id, "mrp", "MRP: Rs. 299.00", "Rs. 299.00"),
    ]

    report = service.analyze_cross_image_consistency(
        inspection_id=insp_id,
        images=[img_physical, img_ecom],
        fields=fields,
    )

    assert report.is_consistent is True
    assert len(report.discrepancies) == 0
    assert "net_quantity" in report.consistent_fields
    assert "mrp" in report.consistent_fields

