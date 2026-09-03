from unittest.mock import MagicMock

import numpy as np
import pytest

from app.services.ocr import (
    BoundingBox,
    OCRLine,
    OCRResult,
    OCRService,
    PaddleOCREngine,
    TesseractEngine,
)
from app.services.preprocessing import PipelineConfig, PreprocessingPipeline


@pytest.fixture
def mock_paddle_instance():
    """Mocks PaddleOCR library instance returning standard output format."""
    mock_ocr = MagicMock()
    # Format: [[[ [x1, y1], [x2, y2], [x3, y3], [x4, y4] ], (text, confidence)]]
    mock_ocr.ocr.return_value = [
        [
            [
                [[50.0, 100.0], [300.0, 100.0], [300.0, 140.0], [50.0, 140.0]],
                ("MRP Rs. 250.00 (Incl. of all taxes)", 0.965),
            ],
            [
                [[50.0, 150.0], [200.0, 150.0], [200.0, 180.0], [50.0, 180.0]],
                ("Net Quantity: 500 g", 0.920),
            ],
            [
                [[50.0, 200.0], [450.0, 200.0], [450.0, 230.0], [50.0, 230.0]],
                ("Mfg Date: 08/2026", 0.885),
            ],
        ]
    ]
    return mock_ocr


@pytest.fixture
def dummy_image():
    """Creates a blank 800x600 test canvas."""
    return np.full((600, 800, 3), 220, dtype=np.uint8)


def test_paddle_ocr_engine_extraction(mock_paddle_instance, dummy_image):
    """Test PP-OCR parsing of polygon, bounding box, text, and confidence."""
    engine = PaddleOCREngine(ocr_instance=mock_paddle_instance)
    result = engine.extract(dummy_image, source_image_id="img_test_01")

    assert result.source_image_id == "img_test_01"
    assert len(result.lines) == 3
    assert result.engine_used == "paddleocr"
    assert result.average_confidence > 0.90

    line1 = result.lines[0]
    assert line1.text == "MRP Rs. 250.00 (Incl. of all taxes)"
    assert line1.confidence == 0.965
    assert line1.bounding_box.x == 50.0
    assert line1.bounding_box.y == 100.0
    assert line1.bounding_box.w == 250.0
    assert line1.bounding_box.h == 40.0
    assert len(line1.bounding_box.polygon) == 4
    assert line1.source_image_id == "img_test_01"


def test_tesseract_engine_extraction(monkeypatch, dummy_image):
    """Test Tesseract line aggregation and token grouping."""
    mock_pytesseract = MagicMock()
    mock_data = {
        "text": ["", "MRP", "Rs.", "150.00", "", "Net", "Qty", "250g"],
        "conf": [-1, 95, 90, 88, -1, 92, 94, 91],
        "left": [0, 50, 110, 160, 0, 50, 100, 150],
        "top": [0, 80, 80, 80, 0, 120, 120, 120],
        "width": [0, 50, 40, 70, 0, 40, 40, 50],
        "height": [0, 25, 25, 25, 0, 25, 25, 25],
        "block_num": [1, 1, 1, 1, 1, 1, 1, 1],
        "par_num": [1, 1, 1, 1, 1, 1, 1, 1],
        "line_num": [1, 1, 1, 1, 2, 2, 2, 2],
    }
    mock_pytesseract.image_to_data.return_value = mock_data
    mock_pytesseract.Output.DICT = "dict"

    import sys

    monkeypatch.setitem(sys.modules, "pytesseract", mock_pytesseract)

    engine = TesseractEngine()
    result = engine.extract(dummy_image, source_image_id="img_tess_01")

    assert result.source_image_id == "img_tess_01"
    assert len(result.lines) == 2
    assert result.engine_used == "tesseract"

    # Line 1: MRP Rs. 150.00
    assert result.lines[0].text == "MRP Rs. 150.00"
    assert result.lines[0].bounding_box.x == 50.0
    assert result.lines[0].bounding_box.y == 80.0
    assert result.lines[0].bounding_box.w == 180.0  # 160 + 70 - 50 = 180
    assert result.lines[0].bounding_box.h == 25.0

    # Line 2: Net Qty 250g
    assert result.lines[1].text == "Net Qty 250g"


