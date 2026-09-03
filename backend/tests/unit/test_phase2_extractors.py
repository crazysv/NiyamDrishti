import uuid

from app.services.extraction.dimensions_count_extractor import DimensionsAndCountExtractor
from app.services.extraction.importer_packer_extractor import ImporterPackerExtractor
from app.services.extraction.rsp_extractor import RSPExtractor
from app.services.extraction.service import DeclarationExtractionService
from app.services.ocr.schemas import BoundingBox, OCRLine, OCRResult


def make_line(text: str, confidence: float = 0.95) -> OCRLine:
    return OCRLine(
        text=text,
        confidence=confidence,
        bounding_box=BoundingBox(x=10, y=20, w=100, h=30),
        source_image_id=str(uuid.uuid4()),
    )


def test_dimensions_extraction():
    extractor = DimensionsAndCountExtractor()
    img_id = str(uuid.uuid4())

    lines = [
        make_line("Product Dimensions: 25.5 cm x 18.0 cm x 5.2 cm"),
        make_line("Other text"),
    ]
    results = extractor.extract(lines, img_id)
    assert len(results) == 1
    decl = results[0]
    assert decl.field_type == "dimensions"
    assert "25.5 x 18.0 x 5.2 cm" in decl.parsed_value
    assert decl.metadata["unit"] == "cm"
    assert decl.metadata["dimensions"] == [25.5, 18.0, 5.2]


def test_unit_and_piece_count_extraction():
    extractor = DimensionsAndCountExtractor()
    img_id = str(uuid.uuid4())

    lines = [
        make_line("Net Quantity: Pack of 10 N"),
        make_line("Quantity: 50 Pieces"),
    ]
    results = extractor.extract(lines, img_id)
    assert len(results) >= 1
    types = [r.field_type for r in results]
    assert "item_count" in types
    counts = [r.metadata.get("count") for r in results if r.field_type == "item_count"]
    assert 10 in counts or 50 in counts


def test_importer_packer_marketer_extraction():
    extractor = ImporterPackerExtractor()
    img_id = str(uuid.uuid4())

    lines = [
        make_line("Imported and Marketed by: Global Trade Partners Pvt Ltd, Nariman Point, Mumbai - 400021"),
        make_line("Packed by: Standard Packaging Hub, Shed 4, Bhiwandi, Maharashtra"),
        make_line("Marketed by: Brand Retail Ltd, Nehru Place, New Delhi - 110019"),
    ]
    results = extractor.extract(lines, img_id)
    assert len(results) == 3
    field_types = {r.field_type for r in results}
    assert "importer_address" in field_types
    assert "packer_address" in field_types
    assert "marketer_address" in field_types

    importer = next(r for r in results if r.field_type == "importer_address")
    assert "Global Trade Partners" in importer.parsed_value


def test_rsp_2026_amendment_extraction():
    extractor = RSPExtractor()
    img_id = str(uuid.uuid4())

    lines = [
        make_line("RSP Rs. 15.00 (INCL. OF ALL TAXES)"),
        make_line("Retail Sale Price: ₹ 25.50"),
    ]
    results = extractor.extract(lines, img_id)
    assert len(results) == 2
    for r in results:
        assert r.field_type == "rsp"
        assert "LM(PC) Second Amendment" in r.metadata["amendment"]

    assert results[0].metadata["price"] == 15.00
    assert results[0].metadata["inclusive_of_taxes"] is True
    assert results[1].metadata["price"] == 25.50


def test_full_service_extracts_all_extended_fields():
    service = DeclarationExtractionService()
    img_id = str(uuid.uuid4())

    lines = [
        make_line("HIMALAYAN BASMATI RICE"),
        make_line("Net Qty: 5 kg"),
        make_line("MRP Rs. 320.00 (incl. of all taxes)"),
        make_line("Size: 30 cm x 20 cm x 10 cm"),
        make_line("Pack of 2 N"),
        make_line("Imported by: Asian Imports Ltd, Port Area, Kochi"),
        make_line("RSP Rs. 50.00"),
    ]
    res = OCRResult(
        source_image_id=img_id,
        lines=lines,
        full_text="\n".join(line_item.text for line_item in lines),
    )
    declarations = service.extract_from_ocr_result(res)
    field_types = {d.field_type for d in declarations}

    assert "mrp" in field_types
    assert "net_quantity" in field_types
    assert "dimensions" in field_types
    assert "item_count" in field_types
    assert "importer_address" in field_types
    assert "rsp" in field_types
