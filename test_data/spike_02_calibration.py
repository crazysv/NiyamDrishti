"""
SPIKE-02 — Barcode mm-per-pixel Calibration Accuracy
=====================================================
Copy this file to d:/NiyamDrishti/test_data/spike_02_calibration.py
then run: python test_data/spike_02_calibration.py

For every image in spike_photos/ that contains a detectable EAN-13 or EAN-8
barcode, this script:
  1. Detects the barcode and measures its pixel width
  2. Derives a mm-per-pixel scale factor (EAN-13 nominal width = 37.29 mm)
  3. Reports the scale factor so we can judge consistency across photos

Output:
  spike_02_results/summary.csv    — per-image calibration table
  spike_02_results/report.md      — human-readable summary for 09_DECISIONS.md
"""

import csv
import sys
import time
from pathlib import Path

import cv2

PHOTOS_DIR = Path(__file__).parent / "spike_photos"
RESULTS_DIR = Path(__file__).parent / "spike_02_results"
RESULTS_DIR.mkdir(exist_ok=True)

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# EAN-13 standard nominal width (mm) per ISO/IEC 15420
EAN13_WIDTH_MM = 37.29
EAN8_WIDTH_MM  = 26.73


def detect_barcodes(image_path: Path):
    """
    Try pyzbar first, fall back to OpenCV's built-in QR/barcode detector.
    Returns list of dicts: {type, data, pixel_width, pixel_height}
    """
    results = []

    # --- pyzbar ---
    try:
        import pyzbar.pyzbar as pyzbar
        img = cv2.imread(str(image_path))
        if img is None:
            return results, "cv2 could not open image"
        decoded = pyzbar.decode(img)
        for obj in decoded:
            x, y, w, h = obj.rect
            results.append({
                "type":        obj.type,
                "data":        obj.data.decode("utf-8", errors="replace"),
                "pixel_width": w,
                "pixel_height":h,
                "detector":    "pyzbar",
            })
        if results:
            return results, None
    except ImportError:
        pass
    except Exception as e:
        pass

    # --- OpenCV BarcodeDetector (OpenCV 4.5.3+) ---
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            return results, "cv2 could not open image"
        detector = cv2.barcode.BarcodeDetector()
        ok, decoded_info, decoded_type, corners = detector.detectAndDecodeWithType(img)
        if ok and decoded_info:
            for info, btype, corner in zip(decoded_info, decoded_type, corners):
                pts = corner.reshape(-1, 2)
                # width = distance between left two points
                w = int(abs(pts[1][0] - pts[0][0]))
                h = int(abs(pts[2][1] - pts[1][1]))
                results.append({
                    "type":        btype,
                    "data":        info,
                    "pixel_width": w,
                    "pixel_height":h,
                    "detector":    "opencv",
                })
    except Exception as e:
        pass

    return results, None


def mm_per_pixel(barcode_type: str, pixel_width: int) -> float | None:
    if pixel_width <= 0:
        return None
    btype = str(barcode_type).upper()
    if "EAN13" in btype or btype == "EAN-13":
        return EAN13_WIDTH_MM / pixel_width
    if "EAN8" in btype or btype == "EAN-8":
        return EAN8_WIDTH_MM / pixel_width
    # Unknown barcode type — can't calibrate with known width
    return None


