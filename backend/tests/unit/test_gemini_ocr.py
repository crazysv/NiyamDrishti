import json
from unittest.mock import MagicMock

import numpy as np
import pytest

from app.services.extraction.service import DeclarationExtractionService
from app.services.ocr import (
    BoundingBox,
    OCRLine,
    OCRResult,
    OCRService,
)
from app.services.ocr.gemini_engine import (
    GeminiOCREngine,
    convert_gemini_box_to_pixels,
)
from app.services.preprocessing import PipelineConfig, PreprocessingPipeline


@pytest.fixture
def dummy_image():
    """800x600 test image canvas."""
    return np.full((600, 800, 3), 200, dtype=np.uint8)


@pytest.fixture
def mock_gemini_response_payload():
    """Valid structured Gemini response dictionary."""
    return {
        "regions": [
            {
                "text": "MRP ₹149.00 (Incl. of all taxes)",
                "box_2d": [100, 200, 150, 600],  # ymin, xmin, ymax, xmax
                "confidence": 0.96,
            },
            {
                "text": "Net Quantity: 500 g",
                "box_2d": [200, 200, 240, 450],
                "confidence": 0.94,
            },
            {
                "text": "Mfg Date: 08/2026",
                "box_2d": [300, 200, 340, 400],
                "confidence": 0.91,
            },
        ]
    }


def test_convert_gemini_box_to_pixels_standard():
    """Verify conversion from 0-1000 normalized coordinates to pixel coordinates."""
    # 800 width, 600 height
    # box_2d: [ymin, xmin, ymax, xmax] = [100, 200, 150, 400]
    bbox = convert_gemini_box_to_pixels([100, 200, 150, 400], image_width=800, image_height=600)

    assert bbox is not None
    assert bbox.x == 160.0  # (200/1000) * 800
    assert bbox.y == 60.0  # (100/1000) * 600
    assert bbox.w == 160.0  # ((400-200)/1000) * 800
    assert bbox.h == 30.0  # ((150-100)/1000) * 600
    assert len(bbox.polygon) == 4
    assert bbox.polygon[0] == [160.0, 60.0]


def test_convert_gemini_box_to_pixels_inverted_and_clipped():
    """Verify coordinate converter handles inverted coords and out-of-bound coords safely."""
    # xmin > xmax (600 > 100), ymin > ymax (900 > 200)
    bbox = convert_gemini_box_to_pixels([900, 600, 200, 100], image_width=1000, image_height=500)

    assert bbox is not None
    assert bbox.x == 100.0
    assert bbox.y == 100.0  # (200/1000) * 500
    assert bbox.w == 500.0
    assert bbox.h == 350.0  # ((900-200)/1000) * 500

    # Over 1000 should clip to image dimensions
    bbox_clipped = convert_gemini_box_to_pixels([-50, -100, 1200, 1500], image_width=800, image_height=600)
    assert bbox_clipped is not None
    assert bbox_clipped.x == 0.0
    assert bbox_clipped.y == 0.0
    assert bbox_clipped.w <= 800.0
    assert bbox_clipped.h <= 600.0


def test_convert_gemini_box_to_pixels_invalid_inputs():
    """Verify malformed coordinates, NaNs, and non-lists return None without crashing."""
    assert convert_gemini_box_to_pixels([], 800, 600) is None
    assert convert_gemini_box_to_pixels([100, 200], 800, 600) is None
    assert convert_gemini_box_to_pixels([float("nan"), 100, 200, 300], 800, 600) is None
    assert convert_gemini_box_to_pixels([100, float("inf"), 200, 300], 800, 600) is None


def test_gemini_ocr_engine_availability():
    """Verify availability status based on credentials or injected client."""
    engine_no_key = GeminiOCREngine(api_key="")
    assert engine_no_key.is_available is False

    engine_with_key = GeminiOCREngine(api_key="mock-api-key-12345")
    assert engine_with_key.is_available is True

    mock_client = MagicMock()
    engine_with_client = GeminiOCREngine(client=mock_client)
    assert engine_with_client.is_available is True


def test_server_error_class_is_treated_as_a_transient_gemini_failure():
    """google-genai may expose a 5xx only through its ServerError class name."""

    class ServerError(Exception):
        pass

    assert GeminiOCREngine._is_transient_or_model_error(ServerError("temporary upstream failure"))


