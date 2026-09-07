"""
SPIKE-01 — OCR Comparison (PaddleOCR vs Tesseract)
====================================================
Copy this file to d:/NiyamDrishti/test_data/spike_01_ocr.py
then run: python test_data/spike_01_ocr.py

Output goes to: test_data/spike_01_results/
  summary.csv        — per-image metrics
  report.md          — human-readable summary for 09_DECISIONS.md
  <img>_paddle.txt   — PaddleOCR raw text per image
  <img>_tess.txt     — Tesseract raw text per image
"""

import csv
import os
import sys
import time
from pathlib import Path

PHOTOS_DIR = Path(__file__).parent / "spike_photos"
RESULTS_DIR = Path(__file__).parent / "spike_01_results"
RESULTS_DIR.mkdir(exist_ok=True)

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def load_paddle():
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        return ocr
    except Exception as e:
        print(f"[WARN] PaddleOCR unavailable: {e}")
        return None


def run_paddle(ocr, image_path: Path):
    start = time.perf_counter()
    try:
        result = ocr.ocr(str(image_path), cls=True)
        elapsed_ms = (time.perf_counter() - start) * 1000
        lines, confidences = [], []
        if result and result[0]:
            for line in result[0]:
                lines.append(line[1][0])
                confidences.append(float(line[1][1]))
        mean_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return lines, mean_conf, elapsed_ms, None
    except Exception as e:
        return [], 0.0, (time.perf_counter() - start) * 1000, str(e)


def load_tesseract():
    try:
        import pytesseract
        for c in [r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                  r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]:
            if os.path.exists(c):
                pytesseract.pytesseract.tesseract_cmd = c
                break
        pytesseract.get_tesseract_version()
        return pytesseract
    except Exception as e:
        print(f"[WARN] Tesseract unavailable: {e}")
        return None


def run_tesseract(tess, image_path: Path):
    start = time.perf_counter()
    try:
        from PIL import Image
        text = tess.image_to_string(Image.open(image_path), lang="eng")
        elapsed_ms = (time.perf_counter() - start) * 1000
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return lines, elapsed_ms, None
    except Exception as e:
        return [], (time.perf_counter() - start) * 1000, str(e)


def avg(rows, key):
    vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    return round(sum(vals) / len(vals), 2) if vals else "N/A"


def main():
    images = sorted([p for p in PHOTOS_DIR.iterdir() if p.suffix.lower() in SUPPORTED_EXTS])
    if not images:
        print(f"No images in {PHOTOS_DIR}"); sys.exit(1)

    print(f"Found {len(images)} images. Loading engines...")
    paddle = load_paddle()
    tess   = load_tesseract()
    if not paddle and not tess:
        print("No OCR engine available."); sys.exit(1)

    csv_rows, report_lines = [], [
        "# SPIKE-01 OCR Comparison Report", "",
        f"Images tested: {len(images)}", "", "## Per-image results", "",
    ]

    for i, img_path in enumerate(images, 1):
        stem = img_path.stem
        print(f"[{i}/{len(images)}] {img_path.name}")
        row = {"image": img_path.name}

        if paddle:
            p_lines, p_conf, p_ms, p_err = run_paddle(paddle, img_path)
            row.update(paddle_regions=len(p_lines), paddle_mean_conf=round(p_conf,4),
                       paddle_ms=round(p_ms,1), paddle_error=p_err or "")
            (RESULTS_DIR / f"{stem}_paddle.txt").write_text("\n".join(p_lines), encoding="utf-8")
            print(f"  Paddle: {len(p_lines)} regions, conf={p_conf:.2f}, {p_ms:.0f}ms" +
                  (f"  ERR: {p_err}" if p_err else ""))
        else:
            row.update(paddle_regions="", paddle_mean_conf="", paddle_ms="", paddle_error="unavailable")

        if tess:
            t_lines, t_ms, t_err = run_tesseract(tess, img_path)
            row.update(tess_regions=len(t_lines), tess_ms=round(t_ms,1), tess_error=t_err or "")
            (RESULTS_DIR / f"{stem}_tess.txt").write_text("\n".join(t_lines), encoding="utf-8")
            print(f"  Tess:   {len(t_lines)} lines, {t_ms:.0f}ms" +
                  (f"  ERR: {t_err}" if t_err else ""))
        else:
            row.update(tess_regions="", tess_ms="", tess_error="unavailable")

        csv_rows.append(row)
        report_lines.append(
            f"### {img_path.name}\n"
            f"- Paddle: {row.get('paddle_regions','N/A')} regions, "
            f"conf={row.get('paddle_mean_conf','N/A')}, {row.get('paddle_ms','N/A')}ms\n"
            f"- Tesseract: {row.get('tess_regions','N/A')} lines, {row.get('tess_ms','N/A')}ms\n"
        )

    # Write CSV
    fields = ["image","paddle_regions","paddle_mean_conf","paddle_ms","paddle_error",
              "tess_regions","tess_ms","tess_error"]
    with open(RESULTS_DIR/"summary.csv","w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(csv_rows)

    p_avg_ms   = avg(csv_rows, "paddle_ms")
    p_avg_conf = avg(csv_rows, "paddle_mean_conf")
    t_avg_ms   = avg(csv_rows, "tess_ms")
    p_errors   = sum(1 for r in csv_rows if r.get("paddle_error"))
    t_errors   = sum(1 for r in csv_rows if r.get("tess_error"))

    report_lines += [
        "", "## Aggregate Summary", "",
        "| Engine    | Avg latency (ms) | Avg confidence | Errors |",
        "|-----------|-----------------|----------------|--------|",
        f"| PaddleOCR | {p_avg_ms}       | {p_avg_conf}   | {p_errors}     |",
        f"| Tesseract | {t_avg_ms}       | N/A            | {t_errors}     |",
        "", "## Next step",
        "Review *_paddle.txt / *_tess.txt files against what labels actually say.",
        "Log decision in docs/09_DECISIONS.md as ADR-005.",
        "Mark SPIKE-01 Done in docs/08_TRACKER.md.",
    ]
    (RESULTS_DIR/"report.md").write_text("\n".join(report_lines), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"Results: {RESULTS_DIR}")
    print(f"  Paddle avg: {p_avg_ms}ms, conf={p_avg_conf}, errors={p_errors}")
    print(f"  Tess   avg: {t_avg_ms}ms, errors={t_errors}")


if __name__ == "__main__":
    main()