def main():
    images = sorted([p for p in PHOTOS_DIR.iterdir() if p.suffix.lower() in SUPPORTED_EXTS])
    if not images:
        print(f"No images in {PHOTOS_DIR}"); sys.exit(1)

    print(f"Found {len(images)} images. Scanning for barcodes...")

    csv_rows = []
    calibrated_count = 0
    mpp_values = []

    report_lines = [
        "# SPIKE-02 Barcode Calibration Report", "",
        f"Images tested: {len(images)}", "",
        "## Per-image results", "",
    ]

    for i, img_path in enumerate(images, 1):
        print(f"[{i}/{len(images)}] {img_path.name}")
        start = time.perf_counter()
        barcodes, err = detect_barcodes(img_path)
        elapsed_ms = (time.perf_counter() - start) * 1000

        if err:
            print(f"  ERROR: {err}")
            csv_rows.append({"image": img_path.name, "status": f"error: {err}",
                             "barcode_type":"","barcode_data":"",
                             "pixel_width":"","mm_per_pixel":"","detector":""})
            report_lines.append(f"### {img_path.name}\n- ERROR: {err}\n")
            continue

        if not barcodes:
            print(f"  No barcode found ({elapsed_ms:.0f}ms)")
            csv_rows.append({"image": img_path.name, "status": "no_barcode",
                             "barcode_type":"","barcode_data":"",
                             "pixel_width":"","mm_per_pixel":"","detector":""})
            report_lines.append(f"### {img_path.name}\n- No barcode detected\n")
            continue

        for bc in barcodes:
            mpp = mm_per_pixel(bc["type"], bc["pixel_width"])
            if mpp:
                calibrated_count += 1
                mpp_values.append(mpp)
                status = "calibrated"
            else:
                status = f"unknown_type:{bc['type']}"

            print(f"  {bc['type']} | px_w={bc['pixel_width']} | "
                  f"mm/px={mpp:.5f}" if mpp else f"  {bc['type']} | uncalibratable")

            csv_rows.append({
                "image":        img_path.name,
                "status":       status,
                "barcode_type": bc["type"],
                "barcode_data": bc["data"][:30],
                "pixel_width":  bc["pixel_width"],
                "mm_per_pixel": round(mpp, 6) if mpp else "",
                "detector":     bc["detector"],
            })
            report_lines.append(
                f"### {img_path.name}\n"
                f"- Type: {bc['type']}, detector: {bc['detector']}\n"
                f"- Pixel width: {bc['pixel_width']}px\n"
                f"- mm/px: {round(mpp,6) if mpp else 'N/A (unknown barcode type)'}\n"
            )

    # CSV
    fields = ["image","status","barcode_type","barcode_data","pixel_width","mm_per_pixel","detector"]
    with open(RESULTS_DIR/"summary.csv","w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(csv_rows)

    # Stats
    if mpp_values:
        avg_mpp = sum(mpp_values) / len(mpp_values)
        min_mpp = min(mpp_values)
        max_mpp = max(mpp_values)
        spread_pct = ((max_mpp - min_mpp) / avg_mpp) * 100
    else:
        avg_mpp = min_mpp = max_mpp = spread_pct = None

    report_lines += [
        "", "## Aggregate Summary", "",
        f"- Images with calibrated barcodes: {calibrated_count} / {len(images)}",
        f"- Average mm/px: {round(avg_mpp,6) if avg_mpp else 'N/A'}",
        f"- Min mm/px: {round(min_mpp,6) if min_mpp else 'N/A'}",
        f"- Max mm/px: {round(max_mpp,6) if max_mpp else 'N/A'}",
        f"- Spread (max-min / avg): {round(spread_pct,2) if spread_pct is not None else 'N/A'}%",
        "",
        "## Interpretation guidance",
        "- Spread < 5%: calibration is reliable across photos — proceed with confidence.",
        "- Spread 5–15%: usable but flag measurements as 'approximate' in the report.",
        "- Spread > 15%: too variable — investigate angle/distance factors before relying on it.",
        "",
        "## Next step",
        "Log the acceptable-use threshold decision in docs/09_DECISIONS.md as ADR-006.",
        "Mark SPIKE-02 Done in docs/08_TRACKER.md.",
    ]
    (RESULTS_DIR/"report.md").write_text("\n".join(report_lines), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"Results: {RESULTS_DIR}")
    print(f"  Calibrated: {calibrated_count}/{len(images)} images")
    if avg_mpp:
        print(f"  mm/px avg={round(avg_mpp,6)}, spread={round(spread_pct,2)}%")
    else:
        print("  No calibration data — no EAN barcodes detected in any photo.")
        print("  Tip: make sure at least some photos show the barcode panel clearly.")


if __name__ == "__main__":
    main()