def test_ocr_service_primary_path(mock_paddle_instance, dummy_image):
    """Verify primary engine (PaddleOCR) is used when confidence exceeds threshold."""
    paddle_engine = PaddleOCREngine(ocr_instance=mock_paddle_instance)
    mock_fallback = MagicMock()

    service = OCRService(
        primary_engine=paddle_engine,
        fallback_engine=mock_fallback,
        min_confidence_threshold=0.60,
    )

    result = service.process_image(dummy_image, source_image_id="img_primary_01")

    assert result.engine_used == "paddleocr"
    assert result.fallback_triggered is False
    assert len(result.lines) == 3
    # Fallback should not be called
    mock_fallback.extract.assert_not_called()


def test_ocr_service_fallback_on_low_confidence(dummy_image):
    """Verify fallback engine (Tesseract) is triggered when primary confidence is low."""
    # Primary engine returns low confidence
    mock_primary = MagicMock()
    low_conf_line = OCRLine(
        text="unclear text",
        confidence=0.35,
        bounding_box=BoundingBox(x=10, y=10, w=50, h=20),
        source_image_id="img_fallback_01",
        engine="paddleocr",
    )
    mock_primary.extract.return_value = OCRResult(
        source_image_id="img_fallback_01",
        lines=[low_conf_line],
        full_text="unclear text",
        average_confidence=0.35,
        engine_used="paddleocr",
    )

    # Fallback engine returns good result
    mock_fallback = MagicMock()
    good_line = OCRLine(
        text="MRP Rs. 100",
        confidence=0.88,
        bounding_box=BoundingBox(x=10, y=10, w=100, h=20),
        source_image_id="img_fallback_01",
        engine="tesseract",
    )
    mock_fallback.extract.return_value = OCRResult(
        source_image_id="img_fallback_01",
        lines=[good_line],
        full_text="MRP Rs. 100",
        average_confidence=0.88,
        engine_used="tesseract",
    )

    service = OCRService(
        primary_engine=mock_primary,
        fallback_engine=mock_fallback,
        min_confidence_threshold=0.60,
    )

    result = service.process_image(dummy_image, source_image_id="img_fallback_01")

    assert result.fallback_triggered is True
    assert result.engine_used == "tesseract"
    assert len(result.lines) == 1
    assert result.lines[0].text == "MRP Rs. 100"
    mock_fallback.extract.assert_called_once()


def test_ocr_service_preserves_all_metadata_and_maps_coordinates(mock_paddle_instance):
    """
    Test OCR-03:
    Guarantees every line retains text + confidence + bounding box + source-image ref,
    and ensures bounding boxes are mapped back to original image space.
    """
    # Create large image that gets downscaled by 0.5x during preprocessing
    large_img = np.full((1600, 2400, 3), 200, dtype=np.uint8)

    pipeline = PreprocessingPipeline(PipelineConfig(max_dimension=1200))
    paddle_engine = PaddleOCREngine(ocr_instance=mock_paddle_instance)

    service = OCRService(
        primary_engine=paddle_engine,
        preprocessing_pipeline=pipeline,
    )

    result = service.process_image(large_img, source_image_id="img_large_01")

    assert len(result.lines) == 3
    # Check that each line retains all required fields
    for line in result.lines:
        assert line.text != ""
        assert 0.0 <= line.confidence <= 1.0
        assert line.bounding_box.w > 0
        assert line.bounding_box.h > 0
        assert line.source_image_id == "img_large_01"
        assert line.engine == "paddleocr"

    # Verify coordinate mapping: original width was 2400, downscaled to 1200 (0.5x)
    # The mock paddle box had x=50.0, y=100.0 on the preprocessed image.
    # Scaled back to original image: x=100.0, y=200.0
    line1 = result.lines[0]
    assert line1.bounding_box.x == 100.0
    assert line1.bounding_box.y == 200.0
    assert line1.bounding_box.w == 500.0
    assert line1.bounding_box.h == 80.0