def test_gemini_client_applies_configured_http_timeout(monkeypatch):
    """The documented timeout must be applied to the SDK client in milliseconds."""
    from google import genai
    from google.genai import types

    client_factory = MagicMock(return_value=MagicMock())
    http_options_factory = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(genai, "Client", client_factory)
    monkeypatch.setattr(types, "HttpOptions", http_options_factory)

    engine = GeminiOCREngine(api_key="test-key", timeout_seconds=12.5)
    engine._get_client_for_key("test-key")

    http_options_factory.assert_called_once_with(timeout=12500)
    client_factory.assert_called_once()
    assert client_factory.call_args.kwargs["api_key"] == "test-key"


def test_gemini_ocr_engine_extraction_success(dummy_image, mock_gemini_response_payload):
    """Test successful Gemini OCR extraction and conversion to standard OCRResult contract."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps(mock_gemini_response_payload)
    mock_client.models.generate_content.return_value = mock_response

    engine = GeminiOCREngine(client=mock_client, model="gemini-2.5-flash")
    result = engine.extract(dummy_image, source_image_id="img_gemini_01")

    assert result.source_image_id == "img_gemini_01"
    assert result.engine_used == "gemini"
    assert len(result.lines) == 3
    assert result.average_confidence > 0.90
    assert "MRP ₹149.00" in result.full_text

    line0 = result.lines[0]
    assert line0.text == "MRP ₹149.00 (Incl. of all taxes)"
    assert line0.confidence == 0.96
    assert line0.source_image_id == "img_gemini_01"
    assert line0.engine == "gemini"
    assert line0.bounding_box.x > 0
    assert line0.bounding_box.y > 0


def test_gemini_ocr_engine_missing_key_raises(dummy_image):
    """Calling extract on unconfigured engine raises a descriptive RuntimeError."""
    engine = GeminiOCREngine(api_key="")
    with pytest.raises(RuntimeError, match="no API key is configured"):
        engine.extract(dummy_image, source_image_id="img_err")


def test_gemini_ocr_engine_malformed_json_handling(dummy_image):
    """Malformed JSON response from API raises ValueError and is handled defensively."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "NOT JSON TEXT AT ALL"
    mock_client.models.generate_content.return_value = mock_response

    engine = GeminiOCREngine(client=mock_client)
    with pytest.raises(ValueError, match="Malformed Gemini OCR output"):
        engine.extract(dummy_image, source_image_id="img_bad_json")


def test_ocr_service_gemini_explicit_selection(dummy_image, mock_gemini_response_payload):
    """Verify OCRService selects Gemini when requested explicitly and formats correctly."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps(mock_gemini_response_payload)
    mock_client.models.generate_content.return_value = mock_response

    gemini_engine = GeminiOCREngine(client=mock_client)
    mock_paddle = MagicMock()
    mock_tesseract = MagicMock()

    service = OCRService(
        primary_engine=mock_paddle,
        fallback_engine=mock_tesseract,
        gemini_engine=gemini_engine,
    )

    result = service.process_image(
        dummy_image,
        source_image_id="img_explicit_gemini",
        provider="gemini",
    )

    assert result.engine_used == "gemini"
    assert len(result.lines) == 3
    # Local engines should not have been called
    mock_paddle.extract.assert_not_called()
    mock_tesseract.extract.assert_not_called()


def test_ocr_service_gemini_failure_is_strict_and_never_loads_local_engine(dummy_image):
    """Explicit Gemini mode must surface failure instead of risking a Render OOM fallback."""
    mock_gemini = MagicMock()
    mock_gemini.name = "gemini"
    mock_gemini.is_available = True
    mock_gemini.extract.side_effect = TimeoutError("Gemini API connection timed out")

    mock_paddle = MagicMock()
    paddle_line = OCRLine(
        text="MRP Rs. 200",
        confidence=0.92,
        bounding_box=BoundingBox(x=50, y=50, w=150, h=30),
        source_image_id="img_fallback_gemini",
        engine="paddleocr",
    )
    mock_paddle.extract.return_value = OCRResult(
        source_image_id="img_fallback_gemini",
        lines=[paddle_line],
        full_text="MRP Rs. 200",
        average_confidence=0.92,
        engine_used="paddleocr",
    )

    service = OCRService(
        primary_engine=mock_paddle,
        gemini_engine=mock_gemini,
    )

    with pytest.raises(RuntimeError, match="Gemini OCR failed"):
        service.process_image(
            dummy_image,
            source_image_id="img_fallback_gemini",
            provider="gemini",
        )

    mock_paddle.extract.assert_not_called()


def test_ocr_service_gemini_coordinate_mapping_to_original(mock_gemini_response_payload):
    """Verify Gemini coordinates are mapped back through preprocessing to original raw image space."""
    large_img = np.full((1600, 2400, 3), 200, dtype=np.uint8)

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps(mock_gemini_response_payload)
    mock_client.models.generate_content.return_value = mock_response

    gemini_engine = GeminiOCREngine(client=mock_client)
    pipeline = PreprocessingPipeline(PipelineConfig(max_dimension=1200))

    service = OCRService(
        gemini_engine=gemini_engine,
        preprocessing_pipeline=pipeline,
    )

    result = service.process_image(
        large_img,
        source_image_id="img_mapped_gemini",
        provider="gemini",
    )

    assert len(result.lines) == 3
    # Original width was 2400, downscaled to 1200 (scale 0.5)
    # Preprocessed image: width=1200, height=800
    # Region 0: box_2d = [100, 200, 150, 600]
    # In 1200x800 preprocessed space:
    # x = (200/1000) * 1200 = 240.0; y = (100/1000) * 800 = 80.0
    # Scaled back to 2400x1600 original space (divided by 0.5 = multiplied by 2):
    # x = 480.0; y = 160.0
    line0 = result.lines[0]
    assert line0.bounding_box.x == 480.0
    assert line0.bounding_box.y == 160.0
    assert line0.source_image_id == "img_mapped_gemini"


def test_gemini_ocr_result_feeds_declaration_extraction(dummy_image, mock_gemini_response_payload):
    """Verify DeclarationExtractionService extracts mandatory declarations directly from Gemini OCRResult."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps(mock_gemini_response_payload)
    mock_client.models.generate_content.return_value = mock_response

    engine = GeminiOCREngine(client=mock_client)
    ocr_res = engine.extract(dummy_image, source_image_id="img_extract_test")

    extraction_service = DeclarationExtractionService()
    declarations = extraction_service.extract_from_ocr_result(ocr_res)

    extracted_types = {d.field_type for d in declarations}
    assert "mrp" in extracted_types
    assert "net_quantity" in extracted_types
    assert "mfg_date" in extracted_types

    mrp_decl = next(d for d in declarations if d.field_type == "mrp")
    assert "149.0" in mrp_decl.parsed_value
    assert mrp_decl.source_image_id == "img_extract_test"
    assert mrp_decl.bounding_box is not None


