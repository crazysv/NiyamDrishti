import cv2
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.ocr.paddle_engine import PaddleOCREngine
from app.services.extraction.service import DeclarationExtractionService
from app.services.calibration.detector import BarcodeCalibrationDetector

def test_samples():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../test_data/test_pics"))
    engine = PaddleOCREngine()
    service = DeclarationExtractionService()
    detector = BarcodeCalibrationDetector()

    all_declarations = []
    calibration_results = {}

    for img_name in ["front.jpeg", "back.jpeg", "side_panel.jpeg"]:
        img_path = os.path.join(base_dir, img_name)
        img = cv2.imread(img_path)
        assert img is not None, f"Failed to load {img_path}"

        # 1. Barcode calibration
        cal = detector.calibrate(img)
        calibration_results[img_name] = {
            "calibrated": cal.is_calibrated,
            "type": cal.barcode_type,
            "data": cal.barcode_data,
            "scale": cal.scale_mm_per_px,
        }

        # 2. OCR
        ocr_res = engine.extract(img, img_name)

        # 3. Extraction
        decls = service.extract_declarations(ocr_res.lines, img_name)
        all_declarations.extend(decls)

    print("=== CALIBRATION SUMMARY ===")
    for k, v in calibration_results.items():
        print(f"{k}: {v}")

    print("\n=== EXTRACTED STATUTORY DECLARATIONS ===")
    found_types = set()
    for d in all_declarations:
        found_types.add(d.field_type)
        print(f"[{d.field_type.upper()}] ({d.source_image_id}) - {d.raw_text}")
        print(f"   Verdict: {d.verdict}, Conf: {d.confidence:.2f}, Payload: {d.parsed_value}")

    print(f"\nUnique statutory field types extracted: {found_types}")
    assert "mrp" in found_types, "MRP missing"
    assert "mfg_date" in found_types, "Mfg Date missing"
    assert "net_quantity" in found_types, "Net Quantity missing"
    assert "commodity_name" in found_types, "Commodity Name missing"
    assert "manufacturer_address" in found_types, "Manufacturer Address missing"
    assert "consumer_care" in found_types, "Consumer Care missing"
    assert any(c["calibrated"] for c in calibration_results.values()), "Barcode calibration failed on all images"
    print("\nALL STATUTORY DECLARATIONS & CALIBRATION VERIFIED SUCCESSFULLY ON REAL SAMPLES!")

if __name__ == "__main__":
    test_samples()
