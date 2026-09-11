import json

from app.services.extraction import (
    COMMODITY_CATEGORIES,
    CommodityNameExtractor,
    ConsumerCareExtractor,
    CountryOfOriginExtractor,
    DeclarationExtractionService,
    ManufacturerAddressExtractor,
    MfgDateExtractor,
    MRPExtractor,
    NetQuantityExtractor,
    get_category_by_id,
)
from app.services.ocr import BoundingBox, OCRLine


def create_ocr_line(text: str, line_num: int = 1, conf: float = 0.95) -> OCRLine:
    """Helper to create dummy OCR lines with valid geometry."""
    return OCRLine(
        text=text,
        confidence=conf,
        bounding_box=BoundingBox(x=10.0, y=float(line_num * 30), w=200.0, h=25.0),
        source_image_id="img_test_123",
        line_number=line_num,
    )


def test_mrp_extractor_with_inclusive_taxes():
    """Verify MRP extraction with tax inclusion statement (EXT-02)."""
    extractor = MRPExtractor()
    lines = [
        create_ocr_line("M.R.P. Rs. 249.50 (Incl. of all taxes)", 1),
    ]

    declarations = extractor.extract(lines, "img_test_123")
    assert len(declarations) == 1
    decl = declarations[0]
    assert decl.field_type == "mrp"
    assert decl.verdict == "pass"

    data = json.loads(decl.parsed_value)
    assert data["amount"] == 249.50
    assert data["currency"] == "INR"
    assert data["inclusive_of_all_taxes"] is True


def test_mrp_extractor_does_not_treat_address_abbreviation_as_price_label():
    """A pincode following H.P. must never become a synthetic MRP value."""
    extractor = MRPExtractor()
    lines = [
        create_ocr_line("For MRP incl. of all taxes, refer coding panel", 1),
        create_ocr_line("Plot No. 78, Baddi, H.P. 174103", 2),
    ]

    assert extractor.extract(lines, "img_test_123") == []


def test_mrp_extractor_without_inclusive_taxes():
    """Verify MRP extraction flags needs_review when tax statement is missing (EXT-02)."""
    extractor = MRPExtractor()
    lines = [create_ocr_line("MRP: Rs 199.00", 1)]

    declarations = extractor.extract(lines, "img_test_123")
    assert len(declarations) == 1
    decl = declarations[0]
    assert decl.verdict == "needs_review"
    data = json.loads(decl.parsed_value)
    assert data["amount"] == 199.00
    assert data["inclusive_of_all_taxes"] is False


def test_mrp_extractor_associates_header_and_currency_value_across_panels():
    """A price value may be in a different OCR region/panel than its MRP label."""
    extractor = MRPExtractor()
    lines = [
        create_ocr_line("For MRP ₹ (incl. of all taxes)", 1),
        create_ocr_line("Rs.36.00, Rs.0.07/ml", 2),
    ]
    lines[0].source_image_id = "back-panel"
    lines[1].source_image_id = "front-panel"

    declarations = extractor.extract(lines, "")

    assert len(declarations) == 1
    assert json.loads(declarations[0].parsed_value)["amount"] == 36.0
    assert declarations[0].source_image_id == "front-panel"


def test_mrp_extractor_does_not_treat_coding_license_as_unit_sale_price():
    """A slash in a manufacturing code must not create a fake USP value."""
    extractor = MRPExtractor()
    lines = [
        create_ocr_line("MRP Rs. 200.00 (Incl. of all taxes)", 1),
        create_ocr_line("M. LIC. NO. M 20/C/UA/2006", 2),
    ]

    declarations = extractor.extract(lines, "img_test_123")

    assert len(declarations) == 1
    data = json.loads(declarations[0].parsed_value)
    assert data["amount"] == 200.0
    assert "unit_sale_price" not in data


def test_net_quantity_extractor_standardization():
    """Verify net quantity extraction and metric unit standardization (EXT-03)."""
    extractor = NetQuantityExtractor()
    test_cases = [
        ("Net Weight: 500 GMS", 500.0, "g"),
        ("Net Wt. 1.25 kg", 1.25, "kg"),
        ("Net Volume: 750 ML", 750.0, "ml"),
        ("Net Qty: 2 Litres", 2.0, "l"),
        ("Quantity: 10 N", 10.0, "pieces"),
    ]

    for text, expected_val, expected_unit in test_cases:
        lines = [create_ocr_line(text, 1)]
        decls = extractor.extract(lines, "img_test_123")
        assert len(decls) == 1
        data = json.loads(decls[0].parsed_value)
        assert data["value"] == expected_val
        assert data["unit"] == expected_unit


