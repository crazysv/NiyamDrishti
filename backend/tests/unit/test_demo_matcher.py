import pytest
from app.services.extraction.demo_matcher import GoldenDemoMatcher
from app.services.ocr.schemas import BoundingBox, OCRLine

def test_golden_demo_matcher_barcode_lookup():
    matcher = GoldenDemoMatcher()
    
    # 1. Dabur Gulabari
    profile1 = matcher.match_product([], barcode="8901207051425")
    assert profile1 is not None
    assert profile1["sku_id"] == "dabur_gulabari_150g"

    # 2. Britannia Tiger Krunch
    profile2 = matcher.match_product([], barcode="8901063155329")
    assert profile2 is not None
    assert profile2["sku_id"] == "britannia_tiger_krunch_400g"

    # 3. Colgate Visible White
    profile3 = matcher.match_product([], barcode="8901314868114")
    assert profile3 is not None
    assert profile3["sku_id"] == "colgate_visible_white_240g"

def test_golden_demo_matcher_text_anchor_lookup():
    matcher = GoldenDemoMatcher()
    
    lines = [
        OCRLine(text="Colgate Anticavity", confidence=0.98, bounding_box=BoundingBox(x=10, y=20, w=100, h=30), source_image_id="img1", engine="test"),
        OCRLine(text="Visible White Toothpaste", confidence=0.99, bounding_box=BoundingBox(x=10, y=60, w=150, h=30), source_image_id="img1", engine="test"),
    ]
    profile = matcher.match_product(lines, barcode=None)
    assert profile is not None
    assert profile["sku_id"] == "colgate_visible_white_240g"

def test_golden_demo_matcher_dynamic_bounding_box_extraction():
    matcher = GoldenDemoMatcher()
    profile = matcher.profiles["dabur_gulabari_150g"]

    # Mock live OCR lines with custom arbitrary live camera coordinates
    lines = [
        OCRLine(text="Dabur Gulabari Radiant Rose Glow", confidence=0.97, bounding_box=BoundingBox(x=123.4, y=456.7, w=300.0, h=40.0), source_image_id="live_capture_1", engine="paddleocr"),
        OCRLine(text="Net Quantity (when packed) : 150 g", confidence=0.99, bounding_box=BoundingBox(x=55.0, y=200.0, w=180.0, h=35.0), source_image_id="live_capture_1", engine="paddleocr"),
    ]

    decls = matcher.extract_golden_declarations(profile, lines, source_image_id="live_capture_1")
    
    # Declarations found for commodity_name and net_quantity
    decl_map = {d.field_type: d for d in decls}
    assert "commodity_name" in decl_map
    assert "net_quantity" in decl_map
    
    # Dynamic bounding box must match the live OCR lines exactly!
    assert decl_map["commodity_name"].bounding_box["x"] == 123.4
    assert decl_map["commodity_name"].bounding_box["y"] == 456.7
    assert decl_map["net_quantity"].bounding_box["x"] == 55.0
    assert decl_map["net_quantity"].bounding_box["y"] == 200.0
