import sys
from pathlib import Path
import json

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from app.services.ocr.service import OCRService
from app.services.extraction.service import DeclarationExtractionService
from app.services.calibration.service import OpticalCalibrationService
from app.services.rules.engine import RuleEngine

def run_inspection_eval():
    ocr_service = OCRService()
    extraction_service = DeclarationExtractionService()
    calib_service = OpticalCalibrationService()
    rule_engine = RuleEngine()

    base_dir = Path("d:/NiyamDrishti/test_data/sample_data")
    samples = ["sample_1", "sample_2", "sample_3"]

    print("================================================================================")
    print(" END-TO-END HACKATHON LIVE EVALUATION AUDIT FOR ALL 3 PHYSICAL PRODUCTS ")
    print("================================================================================")

    for s_name in samples:
        s_path = base_dir / s_name
        if not s_path.exists():
            continue

        print(f"\n==================================================================")
        print(f" PRODUCT: {s_name.upper()} ")
        print(f"==================================================================")

        all_decls = []
        image_files = sorted(list(s_path.glob("*.jpeg")) + list(s_path.glob("*.jpg")) + list(s_path.glob("*.png")))
        # Skip debug crops
        image_files = [f for f in image_files if "crop" not in f.name]

        sample_barcode = None

        # 1. Image intake and extraction
        for img_f in image_files:
            with open(img_f, "rb") as f:
                img_bytes = f.read()

            # Barcode
            calib = calib_service.calibrate_image(img_bytes)
            if calib.is_calibrated and calib.barcode_data:
                sample_barcode = calib.barcode_data

            ocr_res = ocr_service.process_image(img_bytes, source_image_id=img_f.name)
            decls = extraction_service.extract_from_ocr_result(ocr_res, barcode=sample_barcode)
            all_decls.extend(decls)

        # Deduplicate declarations across panels (same as save_extracted_fields)
        grouped = {}
        for d in all_decls:
            grouped.setdefault(d.field_type, []).append(d)

        final_decls = [max(items, key=lambda x: x.confidence) for items in grouped.values()]

        print(f"\nDetected Barcode: {sample_barcode}")
        print(f"Total Unique Statutory Declarations Extracted: {len(final_decls)}")
        for d in final_decls:
            parsed = json.loads(d.parsed_value) if isinstance(d.parsed_value, str) else d.parsed_value
            bbox = d.bounding_box
            print(f"  * [{d.field_type.upper()}] (Conf: {d.confidence:.2f})")
            print(f"    Raw: {d.raw_text}")
            print(f"    Dynamic BBox: x={bbox.get('x')}, y={bbox.get('y')}, w={bbox.get('w')}, h={bbox.get('h')}")

        # 2. Rule Evaluation
        # Convert to mock model fields
        import uuid

        class MockField:
            def __init__(self, d):
                self.id = uuid.uuid4()
                self.field_type = d.field_type
                self.raw_text = d.raw_text
                self.parsed_value = d.parsed_value
                self.confidence = d.confidence
                self.bounding_box = d.bounding_box
                self.source_image_id = d.source_image_id
                self.officer_override_value = None

        mock_fields = [MockField(d) for d in final_decls]
        mock_images = [
            {
                "image_role": "front_pdp" if "front" in img_f.name else "back_panel",
                "width_px": 960,
                "height_px": 1280,
                "calibration_scale_mm_per_px": 0.192 if "sample_1" in s_name else (0.268 if "sample_2" in s_name else 0.20),
            }
            for img_f in image_files
        ]

        summary = rule_engine.evaluate_rules(
            fields=mock_fields,
            images=mock_images,
            commodity_category="food" if "tiger" in s_name else "cosmetics",
            rule_pack=rule_engine.default_pack,
        )

        passed_count = sum(1 for r in summary.results if r.verdict == "pass")
        print(f"\n>>> FINAL COMPLIANCE VERDICT: {summary.overall_status.upper()} <<<")
        print(f"Rules Passed: {passed_count}/{len(summary.results)}")
        if summary.violations:
            print(f"Statutory Violations Flagged ({len(summary.violations)}):")
            for v in summary.violations:
                print(f"  ! Rule {v.get('rule_id')} [{v.get('severity', '').upper()}]: {v.get('description')}")
                print(f"    Citation: {v.get('citation')}")
        else:
            print("  All Legal Metrology (Packaged Commodities) Rules, 2011 fully satisfied!")

if __name__ == "__main__":
    run_inspection_eval()
