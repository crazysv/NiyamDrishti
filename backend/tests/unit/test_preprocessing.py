import base64

import cv2
import numpy as np
import pytest
from PIL import Image

from app.services.preprocessing import (
    PipelineConfig,
    PreprocessingPipeline,
    map_bbox_to_original,
    map_point_to_original,
)


@pytest.fixture
def sample_test_image() -> np.ndarray:
    """Generates a synthetic 800x600 test image with text and shapes."""
    img = np.full((600, 800, 3), 200, dtype=np.uint8)
    # Add simulated dark text
    cv2.putText(
        img,
        "MRP Rs. 150.00",
        (50, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (20, 20, 20),
        2,
    )
    # Add a colored rectangle
    cv2.rectangle(img, (50, 150), (400, 300), (0, 120, 0), -1)
    return img


@pytest.fixture
def sample_jpeg_bytes(sample_test_image: np.ndarray) -> bytes:
    """Encodes sample image as JPEG bytes."""
    _, buf = cv2.imencode(".jpg", sample_test_image)
    return buf.tobytes()


@pytest.fixture
def sample_data_url(sample_jpeg_bytes: bytes) -> str:
    """Creates a base64 data URL for testing."""
    b64 = base64.b64encode(sample_jpeg_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def test_pipeline_initialization():
    """Verify default and custom configuration initialization."""
    default_pipe = PreprocessingPipeline()
    assert default_pipe.config.max_dimension == 2048
    assert default_pipe.config.enable_contrast is True
    assert default_pipe.config.enable_denoise is True
    assert default_pipe.config.enable_deskew is True
    assert default_pipe.config.enable_perspective_correction is True
    assert default_pipe.config.enable_glare_suppression is True
    assert default_pipe.config.enable_text_enhancement is True

    custom_cfg = PipelineConfig(max_dimension=1024, enable_denoise=False)
    custom_pipe = PreprocessingPipeline(custom_cfg)
    assert custom_pipe.config.max_dimension == 1024
    assert custom_pipe.config.enable_denoise is False


def test_pipeline_input_types(
    sample_test_image: np.ndarray,
    sample_jpeg_bytes: bytes,
    sample_data_url: str,
):
    """Test loading and processing across all supported input formats."""
    pipe = PreprocessingPipeline()

    # 1. NumPy Array
    res1 = pipe.process(sample_test_image)
    assert res1.original_shape == (600, 800)
    assert isinstance(res1.image, np.ndarray)

    # 2. Raw Bytes
    res2 = pipe.process(sample_jpeg_bytes)
    assert res2.original_shape == (600, 800)

    # 3. Base64 Data URL
    res3 = pipe.process(sample_data_url)
    assert res3.original_shape == (600, 800)

    # 4. PIL Image
    pil_img = Image.fromarray(cv2.cvtColor(sample_test_image, cv2.COLOR_BGR2RGB))
    res4 = pipe.process(pil_img)
    assert res4.original_shape == (600, 800)


def test_resize_and_aspect_ratio_preservation():
    """Verify downsampling of large images maintains exact aspect ratio."""
    large_img = np.zeros((3000, 4000, 3), dtype=np.uint8)
    pipe = PreprocessingPipeline(
        PipelineConfig(
            max_dimension=2000,
            enable_glare_suppression=False,
            enable_text_enhancement=False,
        )
    )

    result = pipe.process(large_img)
    orig_h, orig_w = result.original_shape
    proc_h, proc_w = result.processed_shape

    assert orig_w == 4000 and orig_h == 3000
    assert proc_w == 2000
    assert proc_h == 1500
    assert pytest.approx(result.scale_factor, 0.001) == 0.5
    assert "resize_scale_0.5000" in result.applied_steps


def test_contrast_enhancement_improves_dynamic_range():
    """Verify CLAHE expands dynamic range on a low-contrast image."""
    low_contrast = np.random.randint(100, 130, (400, 400, 3), dtype=np.uint8)
    pipe = PreprocessingPipeline(
        PipelineConfig(
            enable_denoise=False,
            enable_contrast=True,
            enable_deskew=False,
            enable_perspective_correction=False,
            enable_glare_suppression=False,
            enable_text_enhancement=False,
        )
    )

    result = pipe.process(low_contrast)
    orig_std = np.std(low_contrast)
    proc_std = np.std(result.image)

    assert proc_std > orig_std
    assert "clahe_contrast_enhancement" in result.applied_steps


def test_bilateral_denoising():
    """Verify denoising reduces noise in uniform areas."""
    clean = np.full((300, 300, 3), 128, dtype=np.uint8)
    noise = np.random.normal(0, 15, clean.shape).astype(np.int16)
    noisy = np.clip(clean.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    pipe = PreprocessingPipeline(
        PipelineConfig(
            enable_denoise=True,
            enable_contrast=False,
            enable_deskew=False,
            enable_perspective_correction=False,
            enable_glare_suppression=False,
            enable_text_enhancement=False,
        )
    )
    result = pipe.process(noisy)

    noisy_variance = np.var(noisy)
    filtered_variance = np.var(result.image)

    assert filtered_variance < noisy_variance
    assert "bilateral_denoise" in result.applied_steps


def test_deskew_tilted_text():
    """Verify skew detection and correction on rotated text lines."""
    canvas = np.full((800, 800, 3), 255, dtype=np.uint8)
    for y in range(200, 600, 60):
        cv2.putText(
            canvas,
            "LEGAL METROLOGY COMPLIANCE LABEL VERIFICATION",
            (80, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 0),
            2,
        )

    center = (400, 400)
    rot_mat = cv2.getRotationMatrix2D(center, 10.0, 1.0)
    tilted = cv2.warpAffine(canvas, rot_mat, (800, 800), borderValue=(255, 255, 255))

    pipe = PreprocessingPipeline(
        PipelineConfig(
            enable_deskew=True,
            enable_perspective_correction=False,
            enable_denoise=False,
            enable_contrast=False,
            enable_glare_suppression=False,
            enable_text_enhancement=False,
        )
    )

    detected_angle = pipe.detect_skew_angle(tilted)
    assert abs(detected_angle - 10.0) < 2.5

    result = pipe.process(tilted)
    assert any("deskew_angle" in step for step in result.applied_steps)


def test_perspective_correction_quadrilateral():
    """Verify detection and perspective warp of a distorted quadrilateral label."""
    canvas = np.zeros((1000, 1000, 3), dtype=np.uint8)

    pts = np.array([[200, 200], [800, 250], [850, 750], [150, 800]], dtype=np.int32)
    cv2.fillPoly(canvas, [pts], (240, 240, 240))
    cv2.polylines(canvas, [pts], True, (50, 50, 50), 3)

    pipe = PreprocessingPipeline(
        PipelineConfig(
            enable_perspective_correction=True,
            min_quad_area_ratio=0.15,
            enable_deskew=False,
            enable_denoise=False,
            enable_contrast=False,
            enable_glare_suppression=False,
            enable_text_enhancement=False,
        )
    )

    result = pipe.process(canvas)
    assert "perspective_correction" in result.applied_steps
    assert len(result.transforms) > 0
    assert result.transforms[0]["type"] == "perspective"


def test_glare_suppression():
    """Verify specular glare detection and inpainting on glossy packaging."""
    # Create an image with a bright saturated specular hotspot
    canvas = np.full((600, 600, 3), (40, 100, 180), dtype=np.uint8)  # Blue package background
    # Add a white specular reflection circular hotspot
    cv2.circle(canvas, (300, 300), 40, (255, 255, 255), -1)

    pipe = PreprocessingPipeline(
        PipelineConfig(
            enable_glare_suppression=True,
            glare_luminance_threshold=240,
            glare_saturation_threshold=40,
            enable_deskew=False,
            enable_perspective_correction=False,
            enable_denoise=False,
            enable_contrast=False,
            enable_text_enhancement=False,
        )
    )

    suppressed, had_glare = pipe.suppress_glare(canvas)
    assert had_glare is True
    # The center pixel of the hotspot should no longer be pure saturated white (255, 255, 255)
    center_val = suppressed[300, 300]
    assert np.mean(center_val) < 250

    result = pipe.process(canvas)
    assert "glare_suppression" in result.applied_steps


def test_text_region_enhancement():
    """Verify text stroke edge sharpening using unsharp mask."""
    canvas = np.full((400, 400, 3), 200, dtype=np.uint8)
    cv2.putText(canvas, "BATCH 2026-X", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (10, 10, 10), 2)

    pipe = PreprocessingPipeline(
        PipelineConfig(
            enable_text_enhancement=True,
            text_unsharp_amount=0.8,
            enable_glare_suppression=False,
            enable_deskew=False,
            enable_perspective_correction=False,
            enable_denoise=False,
            enable_contrast=False,
        )
    )

    sharpened = pipe.enhance_text_regions(canvas)
    assert sharpened.shape == canvas.shape

    # Stroke edge gradients (Laplacian variance) should increase with sharpening
    orig_lap_var = cv2.Laplacian(cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
    proc_lap_var = cv2.Laplacian(cv2.cvtColor(sharpened, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
    assert proc_lap_var > orig_lap_var

    result = pipe.process(canvas)
    assert "text_region_enhancement" in result.applied_steps


def test_inverse_transforms_mapping():
    """Verify point and box inverse mapping through resize, rotation, and perspective."""
    transforms = [
        {"type": "resize", "scale": 0.5},
        {
            "type": "rotation",
            "angle": 15.0,
            "matrix": cv2.getRotationMatrix2D((300, 300), 15.0, 1.0).tolist(),
        },
    ]

    pt_in_proc = (300.0, 300.0)
    mapped_x, mapped_y = map_point_to_original(pt_in_proc[0], pt_in_proc[1], transforms)

    assert pytest.approx(mapped_x, 1.0) == 600.0
    assert pytest.approx(mapped_y, 1.0) == 600.0

    box = {"x": 280.0, "y": 280.0, "w": 40.0, "h": 40.0}
    mapped_box = map_bbox_to_original(box, 0.5, transforms=transforms)
    assert mapped_box["w"] > 0
    assert mapped_box["h"] > 0
    assert mapped_box["x"] > 0
    assert mapped_box["y"] > 0


def test_bounding_box_coordinate_inverse_mapping_simple():
    """Verify simple scale-only bounding box mapping."""
    scale_factor = 0.5
    box_in_processed = {"x": 100.0, "y": 150.0, "w": 250.0, "h": 50.0}

    mapped = map_bbox_to_original(box_in_processed, scale_factor)
    assert mapped["x"] == 200.0
    assert mapped["y"] == 300.0
    assert mapped["w"] == 500.0
    assert mapped["h"] == 100.0


def test_output_conversions(sample_test_image: np.ndarray):
    """Verify output formatting helpers (PIL, bytes, RGB array)."""
    pipe = PreprocessingPipeline(PipelineConfig(enable_deskew=False, enable_perspective_correction=False))
    res = pipe.process(sample_test_image)

    pil_img = res.to_pil()
    assert isinstance(pil_img, Image.Image)
    assert pil_img.size == (res.processed_shape[1], res.processed_shape[0])

    jpg_bytes = res.to_bytes("JPEG", quality=90)
    assert isinstance(jpg_bytes, bytes)
    assert len(jpg_bytes) > 0

    rgb_arr = res.to_rgb_array()
    assert isinstance(rgb_arr, np.ndarray)
    assert rgb_arr.shape == res.image.shape
