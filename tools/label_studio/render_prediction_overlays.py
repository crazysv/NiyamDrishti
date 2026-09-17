"""Render contact sheets of local Label Studio suggestions for visual QA."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2


ROOT = Path(__file__).resolve().parents[2]
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


def resize_to_cell(image, width: int, height: int):
    scale = min(width / image.shape[1], height / image.shape[0])
    resized = cv2.resize(image, (round(image.shape[1] * scale), round(image.shape[0] * scale)))
    canvas = cv2.copyMakeBorder(
        resized,
        (height - resized.shape[0]) // 2,
        height - resized.shape[0] - (height - resized.shape[0]) // 2,
        (width - resized.shape[1]) // 2,
        width - resized.shape[1] - (width - resized.shape[1]) // 2,
        cv2.BORDER_CONSTANT,
        value=(20, 20, 20),
    )
    return canvas, scale


def overlay(image, prediction: dict) -> None:
    for item in prediction["prediction"].get("result", []):
        if item.get("type") != "rectanglelabels":
            continue
        value = item["value"]
        label = value["rectanglelabels"][0]
        height, width = image.shape[:2]
        x, y = round(width * value["x"] / 100), round(height * value["y"] / 100)
        w, h = round(width * value["width"] / 100), round(height * value["height"] / 100)
        color = COLORS.get(label, (255, 255, 255))
        cv2.rectangle(image, (x, y), (x + w, y + h), color, 3)
        cv2.putText(image, label, (x, max(18, y - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Label Studio prediction QA contact sheets.")
    parser.add_argument("--predictions", type=Path, default=ROOT / "test_data" / "label_studio" / "local_paddle_predictions.json")
    parser.add_argument("--raw-root", type=Path, default=ROOT / "test_data" / "benchmark_raw")
    parser.add_argument("--output", type=Path, default=ROOT / "tmp" / "label_studio_overlay_audit")
    parser.add_argument("--per-sheet", type=int, default=12)
    args = parser.parse_args()

    predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    columns, cell_width, cell_height = 3, 500, 520
    for start in range(0, len(predictions), args.per_sheet):
        page = predictions[start : start + args.per_sheet]
        rows = math.ceil(len(page) / columns)
        sheet = cv2.copyMakeBorder(
            cv2.UMat(rows * cell_height, columns * cell_width, cv2.CV_8UC3).get(), 0, 0, 0, 0, cv2.BORDER_CONSTANT, value=(20, 20, 20)
        )
        for offset, prediction in enumerate(page):
            data = prediction["match"]
            source = args.raw_root / data["sample_id"] / data["source_filename"]
            image = cv2.imread(str(source))
            if image is None:
                raise RuntimeError(f"Could not read {source}")
            overlay(image, prediction)
            cell, _ = resize_to_cell(image, cell_width, cell_height - 30)
            row, column = divmod(offset, columns)
            top, left = row * cell_height + 30, column * cell_width
            sheet[top : top + cell.shape[0], left : left + cell.shape[1]] = cell
            cv2.putText(sheet, f"{start + offset + 1}. {data['sample_id']}/{data['source_filename']}", (left + 8, row * cell_height + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
        destination = args.output / f"sheet_{start // args.per_sheet + 1:02d}.jpg"
        cv2.imwrite(str(destination), sheet)
        print(destination)


if __name__ == "__main__":
    main()
