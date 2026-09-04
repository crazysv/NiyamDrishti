import os
import sys
from pathlib import Path
import json

# Ensure UTF-8 output on Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from app.services.ocr.service import OCRService
from app.services.extraction.service import DeclarationExtractionService
from app.services.calibration.service import OpticalCalibrationService
from app.services.rules.engine import RuleEngine

def test_samples():
    ocr_service = OCRService()
    extractor = DeclarationExtractionService()
    calib_service = OpticalCalibrationService()
    rule_engine = RuleEngine()

    base_dir = Path("d:/NiyamDrishti/test_data/sample_data")
    sample_dirs = ["sample_1", "sample_2", "sample_3"]

    results_summary = {}

    for sample_name in sample_dirs:
        sample_path = base_dir / sample_name
        if not sample_path.exists():
            continue

        print(f"\n=======================================================")
        print(f" PROCESSING {sample_name.upper()} ")
        print(f"=======================================================")

        sample_res = {
            "images": {},
            "all_declarations": [],
            "barcodes": []
        }

        all_decls = []

        # Find all jpeg/png images
        image_files = sorted(list(sample_path.glob("*.jpeg")) + list(sample_path.glob("*.jpg")) + list(sample_path.glob("*.png")))
        
        for img_file in image_files:
            role = img_file.stem
            print(f"\n--- Panel: {img_file.name} ---")
            with open(img_file, "rb") as f:
                img_bytes = f.read()

            # 1. Barcode / Calibration
            calib = calib_service.calibrate_image(img_bytes)
            barcode_str = calib.barcode_data if calib.is_calibrated else None
            if barcode_str:
                print(f"  [BARCODE DETECTED] {barcode_str} (scale: {calib.scale_mm_per_px:.4f} mm/px)")
                sample_res["barcodes"].append(barcode_str)
            else:
                print(f"  [BARCODE] None detected")

            # 2. OCR
            ocr_res = ocr_service.process_image(img_bytes, source_image_id=img_file.name)
            print(f"  [OCR] Lines detected: {len(ocr_res.lines)}, Avg Confidence: {ocr_res.average_confidence:.2f}")

            # 3. Extraction
            decls = extractor.extract_from_ocr_result(ocr_res, barcode=barcode_str)
            print(f"  [EXTRACTED DECLARATIONS] Found {len(decls)} fields:")
            for d in decls:
                print(f"    * {d.field_type}: '{d.raw_text[:60]}' (confidence: {d.confidence})")
                all_decls.append(d)

            sample_res["images"][img_file.name] = {
                "barcode": barcode_str,
                "lines_count": len(ocr_res.lines),
                "extracted_fields": [d.field_type for d in decls],
                "sample_ocr_lines": [l.text for l in ocr_res.lines[:10]]
            }

        sample_res["all_declarations"] = [
            {"field_type": d.field_type, "raw_text": d.raw_text, "confidence": d.confidence, "bbox": d.bounding_box}
            for d in all_decls
        ]

        results_summary[sample_name] = sample_res

    with open("d:/NiyamDrishti/test_data/sample_data/extraction_results.json", "w", encoding="utf-8") as out_f:
        json.dump(results_summary, out_f, indent=2, ensure_ascii=False)
    
    print("\nSaved full extraction output to test_data/sample_data/extraction_results.json")

if __name__ == "__main__":
    test_samples()