def test_gemini_key_pool_parsing_and_masking():
    """Verify key pool deduplication, trimming, and masking logic."""
    from app.core.config import Settings

    custom_settings = Settings(
        GEMINI_API_KEYS="key_one, key_two , key_three",
        GEMINI_API_KEY="key_one",  # Duplicate should be ignored
        GEMINI_API_KEY_2="key_four",
        GEMINI_API_KEY_3="",
    )
    keys = custom_settings.get_gemini_api_keys()
    assert keys == ["key_one", "key_two", "key_three", "key_four"]

    # Masking test
    assert GeminiOCREngine._mask_key("AIzaSyBJJqOTFNfVnVsRMl9JCr7kxJD8TX1QAXE") == "AIzaSy...1QAXE"
    assert GeminiOCREngine._mask_key("short") == "****"


def test_gemini_key_rotation_on_429_exhaustion(dummy_image, mock_gemini_response_payload):
    """
    Verify 3-key rotation pool automatically detects 429 quota exhaustion on key 1
    and rotates to key 2 seamlessly without crashing.
    """
    engine = GeminiOCREngine(api_keys=["key_alpha", "key_beta", "key_gamma"])
    assert len(engine.api_keys) == 3

    # Mock clients for each key
    client_alpha = MagicMock()
    client_alpha.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED: rate limit exceeded")

    client_beta = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(mock_gemini_response_payload)
    client_beta.models.generate_content.return_value = mock_resp

    engine._clients["key_alpha"] = client_alpha
    engine._clients["key_beta"] = client_beta

    ocr_res = engine.extract(dummy_image, source_image_id="img_rotation_test")

    assert len(ocr_res.lines) == 3
    assert ocr_res.lines[0].text == "MRP ₹149.00 (Incl. of all taxes)"
    # Verify key 1 was called and failed
    client_alpha.models.generate_content.assert_called_once()
    # Verify key 2 was called and succeeded
    client_beta.models.generate_content.assert_called_once()
    # Verify active key advanced to key_beta
    assert engine.api_key == "key_beta"


def test_gemini_key_rotation_all_keys_exhausted_raises(dummy_image):
    """Verify that when all keys in rotation pool are exhausted, descriptive RuntimeError is raised."""
    engine = GeminiOCREngine(api_keys=["key_1", "key_2", "key_3"])

    for k in ["key_1", "key_2", "key_3"]:
        c = MagicMock()
        c.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED: depleted credits")
        engine._clients[k] = c

    with pytest.raises(RuntimeError, match="rotation pool exhausted"):
        engine.extract(dummy_image, source_image_id="img_all_fail")