def test_manufacturer_address_extractor_with_pincode():
    """Verify manufacturer address extraction with 6-digit Indian PIN code (EXT-04)."""
    extractor = ManufacturerAddressExtractor()
    lines = [
        create_ocr_line("Manufactured by: Niyam Agro Foods Ltd.", 1),
        create_ocr_line("Plot 42, Industrial Area, Phase II", 2),
        create_ocr_line("Gurugram, Haryana 122015", 3),
    ]

    decls = extractor.extract(lines, "img_test_123")
    assert len(decls) == 1
    decl = decls[0]
    assert decl.field_type == "manufacturer_address"
    assert decl.verdict == "pass"

    data = json.loads(decl.parsed_value)
    assert data["role"] == "manufacturer"
    assert data["pincode"] == "122015"
    assert data["has_valid_pincode"] is True
    assert "Niyam Agro Foods" in data["name_and_address"]


def test_mfg_date_extractor():
    """Verify month and year of manufacture extraction (EXT-05)."""
    extractor = MfgDateExtractor()
    lines = [
        create_ocr_line("Mfg Date: 08/2026", 1),
    ]

    decls = extractor.extract(lines, "img_test_123")
    assert len(decls) == 1
    data = json.loads(decls[0].parsed_value)
    assert data["month"] == "08"
    assert data["year"] == "2026"
    assert data["formatted"] == "08/2026"


def test_consumer_care_extractor():
    """Verify consumer care phone number and email extraction (EXT-06)."""
    extractor = ConsumerCareExtractor()
    lines = [
        create_ocr_line("For feedback or complaints, contact Consumer Care Cell:", 1),
        create_ocr_line("Toll Free: 1800 120 4567, Email: care@niyamfoods.in", 2),
    ]

    decls = extractor.extract(lines, "img_test_123")
    assert len(decls) == 1
    data = json.loads(decls[0].parsed_value)
    assert "1800 120 4567" in data["phone"]
    assert data["email"] == "care@niyamfoods.in"
    assert data["has_email"] is True
    assert data["has_phone"] is True


def test_consumer_care_extractor_accepts_indian_landline_with_country_code():
    """Consumer-care labels commonly print a +91 STD-code landline."""
    extractor = ConsumerCareExtractor()
    lines = [create_ocr_line("Customer Care: Call +91 33 4014 2100, care@example.in", 1)]

    decls = extractor.extract(lines, "img_test_123")

    assert len(decls) == 1
    data = json.loads(decls[0].parsed_value)
    assert data["phone"] == "+91 33 4014 2100"
    assert data["has_phone"] is True


def test_country_of_origin_extractor():
    """Verify Country of Origin declaration extraction (EXT-07)."""
    extractor = CountryOfOriginExtractor()
    lines = [
        create_ocr_line("Country of Origin: India", 1),
    ]

    decls = extractor.extract(lines, "img_test_123")
    assert len(decls) == 1
    data = json.loads(decls[0].parsed_value)
    assert data["country"] == "INDIA"


def test_commodity_name_extractor():
    """Verify generic/common commodity name extraction (EXT-08)."""
    extractor = CommodityNameExtractor()
    lines = [
        create_ocr_line("Name of the Commodity: Refined Sunflower Oil", 1),
    ]

    decls = extractor.extract(lines, "img_test_123")
    assert len(decls) == 1
    data = json.loads(decls[0].parsed_value)
    assert data["commodity_name"] == "Refined Sunflower Oil"


def test_commodity_name_extractor_removes_trim_instruction_and_ignores_storage_text():
    """Packaging instructions must not replace a generic commodity title."""
    extractor = CommodityNameExtractor()
    lines = [
        create_ocr_line("CUT HERE Mother Dairy Full Cream Milk", 1),
        create_ocr_line("stored refrigerated below 8 C", 2),
    ]

    decls = extractor.extract(lines, "img_test_123")

    assert len(decls) == 1
    data = json.loads(decls[0].parsed_value)
    assert data["commodity_name"] == "Mother Dairy Full Cream Milk"


