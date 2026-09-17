"""Measure whether local Paddle OCR sees text inside reviewed field boxes.

This is a diagnostic between reviewed geometry and declaration extraction. A
high OCR-line coverage with low field-prediction recall indicates extractor or
field-grouping work; low coverage indicates the image/OCR stage is the limit.
It does not produce or modify Label Studio predictions.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2
from evaluate_field_boxes import (
    DEFAULT_GROUND_TRUTH,
    DEFAULT_PREDICTIONS,
    FIELD_LABELS,
    Region,
    collect_ground_truth,
    collect_predictions,
    intersection_over_union,
    load_list,
)
from prelabel_local_paddle import BACKEND_ROOT, bounded_working_image

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.ocr.paddle_engine import PaddleOCREngine

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_ROOT = ROOT / "test_data" / "benchmark_raw"
DEFAULT_OUTPUT = ROOT / "test_data" / "label_studio" / "reports" / "ground_truth_v1_paddle_ocr_coverage.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit raw Paddle OCR coverage inside reviewed field boxes.")
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-ocr-edge", type=int, default=1920)
    parser.add_argument("--limit", type=int, help="Inspect only the first N annotated tasks for a smoke test.")
    return parser.parse_args()


def line_region(task_key: tuple[str, str], line: Any, width: int, height: int) -> Region:
    box = line.bounding_box
    return Region(task_key, str(line.text), 100 * box.x / width, 100 * box.y / height, 100 * box.w / width, 100 * box.h / height)


def line_inside_ratio(field: Region, line: Region) -> float:
    left, top = max(field.x, line.x), max(field.y, line.y)
    right, bottom = min(field.x + field.width, line.x + line.width), min(field.y + field.height, line.y + line.height)
    overlap = max(0.0, right - left) * max(0.0, bottom - top)
    line_area = line.width * line.height
    return overlap / line_area if line_area else 0.0


def main() -> None:
    args = parse_args()
    if args.limit is not None and args.limit <= 0:
        raise SystemExit("--limit must be positive")
    if args.max_ocr_edge < 512:
        raise SystemExit("--max-ocr-edge must be at least 512")
    truth_tasks = load_list(args.ground_truth, "Ground truth")
    prediction_items = load_list(args.predictions, "Prediction")
    truth, audit = collect_ground_truth(truth_tasks)
    predictions, prediction_errors = collect_predictions(prediction_items)
    if audit["errors"]:
        raise SystemExit(f"Ground-truth audit has {len(audit['errors'])} error(s); refusing OCR coverage run.")
    if prediction_errors:
        raise SystemExit(f"Prediction audit has {len(prediction_errors)} error(s); refusing OCR coverage run.")
    task_keys = sorted(truth)
    if args.limit:
        task_keys = task_keys[: args.limit]
    engine = PaddleOCREngine()
    totals: dict[str, Counter[str]] = defaultdict(Counter)
    unreadable: list[dict[str, Any]] = []
    extraction_gap_examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, key in enumerate(task_keys, start=1):
        sample_id, filename = key
        image_path = args.raw_root / sample_id / filename
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Could not decode benchmark image: {image_path}")
        height, width = image.shape[:2]
        working, scale = bounded_working_image(image, args.max_ocr_edge)
        result = engine.extract(cv2.cvtColor(working, cv2.COLOR_BGR2RGB), f"{sample_id}/{filename}")
        if scale != 1:
            for line in result.lines:
                line.bounding_box.x /= scale
                line.bounding_box.y /= scale
                line.bounding_box.w /= scale
                line.bounding_box.h /= scale
        lines = [line_region(key, line, width, height) for line in result.lines]
        if index == 1 or index == len(task_keys) or index % 10 == 0:
            print(f"OCR coverage [{index}/{len(task_keys)}] {sample_id}/{filename}", flush=True)
        for field in truth[key]:
            totals[field.label]["reviewed_boxes"] += 1
            best_ratio, best_line = max(
                ((line_inside_ratio(field, line), line) for line in lines),
                default=(0.0, None),
                key=lambda candidate: candidate[0],
            )
            if best_ratio >= 0.5:
                totals[field.label]["ocr_seen"] += 1
            else:
                unreadable.append({"task": list(key), "label": field.label, "best_line_inside_ratio": round(best_ratio, 4)})
            has_field_prediction = any(
                candidate.label == field.label and intersection_over_union(field, candidate) >= 0.5
                for candidate in predictions.get(key, [])
            )
            if best_ratio >= 0.5 and not has_field_prediction and len(extraction_gap_examples[field.label]) < 12:
                extraction_gap_examples[field.label].append(
                    {
                        "task": list(key),
                        "ocr_line_text": best_line.label if best_line else None,
                        "ocr_line_inside_ratio": round(best_ratio, 4),
                    }
                )
    fields = {
        label: {
            "reviewed_boxes": totals[label]["reviewed_boxes"],
            "ocr_seen": totals[label]["ocr_seen"],
            "ocr_line_coverage": round(totals[label]["ocr_seen"] / totals[label]["reviewed_boxes"], 4)
            if totals[label]["reviewed_boxes"]
            else None,
        }
        for label in sorted(FIELD_LABELS)
    }
    reviewed = sum(row["reviewed_boxes"] for row in fields.values())
    seen = sum(row["ocr_seen"] for row in fields.values())
    report = {
        "ground_truth": str(args.ground_truth.resolve()),
        "raw_root": str(args.raw_root.resolve()),
        "selected_task_count": len(task_keys),
        "max_ocr_edge": args.max_ocr_edge,
        "definition": "An OCR line is seen when at least 50% of that line lies inside a reviewed field rectangle.",
        "fields": fields,
        "overall": {"reviewed_boxes": reviewed, "ocr_seen": seen, "ocr_line_coverage": round(seen / reviewed, 4) if reviewed else None},
        "not_seen": unreadable,
        "extraction_gap_examples": dict(extraction_gap_examples),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OCR line coverage: {seen}/{reviewed} ({seen / reviewed:.1%})")
    print(f"Wrote {args.output.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        print(f"OCR coverage audit failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