def test_ocr_service_all_gemini_keys_exhausted_is_strict(dummy_image):
    """A demo Gemini outage must be reported rather than silently loading PaddleOCR."""
    gemini_engine = GeminiOCREngine(api_keys=["k1", "k2", "k3"])
    for k in ["k1", "k2", "k3"]:
        c = MagicMock()
        c.models.generate_content.side_effect = Exception("429 quota exceeded")
        gemini_engine._clients[k] = c

    mock_paddle = MagicMock()
    fallback_line = OCRLine(
        text="MRP Rs. 50.00",
        confidence=0.91,
        bounding_box=BoundingBox(x=10, y=10, w=100, h=25),
        source_image_id="img_pool_fallback",
        engine="paddleocr",
    )
    mock_paddle.extract.return_value = OCRResult(
        source_image_id="img_pool_fallback",
        lines=[fallback_line],
        full_text="MRP Rs. 50.00",
        average_confidence=0.91,
        engine_used="paddleocr",
    )

    service = OCRService(
        primary_engine=mock_paddle,
        gemini_engine=gemini_engine,
    )

    with pytest.raises(RuntimeError, match="Gemini OCR failed"):
        service.process_image(
            dummy_image,
            source_image_id="img_pool_fallback",
            provider="gemini",
        )

    mock_paddle.extract.assert_not_called()


def test_gemini_key_rotation_on_403_permission_denied(dummy_image, mock_gemini_response_payload):
    """Verify immediate rotation when a key returns 403 PERMISSION_DENIED or leaked status."""
    keys = ["AIzaSyDeadKey1", "AIzaSyHealthyKey2"]
    gemini_engine = GeminiOCREngine(api_keys=keys, max_retries=2)

    client_dead = MagicMock()
    client_dead.models.generate_content.side_effect = Exception(
        "403 PERMISSION_DENIED. {'error': {'message': 'Your API key was reported as leaked.'}}"
    )
    client_healthy = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(mock_gemini_response_payload)
    client_healthy.models.generate_content.return_value = mock_resp

    gemini_engine._clients[keys[0]] = client_dead
    gemini_engine._clients[keys[1]] = client_healthy

    result = gemini_engine.extract(dummy_image, source_image_id="img_perm_denied_test")
    assert len(result.lines) == 3
    # First key should only be called once because 403 triggers immediate break/rotation
    assert client_dead.models.generate_content.call_count == 1
    assert client_healthy.models.generate_content.call_count == 1


def test_gemini_model_fallback_on_model_quota(dummy_image, mock_gemini_response_payload):
    """Verify automatic fallback to the available Flash-Lite model when primary quota is exhausted."""
    key = "AIzaSyGoodKey"
    gemini_engine = GeminiOCREngine(api_keys=[key], model="gemini-3.7-flash", max_retries=1)

    client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(mock_gemini_response_payload)

    def side_effect(model, contents, config):
        if model == "gemini-3.7-flash":
            raise Exception(
                "429 RESOURCE_EXHAUSTED. Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests"
            )
        return mock_resp

    client.models.generate_content.side_effect = side_effect
    gemini_engine._clients[key] = client

    result = gemini_engine.extract(dummy_image, source_image_id="img_model_fallback_test")
    assert len(result.lines) == 3
    # Both gemini-3.7-flash and gemini-3.5-flash-lite should have been called on the same client
    calls = client.models.generate_content.call_args_list
    assert len(calls) == 2
    assert calls[0].kwargs["model"] == "gemini-3.7-flash"
    assert calls[1].kwargs["model"] == "gemini-3.5-flash-lite"


def test_gemini_model_fallback_on_503_or_404(dummy_image, mock_gemini_response_payload):
    """Verify automatic fallback to Flash-Lite when a model returns 503 UNAVAILABLE or 404 NOT_FOUND."""
    key = "AIzaSyGoodKey"
    gemini_engine = GeminiOCREngine(api_keys=[key], model="gemini-3.6-flash", max_retries=1)

    client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(mock_gemini_response_payload)

    def side_effect(model, contents, config):
        if model == "gemini-3.6-flash":
            raise Exception("503 UNAVAILABLE: The model is overloaded. Please try again later.")
        return mock_resp

    client.models.generate_content.side_effect = side_effect
    gemini_engine._clients[key] = client

    result = gemini_engine.extract(dummy_image, source_image_id="img_503_fallback_test")
    assert len(result.lines) == 3
    calls = client.models.generate_content.call_args_list
    assert len(calls) == 2
    assert calls[0].kwargs["model"] == "gemini-3.6-flash"
    assert calls[1].kwargs["model"] == "gemini-3.5-flash-lite"
