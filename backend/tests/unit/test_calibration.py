from unittest.mock import MagicMock

import numpy as np
import pytest

from app.services.calibration import (
    NOMINAL_BARCODE_WIDTHS_MM,
    BarcodeCalibrationDetector,
    CalibrationResult,
    OpticalCalibrationService,
)


def test_gs1_nominal_widths_lookup():
    """Verify GS1 standard nominal widths for retail barcodes (CAL-01)."""
    assert NOMINAL_BARCODE_WIDTHS_MM["EAN-13"] == 37.29
    assert NOMINAL_BARCODE_WIDTHS_MM["UPC-A"] == 37.29
    assert NOMINAL_BARCODE_WIDTHS_MM["EAN-8"] == 26.73


def test_optical_scale_derivation_from_barcode():
    """Verify mm-per-pixel derivation given detected barcode pixel width (CAL-01 & CAL-02)."""
    detector = BarcodeCalibrationDetector()
    # Mock OpenCV detector returning valid EAN-13 barcode detection
    detector._try_opencv = MagicMock(
        return_value={
            "type": "EAN-13",
            "data": "8901030384728",
            "bbox": {"x": 100.0, "y": 200.0, "w": 372.9, "h": 100.0},
            "width_px": 372.9,
        }
    )

    dummy_image = np.zeros((600, 800, 3), dtype=np.uint8)
    result = detector.calibrate(dummy_image)

    assert result.is_calibrated is True
    assert result.barcode_type == "EAN-13"
    assert result.barcode_data == "8901030384728"
    assert result.nominal_width_mm == 37.29
    assert result.barcode_width_px == 372.9
    # 37.29 mm / 372.9 px = 0.1 mm/px
    assert pytest.approx(result.scale_mm_per_px, 0.001) == 0.1
    assert result.warning is None


def test_uncalibrated_fallback_path():
    """Verify uncalibrated fallback path when no barcode is found (CAL-03)."""
    detector = BarcodeCalibrationDetector()
    detector._try_opencv = MagicMock(return_value=None)
    detector._try_pyzbar = MagicMock(return_value=None)

    dummy_image = np.zeros((600, 800, 3), dtype=np.uint8)
    result = detector.calibrate(dummy_image)

    assert result.is_calibrated is False
    assert result.scale_mm_per_px is None
    assert result.method == "uncalibrated_pdp_ratio"
    assert result.warning is not None
    assert "uncalibrated" in result.warning.lower()


def test_measure_dimension_calibrated():
    """Verify physical millimeter measurement when calibrated scale is available."""
    service = OpticalCalibrationService()
    calib = CalibrationResult(
        is_calibrated=True,
        scale_mm_per_px=0.08,  # 0.08 mm per pixel
        barcode_type="EAN-13",
        method="barcode_ean13",
    )

    # 50px font height on 1000px high PDP panel
    measured = service.measure_dimension(
        height_px=50.0,
        pdp_height_px=1000.0,
        calibration=calib,
    )

    assert measured.is_calibrated is True
    assert measured.height_mm == 4.0  # 50px * 0.08 mm/px = 4.0 mm
    assert measured.pdp_height_ratio == 0.05  # 50 / 1000
    assert measured.warning is None


def test_measure_dimension_uncalibrated_fallback():
    """Verify relative PDP-ratio calculation and warning when uncalibrated (CAL-03)."""
    service = OpticalCalibrationService()
    calib = CalibrationResult(
        is_calibrated=False,
        scale_mm_per_px=None,
        method="uncalibrated_pdp_ratio",
        warning="No standard barcode detected for optical calibration; physical millimeter measurements are uncalibrated.",
    )

    # 40px font height on 800px high PDP panel
    measured = service.measure_dimension(
        height_px=40.0,
        pdp_height_px=800.0,
        calibration=calib,
    )

    assert measured.is_calibrated is False
    assert measured.height_mm is None
    assert measured.pdp_height_ratio == 0.05  # 40 / 800
    assert measured.warning is not None
    assert "uncalibrated" in measured.warning.lower()
