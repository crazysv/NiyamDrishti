"""Create conservative, inference-only pseudo-label candidates from Round-1 output.

Only explicit field-marked OCR text can create a candidate. Detector boxes merely
corroborate that text when they spatially agree; they never create a semantic
field label on their own. This is deliberately not a Label Studio import or a
training-data exporter.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SOURCE_DEFAULT = ROOT / "test_data" / "supplemental_round1" / "results_v1" / "raw"
OUTPUT_DEFAULT = ROOT / "test_data" / "supplemental_round1" / "pseudo_labels_v1"
COLORS = {
    "net_quantity": (105, 150, 5), "mrp": (38, 38, 220),
    "mfg_or_pkd_date": (237, 58, 124), "consumer_care": (178, 145, 8),
    "country_of_origin": (229, 70, 79),
}
AMOUNT_UNIT = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:kg|kgs|g|gm|gms|ml|l|ltr|litre|litres|pcs|pieces|nos)\b", re.I)
MONEY = re.compile(r"(?:₹|rs\.?|inr)\s*\d+(?:[.,]\d{1,2})?", re.I)
DATE_VALUE = re.compile(r"\b(?:0?[1-9]|1[0-2])[/-](?:19|20)\d{2}\b|\b(?:19|20)\d{2}[/-](?:0?[1-9]|1[0-2])\b|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(?:19|20)\d{2}\b", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.I)
PHONE = re.compile(r"(?:\+?91[\s-]?)?(?:1[\s-]?)?\d(?:[\s-]?\d){7,11}\b")


def bbox(line: dict[str, Any]) -> dict[str, float]:
    return line["bounding_box"]


def union(lines: list[dict[str, Any]]) -> dict[str, Any]:
    xs = [float(bbox(line)["x"]) for line in lines]
    ys = [float(bbox(line)["y"]) for line in lines]
    rights = [float(bbox(line)["x"]) + float(bbox(line)["w"]) for line in lines]
    bottoms = [float(bbox(line)["y"]) + float(bbox(line)["h"]) for line in lines]
    x, y, right, bottom = min(xs), min(ys), max(rights), max(bottoms)
    return {"x": round(x, 2), "y": round(y, 2), "w": round(right - x, 2), "h": round(bottom - y, 2), "coordinate_space": "source_image_px"}


def normalized(line: dict[str, Any]) -> str:
    return re.sub(r"\s+", " ", line["text"]).strip()


def nearby(lines: list[dict[str, Any]], index: int, span: int = 2) -> list[dict[str, Any]]:
    return lines[index:min(len(lines), index + span + 1)]


def explicit_candidates(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only high-specificity OCR declarations; broad text is excluded."""
    candidates: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        text = normalized(line)
        upper = text.upper()
        window = nearby(lines, index)
        joined = " ".join(normalized(item) for item in window)
        joined_upper = joined.upper()

        if re.search(r"\bNET\s*(?:WT|WEIGHT|VOL(?:UME)?|CONTENT|QUANTITY)?\b", upper) and AMOUNT_UNIT.search(joined):
            evidence = [item for item in window if AMOUNT_UNIT.search(normalized(item)) or item is line]
            candidates.append({"label": "net_quantity", "evidence": evidence, "reason": "explicit_net_marker_and_quantity_unit"})

        if re.search(r"\bM\.?R\.?P\.?\b", upper) and MONEY.search(joined):
            evidence = [item for item in window if MONEY.search(normalized(item)) or item is line]
            candidates.append({"label": "mrp", "evidence": evidence, "reason": "explicit_mrp_marker_and_currency_value"})

        if re.search(r"\b(?:MFD|MFG|PKD|PACK(?:ED|ING)?\s*DATE|MANUFACTURED)\b", upper) and DATE_VALUE.search(joined):
            evidence = [item for item in window if DATE_VALUE.search(normalized(item)) or item is line]
            candidates.append({"label": "mfg_or_pkd_date", "evidence": evidence, "reason": "explicit_date_marker_and_month_year_value"})

        if re.search(r"\b(?:MADE\s*IN|COUNTRY\s*OF\s*ORIGIN|ORIGIN\s*[:\-])", upper):
            # Avoid accepting a header-only country marker with no value.
            value_present = re.search(r"\bMADE\s*IN\s+[A-Z]{3,}|COUNTRY\s*OF\s*ORIGIN\s*[:\-]?\s*[A-Z]{3,}", joined_upper)
            if value_present:
                candidates.append({"label": "country_of_origin", "evidence": window[:2], "reason": "explicit_origin_marker_and_country_value"})

        contact_marker = re.search(r"\b(?:CONSUMER\s*(?:CARE|CONNECT|QUERY|QUERIES)|CUSTOMER\s*(?:CARE|SERVICE)|TOLL\s*FREE|HELPLINE|CALL\s*OR\s*WRITE|FOR\s*(?:QUERY|FEEDBACK|COMPLAINT))\b", upper)
        if contact_marker and (EMAIL.search(joined) or PHONE.search(joined)):
            evidence = [item for item in window if item is line or EMAIL.search(normalized(item)) or PHONE.search(normalized(item))]
            candidates.append({"label": "consumer_care", "evidence": evidence, "reason": "explicit_consumer_contact_marker_and_email_or_phone"})

    # OCR can repeat a header/value as overlapping lines. Keep one candidate per
    # label/evidence geometry rather than multiplying a single declaration.
    unique: dict[tuple[str, float, float, float, float], dict[str, Any]] = {}
    for candidate in candidates:
        box = union(candidate["evidence"])
        key = (candidate["label"], box["x"], box["y"], box["w"], box["h"])
        candidate["bounding_box"] = box
        unique[key] = candidate
    return list(unique.values())