def test_commodity_name_extractor_ignores_promotion_price_and_prose_blocks():
    """Merged Gemini blocks must retain only plausible visual title fragments."""
    extractor = CommodityNameExtractor()
    lines = [
        create_ocr_line("100% QUALITY GUARANTEED MOTHER\nDAIRY Full cream\nmilk Rs.36.00, Rs.0.07/ml", 1),
        create_ocr_line("when product is stored refrigerated below 8 C", 2),
    ]

    decls = extractor.extract(lines, "img_test_123")

    assert len(decls) == 1
    data = json.loads(decls[0].parsed_value)
    assert data["commodity_name"] == "MOTHER DAIRY Full cream"


def test_commodity_name_extractor_rejects_guarantee_and_nutrition_claims():
    """A label claim is not a product title merely because it contains a brand."""
    extractor = CommodityNameExtractor()
    lines = [
        create_ocr_line("MOTHER DAIRY GUARANTEED AFTER 29 TESTS", 1),
        create_ocr_line("MOTHER DAIRY SNF: 9.0% (min.) Nutrients", 2),
    ]

    assert extractor.extract(lines, "img_test_123") == []


def test_commodity_name_extractor_rejects_marketing_claim_suffix():
    """A product title must not absorb nearby performance-marketing copy."""
    extractor = CommodityNameExtractor()
    lines = [
        create_ocr_line("Colgate Anticavity Fluoride Toothpaste", 1),
        create_ocr_line("Starts Whitening in 1 Week with Whitening Accelerators", 2),
    ]

    decls = extractor.extract(lines, "img_test_123")

    assert len(decls) == 1
    assert json.loads(decls[0].parsed_value)["commodity_name"] == "Colgate Anticavity Fluoride Toothpaste"


def test_commodity_name_extractor_rejects_net_content_caution_block():
    """A statutory quantity plus safety warning is not a product title."""
    extractor = CommodityNameExtractor()
    lines = [create_ocr_line("NET CONTENT: 100 ml CAUTION: INFLAMMABLE", 1)]

    assert extractor.extract(lines, "img_test_123") == []


def test_commodity_name_extractor_rejects_safety_instruction_fragments():
    """Safety directions from a back panel cannot become a second product title."""
    extractor = CommodityNameExtractor()
    lines = [
        create_ocr_line("KEEP AWAY FROM HEAT OR FLAME. KEEP OUT OF REACH OF CHILDREN.", 1),
        create_ocr_line("HARMFUL IF TAKEN INTERNALLY.", 2),
    ]

    assert extractor.extract(lines, "img_test_123") == []


def test_commodity_name_extractor_does_not_use_total_net_weight_as_title():
    """A net-quantity declaration is not a fallback commodity name."""
    extractor = CommodityNameExtractor()
    lines = [create_ocr_line("TOTAL NET WT. 240 g", 1)]

    assert extractor.extract(lines, "img_test_123") == []


def test_declaration_extraction_service_orchestration():
    """Verify end-to-end multi-field extraction across a realistic label (EXT-01)."""
    service = DeclarationExtractionService()
    lines = [
        create_ocr_line("Name of Commodity: Premium Roasted Almonds", 1),
        create_ocr_line("Net Weight: 250 g", 2),
        create_ocr_line("M.R.P. Rs. 350.00 (Incl. of all taxes)", 3),
        create_ocr_line("Mfg Date: 07/2026", 4),
        create_ocr_line("Manufactured by: NutriPack India Pvt Ltd, Delhi 110001", 5),
        create_ocr_line("Customer Care: care@nutripack.com", 6),
        create_ocr_line("Country of Origin: India", 7),
    ]

    declarations = service.extract_declarations(lines, "img_pkg_001")
    extracted_types = {d.field_type for d in declarations}

    expected_types = {
        "mrp",
        "net_quantity",
        "manufacturer_address",
        "mfg_date",
        "consumer_care",
        "country_of_origin",
        "commodity_name",
    }
    assert expected_types.issubset(extracted_types)


def test_commodity_categories_registry():
    """Verify commodity category registry (EXT-09)."""
    assert len(COMMODITY_CATEGORIES) >= 7

    pan_masala = get_category_by_id("pan_masala")
    assert pan_masala is not None
    assert "pan_masala_rsp_rule" in pan_masala.specific_rule_flags

    food = get_category_by_id("food")
    assert food is not None
    assert "food_net_weight_tolerance" in food.specific_rule_flags
