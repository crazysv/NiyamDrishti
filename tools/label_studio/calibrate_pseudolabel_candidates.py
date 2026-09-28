"""Calibrate explicit-OCR pseudo-label candidates on trusted training annotations.

This intentionally evaluates the candidate rules only on the 73-image training
split. The product-disjoint validation split remains untouched for a later model
experiment and no model is trained by this script.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.ocr.paddle_engine import PaddleOCREngine  # noqa: E402
from reconcile_supplemental_pseudolabels import explicit_candidates  # noqa: E402


COCO_DEFAULT = ROOT / "test_data" / "detector_dataset" / "train.coco.json"
RAW_ROOT_DEFAULT = ROOT / "test_data" / "benchmark_raw"
OUTPUT_DEFAULT = ROOT / "test_data" / "supplemental_round1" / "pseudolabel_calibration_v1"
IOU_THRESHOLD = 0.50
MIN_PRECISION = 0.85
MIN_TRUE_POSITIVES = 3


def iou(left: dict[str, Any], right: dict[str, Any]) -> float:
    ax1, ay1 = float(left["x"]), float(left["y"])
    ax2, ay2 = ax1 + float(left["w"]), ay1 + float(left["h"])
    bx1, by1 = float(right["x"]), float(right["y"])
    bx2, by2 = bx1 + float(right["w"]), by1 + float(right["h"])
    width, height = max(0.0, min(ax2, bx2) - max(ax1, bx1)), max(0.0, min(ay2, by2) - max(ay1, by1))
    intersection = width * height
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - intersection
    return intersection / union if union else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate pseudo-label OCR rules against training labels.")
    parser.add_argument("--coco", type=Path, default=COCO_DEFAULT)
    parser.add_argument("--raw-root", type=Path, default=RAW_ROOT_DEFAULT)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    coco_path, raw_root, output = args.coco.resolve(), args.raw_root.resolve(), args.output.resolve()
    if not coco_path.is_file() or not raw_root.is_dir():
        raise SystemExit("Trusted training manifest or raw image root does not exist.")
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    output.mkdir(parents=True)

    coco = json.loads(coco_path.read_text(encoding="utf-8"))
    labels = {entry["id"]: entry["name"] for entry in coco["categories"]}
    annotations: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for annotation in coco["annotations"]:
        annotations[annotation["image_id"]].append({
            "label": labels[annotation["category_id"]],
            "bounding_box": dict(zip(("x", "y", "w", "h"), annotation["bbox"])),
        })

    ocr = PaddleOCREngine()
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    per_image: list[dict[str, Any]] = []
    candidate_fields = {"net_quantity", "mrp", "mfg_or_pkd_date", "consumer_care", "country_of_origin"}
    for index, image_meta in enumerate(coco["images"], start=1):
        source = raw_root / image_meta["file_name"]
        image = cv2.imread(str(source))
        if image is None:
            raise RuntimeError(f"OpenCV cannot read {source}")
        result = ocr.extract(image, image_meta["file_name"])
        candidates = explicit_candidates([line.model_dump() for line in result.lines])
        ground_truth = [entry for entry in annotations[image_meta["id"]] if entry["label"] in candidate_fields]
        matched_ground_truth: set[int] = set()
        image_matches: list[dict[str, Any]] = []
        for candidate in candidates:
            best_index, best_iou = None, 0.0
            for ground_index, truth in enumerate(ground_truth):
                if ground_index in matched_ground_truth or truth["label"] != candidate["label"]:
                    continue
                score = iou(candidate["bounding_box"], truth["bounding_box"])
                if score > best_iou:
                    best_index, best_iou = ground_index, score
            if best_index is not None and best_iou >= IOU_THRESHOLD:
                counts[candidate["label"]]["tp"] += 1
                matched_ground_truth.add(best_index)
                image_matches.append({"label": candidate["label"], "outcome": "tp", "iou": round(best_iou, 4)})
            else:
                counts[candidate["label"]]["fp"] += 1
                image_matches.append({"label": candidate["label"], "outcome": "fp", "best_iou": round(best_iou, 4)})
        for ground_index, truth in enumerate(ground_truth):
            if ground_index not in matched_ground_truth:
                counts[truth["label"]]["fn"] += 1
        per_image.append({"source_image": image_meta["file_name"], "candidate_count": len(candidates), "matches": image_matches})
        if index % 10 == 0 or index == len(coco["images"]):
            print(f"Calibrated {index}/{len(coco['images'])}", flush=True)

    metrics: dict[str, dict[str, Any]] = {}
    for label in sorted(candidate_fields):
        tp, fp, fn = (counts[label][key] for key in ("tp", "fp", "fn"))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        metrics[label] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 4), "recall": round(recall, 4),
            "eligible_for_later_pseudolabel_experiment": precision >= MIN_PRECISION and tp >= MIN_TRUE_POSITIVES,
            "gate": f"precision >= {MIN_PRECISION:.2f} and TP >= {MIN_TRUE_POSITIVES}",
        }
    report = {
        "purpose": "training_split_calibration_only_not_independent_accuracy",
        "split": "trusted_train_only",
        "images_examined": len(coco["images"]),
        "iou_threshold": IOU_THRESHOLD,
        "metrics": metrics,
        "per_image": per_image,
        "validation_split_used": False,
        "model_retrained": False,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "per_image"}, indent=2))


if __name__ == "__main__":
    main()