def detector_corrobates(candidate: dict[str, Any], proposals: list[dict[str, Any]]) -> dict[str, Any] | None:
    box = candidate["bounding_box"]
    center_x, center_y = box["x"] + box["w"] / 2, box["y"] + box["h"] / 2
    matches = []
    for proposal in proposals:
        if proposal["label"] != candidate["label"]:
            continue
        proposed = proposal["bounding_box"]
        padding = 20.0
        inside = (
            proposed["x"] - padding <= center_x <= proposed["x"] + proposed["w"] + padding
            and proposed["y"] - padding <= center_y <= proposed["y"] + proposed["h"] + padding
        )
        if inside:
            matches.append(proposal)
    return max(matches, key=lambda item: item["score"]) if matches else None


def draw_overlay(path: Path, candidates: list[dict[str, Any]], destination: Path) -> Any:
    image = cv2.imread(str(path))
    if image is None:
        raise RuntimeError(f"OpenCV cannot read {path}")
    for candidate in candidates:
        box, color = candidate["bounding_box"], COLORS[candidate["label"]]
        x, y, w, h = (round(float(box[key])) for key in ("x", "y", "w", "h"))
        cv2.rectangle(image, (x, y), (x + w, y + h), color, 3)
        suffix = " + detector" if candidate["detector_corroboration"] else " OCR"
        cv2.putText(image, candidate["label"] + suffix, (x, max(22, y - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.52, color, 2, cv2.LINE_AA)
    cv2.imwrite(str(destination), image)
    return image


def contact_sheet(items: list[tuple[str, Any]], destination: Path) -> None:
    columns, cell_width, cell_height = 3, 420, 390
    sheet = np.full((math.ceil(len(items) / columns) * cell_height, columns * cell_width, 3), 20, dtype=np.uint8)
    for index, (name, image) in enumerate(items):
        scale = min(cell_width / image.shape[1], (cell_height - 28) / image.shape[0])
        resized = cv2.resize(image, (round(image.shape[1] * scale), round(image.shape[0] * scale)))
        row, col = divmod(index, columns)
        y, x = row * cell_height, col * cell_width
        top, left = (cell_height - 28 - resized.shape[0]) // 2 + 28, (cell_width - resized.shape[1]) // 2
        sheet[y + top:y + top + resized.shape[0], x + left:x + left + resized.shape[1]] = resized
        cv2.putText(sheet, name[:55], (x + 8, y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.imwrite(str(destination), sheet)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create conservative local supplemental pseudo-label candidates.")
    parser.add_argument("--source", type=Path, default=SOURCE_DEFAULT)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if not source.is_dir():
        raise SystemExit(f"Raw Round-1 directory does not exist: {source}")
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    (output / "records").mkdir(parents=True)
    (output / "overlays").mkdir()
    (output / "contact_sheets").mkdir()

    accepted_counts, rejected_detector_only = Counter(), Counter()
    records: list[dict[str, Any]] = []
    sheet_items: list[tuple[str, Any]] = []
    for index, raw_path in enumerate(sorted(source.glob("*.json")), start=1):
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        lines = raw["paddle_ocr"]["lines"]
        proposals = raw["detector"]["proposals"]
        candidates = explicit_candidates(lines)
        for candidate in candidates:
            match = detector_corrobates(candidate, proposals)
            candidate["detector_corroboration"] = (
                {"score": match["score"], "bounding_box": match["bounding_box"]} if match else None
            )
            candidate["ocr_evidence"] = [
                {"text": line["text"], "confidence": line["confidence"], "bounding_box": line["bounding_box"]}
                for line in candidate.pop("evidence")
            ]
            accepted_counts[candidate["label"]] += 1
        for proposal in proposals:
            if proposal["label"] in {"product_name", "manufacturer_or_packer", "barcode"}:
                rejected_detector_only[proposal["label"]] += 1

        source_image = ROOT / raw["source_image"]
        record = {
            "diagnostic": "supplemental_round1_conservative_pseudolabel_candidates",
            "source_image": raw["source_image"],
            "source_dimensions": raw["source_dimensions"],
            "accepted_candidates": candidates,
            "rejected_automatic_labels": [
                "product_name, manufacturer_or_packer, and barcode detector-only proposals are excluded because detector score alone is not semantic evidence.",
                "OCR text without an explicit field marker is excluded to avoid turning generic product copy into a statutory declaration label.",
            ],
            "limitations": [
                "Candidates are unreviewed pseudo-labels, not ground truth or Label Studio annotations.",
                "No supplemental accuracy score exists because these images have no reviewed ground truth.",
            ],
        }
        records.append(record)
        (output / "records" / raw_path.name).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        if candidates:
            overlay = draw_overlay(source_image, candidates, output / "overlays" / f"{raw_path.stem}.jpg")
            sheet_items.append((raw_path.stem, overlay))
            if len(sheet_items) == 12:
                contact_sheet(sheet_items, output / "contact_sheets" / f"candidates_{index // 12:03d}.jpg")
                sheet_items = []

    if sheet_items:
        contact_sheet(sheet_items, output / "contact_sheets" / "candidates_final.jpg")
    summary = {
        "diagnostic": "supplemental_round1_conservative_pseudolabel_candidates",
        "images_examined": len(records),
        "images_with_candidates": sum(bool(record["accepted_candidates"]) for record in records),
        "accepted_candidate_counts": dict(sorted(accepted_counts.items())),
        "detector_only_proposals_rejected_by_policy": dict(sorted(rejected_detector_only.items())),
        "no_ground_truth_or_accuracy_claim": True,
        "label_studio_mutated": False,
        "model_retrained": False,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
