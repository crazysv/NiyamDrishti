import logging
from typing import Any

import cv2
import numpy as np

from app.services.calibration.schemas import CalibrationResult

logger = logging.getLogger(__name__)

# Standard GS1 nominal physical dimensions for retail barcodes (in millimeters)
NOMINAL_BARCODE_WIDTHS_MM = {
    "EAN-13": 37.29,
    "EAN13": 37.29,
    "UPC-A": 37.29,
    "UPCA": 37.29,
    "EAN-8": 26.73,
    "EAN8": 26.73,
    "UPC-E": 22.11,
    "UPCE": 22.11,
    "CODE-128": 38.00,
    "CODE128": 38.00,
}

DEFAULT_1D_NOMINAL_WIDTH_MM = 37.29


class BarcodeCalibrationDetector:
    """
    Detects retail package barcodes and derives physical mm-per-pixel optical scale (CAL-01 & CAL-03).
    Uses OpenCV's cv2.barcode.BarcodeDetector with pyzbar compatibility.
    """

    def __init__(self) -> None:
        try:
            self.cv_detector = cv2.barcode.BarcodeDetector()
        except Exception as e:
            logger.warning(f"Failed to initialize cv2.barcode.BarcodeDetector: {e}")
            self.cv_detector = None

    def _try_pyzbar(self, image: np.ndarray) -> dict[str, Any] | None:
        """Attempts barcode detection using pyzbar if native libraries are present."""
        try:
            from pyzbar import pyzbar

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            barcodes = pyzbar.decode(gray)

            for b in barcodes:
                b_type = b.type.upper()
                b_data = b.data.decode("utf-8", errors="ignore")
                x, y, w, h = b.rect.left, b.rect.top, b.rect.width, b.rect.height

                if w > 20:  # Valid barcode detection
                    return {
                        "type": b_type,
                        "data": b_data,
                        "bbox": {"x": float(x), "y": float(y), "w": float(w), "h": float(h)},
                        "width_px": float(w),
                    }
        except Exception:
            pass
        return None

    def _try_opencv(self, image: np.ndarray) -> dict[str, Any] | None:
        """Attempts barcode detection using OpenCV's built-in BarcodeDetector."""
        if self.cv_detector is None:
            return None

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        try:
            res = self.cv_detector.detectAndDecode(gray)
            if len(res) == 4:
                ok, decoded_info, decoded_type, points = res
            elif len(res) == 3:
                decoded_info, decoded_type, points = res
                ok = points is not None and len(points) > 0
            else:
                return None

            if ok and points is not None and len(points) > 0:
                for idx, pts in enumerate(points):
                    b_type = decoded_type[idx] if idx < len(decoded_type) and decoded_type[idx] else "EAN-13"
                    b_data = decoded_info[idx] if idx < len(decoded_info) else ""

                    pts_array = np.array(pts).reshape(-1, 2)
                    xs = pts_array[:, 0]
                    ys = pts_array[:, 1]
                    min_x, max_x = float(np.min(xs)), float(np.max(xs))
                    min_y, max_y = float(np.min(ys)), float(np.max(ys))

                    w = max_x - min_x
                    h = max_y - min_y

                    # Barcode width along dominant dimension
                    width_px = max(w, h)

                    if width_px > 25:
                        return {
                            "type": str(b_type).upper(),
                            "data": str(b_data),
                            "bbox": {"x": round(min_x, 1), "y": round(min_y, 1), "w": round(w, 1), "h": round(h, 1)},
                            "width_px": round(width_px, 1),
                        }
        except Exception as e:
            logger.debug(f"OpenCV barcode detection failed: {e}")

        return None

    def _try_zxing(self, image: np.ndarray) -> dict[str, Any] | None:
        """Attempts barcode detection using zxingcpp with raw and adaptive thresholding."""
        try:
            import zxingcpp

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            candidates = [gray]

            # Glossy packaging / glare fallback: adaptive thresholding
            try:
                thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 4)
                candidates.append(thresh)
            except Exception:
                pass

            for candidate in candidates:
                results = zxingcpp.read_barcodes(candidate)
                for b in results:
                    raw_fmt = str(b.format).replace("BarcodeFormat.", "").replace("_", "-").upper()
                    data = str(b.text)
                    pts = [
                        (b.position.top_left.x, b.position.top_left.y),
                        (b.position.top_right.x, b.position.top_right.y),
                        (b.position.bottom_right.x, b.position.bottom_right.y),
                        (b.position.bottom_left.x, b.position.bottom_left.y),
                    ]
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    min_x, max_x = float(min(xs)), float(max(xs))
                    min_y, max_y = float(min(ys)), float(max(ys))
                    w = max_x - min_x
                    h = max_y - min_y
                    width_px = max(w, h)

                    if width_px > 20:
                        return {
                            "type": raw_fmt,
                            "data": data,
                            "bbox": {"x": round(min_x, 1), "y": round(min_y, 1), "w": round(w, 1), "h": round(h, 1)},
                            "width_px": round(width_px, 1),
                        }
        except Exception as e:
            logger.debug(f"zxingcpp detection failed: {e}")
        return None

    def calibrate(self, image: np.ndarray) -> CalibrationResult:
        """
        Executes optical calibration on the image.
        1. Attempts barcode detection (zxingcpp / OpenCV / pyzbar)
        2. If detected: look up nominal physical width in millimeters and compute mm-per-pixel scale.
        3. If not detected (CAL-03): return uncalibrated fallback result with explicit warning.
        """
        detected: dict[str, Any] | None = None

        # 1. Try zxingcpp first (fastest, most robust for 1D retail barcodes & glossy packaging)
        detected = self._try_zxing(image)

        # 2. Try OpenCV detector
        if not detected:
            detected = self._try_opencv(image)

        # 3. Try pyzbar fallback
        if not detected:
            detected = self._try_pyzbar(image)

        # 3. Successful calibration path
        if detected:
            b_type = detected["type"]
            b_data = detected["data"]
            width_px = detected["width_px"]
            bbox = detected["bbox"]

            nominal_mm = NOMINAL_BARCODE_WIDTHS_MM.get(b_type, DEFAULT_1D_NOMINAL_WIDTH_MM)
            scale_mm_per_px = round(float(nominal_mm / width_px), 5)

            method_name = f"barcode_{b_type.lower().replace('-', '')}"

            return CalibrationResult(
                is_calibrated=True,
                scale_mm_per_px=scale_mm_per_px,
                barcode_type=b_type,
                barcode_data=b_data,
                barcode_bbox=bbox,
                barcode_width_px=width_px,
                nominal_width_mm=nominal_mm,
                method=method_name,
                warning=None,
            )

        # 4. Uncalibrated Fallback Path (CAL-03)
        return CalibrationResult(
            is_calibrated=False,
            scale_mm_per_px=None,
            barcode_type=None,
            barcode_data=None,
            barcode_bbox=None,
            barcode_width_px=None,
            nominal_width_mm=None,
            method="uncalibrated_pdp_ratio",
            warning="No standard barcode detected for optical calibration; physical millimeter measurements are uncalibrated.",
        )
