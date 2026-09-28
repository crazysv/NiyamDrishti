"""Run an inference-only detector + PaddleOCR diagnostic on supplemental images.

This deliberately does *not* create Label Studio annotations, accepted labels,
or training data.  It retains source-pixel proposals and raw OCR output solely
for qualitative review of the downloaded supplemental-image copies.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from PIL import Image
from torchvision.models.detection import fasterrcnn_mobilenet_v3_large_fpn
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.ocr.paddle_engine import PaddleOCREngine  # noqa: E402


LABELS = {
    1: "product_name",
    2: "net_quantity",
    3: "mrp",
    4: "mfg_or_pkd_date",
    5: "manufacturer_or_packer",
    6: "consumer_care",
    7: "country_of_origin",
    8: "barcode",
}
COLORS = {
    "product_name": (235, 99, 37),
    "net_quantity": (105, 150, 5),
    "mrp": (38, 38, 220),
    "mfg_or_pkd_date": (237, 58, 124),
    "manufacturer_or_packer": (12, 88, 234),
    "consumer_care": (178, 145, 8),
    "country_of_origin": (229, 70, 79),
    "barcode": (81, 65, 55),
}


def source_tensor(path: Path) -> tuple[torch.Tensor, int, int]:
    """Build a tensor without NumPy conversion (safe with local Torch builds)."""
    with Image.open(path) as pil_image:
        image = pil_image.convert("RGB")
        width, height = image.size
        raw = bytearray(image.tobytes())
    tensor = torch.frombuffer(raw, dtype=torch.uint8).reshape(height, width, 3)
    return tensor.permute(2, 0, 1).float().div(255), width, height


def load_detector(checkpoint_path: Path) -> torch.nn.Module:
    checkpoint: dict[str, Any] = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    model = fasterrcnn_mobilenet_v3_large_fpn(weights=None, weights_backbone=None)
    predictor = FastRCNNPredictor(model.roi_heads.box_predictor.cls_score.in_features, len(LABELS) + 1)
    model.roi_heads.box_predictor = predictor
    state = checkpoint.get("model_state_dict", checkpoint)
    model.load_state_dict(state, strict=True)
    model.eval()
    return model


def detector_proposals(model: torch.nn.Module, path: Path, threshold: float) -> tuple[list[dict[str, Any]], int, int]:
    tensor, width, height = source_tensor(path)
    with torch.inference_mode():
        output = model([tensor])[0]
    proposals: list[dict[str, Any]] = []
    for box, score, class_id in zip(output["boxes"], output["scores"], output["labels"]):
        confidence = float(score.item())
        label_id = int(class_id.item())
        if confidence < threshold:
            continue
        if label_id not in LABELS:
            continue
        x1, y1, x2, y2 = (float(value.item()) for value in box)
        x1, x2 = max(0.0, min(x1, width)), max(0.0, min(x2, width))
        y1, y2 = max(0.0, min(y1, height)), max(0.0, min(y2, height))
        if x2 <= x1 or y2 <= y1:
            continue
        proposals.append({
            "label": LABELS[label_id],
            "class_id": label_id,
            "score": round(confidence, 5),
            "bounding_box": {
                "x": round(x1, 2), "y": round(y1, 2),
                "w": round(x2 - x1, 2), "h": round(y2 - y1, 2),
                "coordinate_space": "source_image_px",
            },
        })
    return proposals, width, height


def draw_detector(image, proposals: list[dict[str, Any]]) -> Any:
    canvas = image.copy()
    for proposal in proposals:
        box = proposal["bounding_box"]
        x, y, w, h = (round(float(box[key])) for key in ("x", "y", "w", "h"))
        color = COLORS[proposal["label"]]
        cv2.rectangle(canvas, (x, y), (x + w, y + h), color, 3)
        caption = f"{proposal['label']} {proposal['score']:.2f}"
        cv2.putText(canvas, caption, (x, max(20, y - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)
    return canvas


def draw_ocr(image, lines: list[dict[str, Any]]) -> Any:
    canvas = image.copy()
    for line in lines:
        polygon = line["bounding_box"].get("polygon") or []
        if len(polygon) == 4:
            points = np.array(polygon, dtype="int32")
            cv2.polylines(canvas, [points], True, (0, 220, 255), 2, cv2.LINE_AA)
    return canvas


def make_contact_sheet(items: list[tuple[str, Any]], destination: Path) -> None:
    columns, cell_width, cell_height = 3, 420, 390
    rows = math.ceil(len(items) / columns)
    sheet = cv2.copyMakeBorder(
        cv2.UMat(rows * cell_height, columns * cell_width, cv2.CV_8UC3).get(),
        0, 0, 0, 0, cv2.BORDER_CONSTANT, value=(20, 20, 20),
    )
    for index, (name, image) in enumerate(items):
        scale = min(cell_width / image.shape[1], (cell_height - 28) / image.shape[0])
        resized = cv2.resize(image, (round(image.shape[1] * scale), round(image.shape[0] * scale)))
        top = (cell_height - 28 - resized.shape[0]) // 2 + 28
        left = (cell_width - resized.shape[1]) // 2
        row, column = divmod(index, columns)
        y, x = row * cell_height, column * cell_width
        sheet[y + top:y + top + resized.shape[0], x + left:x + left + resized.shape[1]] = resized
        cv2.putText(sheet, name[:58], (x + 8, y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.imwrite(str(destination), sheet)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local inference-only supplemental Round-1 diagnostic.")
    parser.add_argument("--source", type=Path, default=ROOT / "test_data" / "supplemental_round1" / "eligible")
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "test_data" / "models" / "niyamdrishti_field_detector_best.pth")
    parser.add_argument("--output", type=Path, default=ROOT / "test_data" / "supplemental_round1" / "results_v1")
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--limit", type=int, default=0, help="Process only the first N images (0 means all).")
    parser.add_argument("--contact-sheet-size", type=int, default=12)
    args = parser.parse_args()

    source, checkpoint, output = args.source.resolve(), args.checkpoint.resolve(), args.output.resolve()
    if not source.is_dir() or not checkpoint.is_file():
        raise SystemExit("Source directory or detector checkpoint does not exist.")
    if not 0.0 <= args.confidence <= 1.0:
        raise SystemExit("--confidence must be between 0 and 1.")
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing diagnostic: {output}")

    images = [path for path in sorted(source.iterdir()) if path.is_file()]
    if args.limit:
        images = images[:args.limit]
    if not images:
        raise SystemExit("No source images selected.")
    for folder in (output / "raw", output / "detector_overlays", output / "ocr_overlays", output / "contact_sheets"):
        folder.mkdir(parents=True, exist_ok=True)

    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    model = load_detector(checkpoint)
    paddle = PaddleOCREngine()
    field_counts: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    sheets: list[tuple[str, Any]] = []
    started = time.perf_counter()

    for index, path in enumerate(images, start=1):
        source_id = str(path.relative_to(ROOT)).replace("\\", "/")
        try:
            proposals, width, height = detector_proposals(model, path, args.confidence)
            image = cv2.imread(str(path))
            if image is None:
                raise RuntimeError("OpenCV could not read image")
            ocr = paddle.extract(image, source_id)
            ocr_payload = ocr.model_dump()
            for proposal in proposals:
                field_counts[proposal["label"]] += 1
            record = {
                "diagnostic": "supplemental_round1_inference_only",
                "source_image": source_id,
                "source_dimensions": {"width": width, "height": height},
                "detector": {"checkpoint": str(checkpoint.relative_to(ROOT)).replace("\\", "/"), "confidence_threshold": args.confidence, "proposals": proposals},
                "paddle_ocr": ocr_payload,
                "limitations": [
                    "No supplemental ground truth exists, so this file contains no accuracy or F1 claim.",
                    "Detector proposals are unreviewed suggestions and are not Label Studio annotations or training labels.",
                ],
            }
            (output / "raw" / f"{path.stem}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            detector_image = draw_detector(image, proposals)
            ocr_image = draw_ocr(image, ocr_payload["lines"])
            cv2.imwrite(str(output / "detector_overlays" / f"{path.stem}.jpg"), detector_image)
            cv2.imwrite(str(output / "ocr_overlays" / f"{path.stem}.jpg"), ocr_image)
            sheets.append((path.name, detector_image))
        except Exception as error:  # Preserve a per-source failure record and continue.
            errors.append({"source_image": source_id, "error": str(error)})

        if index % 10 == 0 or index == len(images):
            elapsed = time.perf_counter() - started
            print(f"Processed {index}/{len(images)} in {elapsed:.1f}s; errors={len(errors)}", flush=True)

        if len(sheets) == args.contact_sheet_size:
            sheet_number = math.ceil(index / args.contact_sheet_size)
            make_contact_sheet(sheets, output / "contact_sheets" / f"detector_{sheet_number:03d}.jpg")
            sheets = []

    if sheets:
        sheet_number = math.ceil(len(images) / args.contact_sheet_size)
        make_contact_sheet(sheets, output / "contact_sheets" / f"detector_{sheet_number:03d}.jpg")

    elapsed = round(time.perf_counter() - started, 2)
    summary = {
        "diagnostic": "supplemental_round1_inference_only",
        "images_requested": len(images),
        "images_completed": len(images) - len(errors),
        "errors": errors,
        "detector_proposal_counts": dict(sorted(field_counts.items())),
        "elapsed_seconds": elapsed,
        "no_ground_truth_or_accuracy_claim": True,
        "source_images_unchanged": True,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
