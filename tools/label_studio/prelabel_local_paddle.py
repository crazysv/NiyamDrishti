"""Create and optionally apply local PaddleOCR predictions to Label Studio tasks.

This is benchmark tooling only. It never changes the product's inspection data or
rule results. Predictions are deliberately marked as unreviewed and must be
confirmed or corrected in Label Studio before they become ground truth.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

import cv2
import requests

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
# Paddle's default OneDNN pool can retain many CPU allocations across a large
# photo batch. Keep this workstation-only benchmark runner bounded; the OCR
# boxes are still mapped back to the original source image.
os.environ.setdefault("FLAGS_use_mkldnn", "false")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.calibration.detector import BarcodeCalibrationDetector
from app.services.extraction.service import DeclarationExtractionService
from app.services.ocr.paddle_engine import PaddleOCREngine

FIELD_LABELS = {
    "commodity_name": "product_name",
    "net_quantity": "net_quantity",
    "mrp": "mrp",
    "mfg_date": "mfg_or_pkd_date",
    "manufacturer_address": "manufacturer_or_packer",
    "consumer_care": "consumer_care",
    "country_of_origin": "country_of_origin",
}
MODEL_VERSION = "local-paddleocr-2.9.1"
PRODUCT_NAME_REJECT_PATTERN = re.compile(
    r"(?:@|\b(?:www\.)?[a-z0-9-]+\.(?:com|in|org)\b|https?://|"
    r"\b(?:call|toll\s*free|e-?mail|website|manufactured|marketed|address|batch|barcode)\b)",
    re.IGNORECASE,
)
EAN_UPC_PATTERN = re.compile(r"^\d{8,14}$")
CONTACT_LINE_PATTERN = re.compile(
    r"(?:\b(?:consumer|customer|dabur)\b.*\b(?:care|call|write|service|helpline|toll)\b|"
    r"\b(?:e-?mail|website|web\s*site|tel(?:ephone)?|phone|contact)\b|"
    r"@|\b(?:www\.)?[a-z0-9-]+\.(?:com|in|org)\b|\b(?:toll\s*free|1800)\b)",
    re.IGNORECASE,
)
MANUFACTURER_LINE_PATTERN = re.compile(
    r"\b(?:manufactured|packed|marketed|imported|distributed|manufacture|packer|importer|"
    r"regd\.?\s*off|address|lic(?:ence)?|mfg\.?\s*lic|factory)\b",
    re.IGNORECASE,
)
COUNTRY_LINE_PATTERN = re.compile(
    r"\b(?:country\s+of\s+origin|made\s+in|product\s+of|imported\s+from)\b",
    re.IGNORECASE,
)
MRP_LINE_PATTERN = re.compile(r"\b(?:m\.?r\.?p\.?|maximum\s+retail|inclusive|incl\.?|all\s+taxes)\b|₹|\brs\.?", re.IGNORECASE)
NET_QUANTITY_LINE_PATTERN = re.compile(
    r"\b(?:net\s*(?:wt|weight|qty|quantity|vol|volume|content)?|quantity|weight|volume)\b|"
    r"\b\d+(?:\.\d+)?\s*(?:kg|g|gm|ml|l|ltr|pcs|pieces|units?|n)\b",
    re.IGNORECASE,
)
DATE_LINE_PATTERN = re.compile(
    r"\b(?:mfg|mfd|pkd|packed\s+on|manufactured\s+on|date\s+of\s+(?:manufacture|packing))\b|"
    r"\b(?:0?[1-9]|1[0-2])\s*[/.-]\s*(?:20)?\d{2}\b",
    re.IGNORECASE,
)
WORD_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)

# The source extractors intentionally return a conservative anchor line.  For
# the benchmark, annotators need a field-level rectangle instead: e.g. the
# whole consumer-care block, not just the OCR line containing the e-mail.
# These limits keep a nearby but unrelated package feature from being pulled
# into the declaration.
FIELD_GROUP_MAX_GAP_PX = 95.0
FIELD_GROUP_MAX_DIAGONAL_PX = 135.0
FIELD_BOX_PADDING_PX = 5.0


def clip_box(box: dict[str, float], width: int, height: int) -> dict[str, float] | None:
    """Clamp a source-pixel box to the image and reject degenerate regions."""
    left = max(0.0, min(float(width), float(box["x"])))
    top = max(0.0, min(float(height), float(box["y"])))
    right = max(left, min(float(width), float(box["x"]) + float(box["w"])))
    bottom = max(top, min(float(height), float(box["y"]) + float(box["h"])))
    if right <= left or bottom <= top:
        return None
    return {"x": left, "y": top, "w": right - left, "h": bottom - top}


def bounded_working_image(image: Any, max_edge: int) -> tuple[Any, float]:
    """Bound Paddle's working pixels while retaining a scale back to source pixels."""
    height, width = image.shape[:2]
    longest_edge = max(width, height)
    if longest_edge <= max_edge:
        return image, 1.0
    scale = max_edge / longest_edge
    resized = cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
    return resized, scale


def map_box_to_source(box: dict[str, float], scale: float) -> dict[str, float]:
    if scale == 1.0:
        return dict(box)
    return {key: float(value) / scale for key, value in box.items()}


def line_box(line: Any) -> dict[str, float]:
    """Return an OCR line's source-pixel axis-aligned box."""
    return {
        "x": float(line.bounding_box.x),
        "y": float(line.bounding_box.y),
        "w": float(line.bounding_box.w),
        "h": float(line.bounding_box.h),
    }


def union_boxes(boxes: list[dict[str, float]]) -> dict[str, float]:
    if not boxes:
        raise ValueError("Cannot union an empty box list")
    left = min(box["x"] for box in boxes)
    top = min(box["y"] for box in boxes)
    right = max(box["x"] + box["w"] for box in boxes)
    bottom = max(box["y"] + box["h"] for box in boxes)
    return {"x": left, "y": top, "w": right - left, "h": bottom - top}


def padded_box(box: dict[str, float], padding: float = FIELD_BOX_PADDING_PX) -> dict[str, float]:
    return {
        "x": box["x"] - padding,
        "y": box["y"] - padding,
        "w": box["w"] + 2 * padding,
        "h": box["h"] + 2 * padding,
    }


def box_gap(first: dict[str, float], second: dict[str, float]) -> tuple[float, float, float]:
    """Return horizontal, vertical and Euclidean gaps between two boxes."""
    horizontal = max(first["x"] - (second["x"] + second["w"]), second["x"] - (first["x"] + first["w"]), 0.0)
    vertical = max(first["y"] - (second["y"] + second["h"]), second["y"] - (first["y"] + first["h"]), 0.0)
    return horizontal, vertical, math.hypot(horizontal, vertical)


def normalized_words(text: str) -> set[str]:
    return set(WORD_PATTERN.findall(text.lower()))


def raw_text_match(line_text: str, declaration_text: str) -> bool:
    """Match an OCR line that contributed to an extractor's raw declaration."""
    line_words = normalized_words(line_text)
    declaration_words = normalized_words(declaration_text)
    if not line_words or not declaration_words:
        return False
    # A short line such as "MRP" alone is too vague; meaningful overlap is
    # still useful for multi-line declarations and avoids relying on OCR order.
    overlap = line_words & declaration_words
    return len(overlap) >= min(2, len(line_words)) or (len(line_words) == 1 and len(line_text.strip()) >= 5 and line_words <= declaration_words)


def has_same_text_orientation(anchor: dict[str, float], candidate: dict[str, float]) -> bool:
    """Reject a perpendicular nearby label, such as vertical side branding."""
    anchor_is_horizontal = anchor["w"] >= anchor["h"]
    candidate_is_horizontal = candidate["w"] >= candidate["h"]
    return anchor_is_horizontal == candidate_is_horizontal


def is_valid_ean_upc(value: str) -> bool:
    """Accept only checksum-valid EAN-8/EAN-13/UPC-A/GTIN-14 digit strings."""
    digits = re.sub(r"[\s-]", "", value)
    if not EAN_UPC_PATTERN.fullmatch(digits) or len(digits) not in {8, 12, 13, 14}:
        return False
    total = 0
    for index, digit in enumerate(reversed(digits[:-1])):
        total += int(digit) * (3 if index % 2 == 0 else 1)
    return (10 - total % 10) % 10 == int(digits[-1])


def field_line_matches(label: str, text: str) -> bool:
    """Identify lines that belong to a statutory declaration block."""
    if label == "consumer_care":
        return bool(CONTACT_LINE_PATTERN.search(text))
    if label == "manufacturer_or_packer":
        return bool(MANUFACTURER_LINE_PATTERN.search(text))
    if label == "country_of_origin":
        return bool(COUNTRY_LINE_PATTERN.search(text))
    if label == "mrp":
        return bool(MRP_LINE_PATTERN.search(text))
    if label == "net_quantity":
        return bool(NET_QUANTITY_LINE_PATTERN.search(text))
    if label == "mfg_or_pkd_date":
        return bool(DATE_LINE_PATTERN.search(text))
    return False


def connected_field_lines(
    *, label: str, declaration_text: str, anchor_box: dict[str, float], lines: list[Any]
) -> list[Any]:
    """Collect the nearby OCR lines that make up one visible declaration.

    We grow only through field-specific candidate lines.  This is deliberately
    stricter than generic proximity grouping: a website elsewhere on a pack
    must not become part of the consumer-care rectangle.
    """
    candidates = [
        line
        for line in lines
        if (field_line_matches(label, line.text) or raw_text_match(line.text, declaration_text))
        and has_same_text_orientation(anchor_box, line_box(line))
    ]
    if not candidates:
        return []

    selected: list[Any] = []
    active_box = dict(anchor_box)
    remaining = list(candidates)
    while remaining:
        closest_index = -1
        closest_distance = float("inf")
        for index, line in enumerate(remaining):
            horizontal, vertical, diagonal = box_gap(active_box, line_box(line))
            if (
                horizontal <= FIELD_GROUP_MAX_GAP_PX
                and vertical <= FIELD_GROUP_MAX_GAP_PX
                and diagonal <= FIELD_GROUP_MAX_DIAGONAL_PX
                and diagonal < closest_distance
            ):
                closest_index = index
                closest_distance = diagonal
        if closest_index < 0:
            break
        selected_line = remaining.pop(closest_index)
        selected.append(selected_line)
        active_box = union_boxes([active_box, line_box(selected_line)])
    return selected


def declaration_evidence(
    *, label: str, declaration: Any, lines: list[Any]
) -> tuple[dict[str, float], str, float]:
    """Return a padded full-declaration box and its exact OCR transcription."""
    anchor_box = {key: float(declaration.bounding_box[key]) for key in ("x", "y", "w", "h")}
    grouped_lines = connected_field_lines(
        label=label,
        declaration_text=declaration.raw_text,
        anchor_box=anchor_box,
        lines=lines,
    )
    if not grouped_lines:
        return padded_box(anchor_box), declaration.raw_text, declaration.confidence

    grouped_boxes = [anchor_box, *(line_box(line) for line in grouped_lines)]
    # Preserve OCR reading order whenever available; dedupe lines as an
    # extractor's anchor text may also be a selected group line.
    seen: set[str] = set()
    transcript_lines: list[str] = []
    for line in grouped_lines:
        text = line.text.strip()
        key = " ".join(text.split()).lower()
        if text and key not in seen:
            seen.add(key)
            transcript_lines.append(text)
    if not transcript_lines:
        transcript_lines = [declaration.raw_text]
    confidence = sum(float(line.confidence) for line in grouped_lines) / len(grouped_lines)
    return padded_box(union_boxes(grouped_boxes)), "\n".join(transcript_lines), round(confidence, 4)


def barcode_evidence(
    *, barcode_box: dict[str, float], barcode_data: str | None, lines: list[Any]
) -> tuple[dict[str, float], str]:
    """Include a printed EAN/UPC digit line when it sits beside the barcode bars."""
    barcode_digits = (barcode_data or "").strip()
    candidates = [
        line
        for line in lines
        if is_valid_ean_upc(line.text)
    ]
    nearest: Any | None = None
    nearest_distance = float("inf")
    for line in candidates:
        _, _, distance = box_gap(barcode_box, line_box(line))
        if distance <= FIELD_GROUP_MAX_DIAGONAL_PX and distance < nearest_distance:
            nearest = line
            nearest_distance = distance
    if nearest is None:
        return padded_box(barcode_box), barcode_digits or "unreadable"
    digit_text = re.sub(r"[\s-]", "", nearest.text)
    return padded_box(union_boxes([barcode_box, line_box(nearest)])), digit_text or barcode_digits or "unreadable"


def region_result(
    *,
    label: str,
    text: str,
    confidence: float,
    box: dict[str, float],
    width: int,
    height: int,
) -> list[dict[str, Any]]:
    """Represent one suggestion using Label Studio's per-region result format."""
    clipped = clip_box(box, width, height)
    if clipped is None:
        return []

    region_id = uuid.uuid4().hex[:10]
    readability = "clear" if confidence >= 0.85 else "partly_obscured"
    rectangle = {
        "id": region_id,
        "type": "rectanglelabels",
        "from_name": "field",
        "to_name": "image",
        "original_width": width,
        "original_height": height,
        "image_rotation": 0,
        "value": {
            "x": round(100 * clipped["x"] / width, 4),
            "y": round(100 * clipped["y"] / height, 4),
            "width": round(100 * clipped["w"] / width, 4),
            "height": round(100 * clipped["h"] / height, 4),
            "rotation": 0,
            "rectanglelabels": [label],
        },
    }
    transcription = {
        "id": uuid.uuid4().hex[:10],
        "type": "textarea",
        "from_name": "transcription",
        "to_name": "image",
        "parentID": region_id,
        "original_width": width,
        "original_height": height,
        "image_rotation": 0,
        "value": {"text": [text or "unreadable"]},
    }
    readability_result = {
        "id": uuid.uuid4().hex[:10],
        "type": "choices",
        "from_name": "readability",
        "to_name": "image",
        "parentID": region_id,
        "original_width": width,
        "original_height": height,
        "image_rotation": 0,
        "value": {"choices": [readability]},
    }
    return [rectangle, transcription, readability_result]


def remove_unreliable_suggestions(result: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Suppress obvious false field suggestions before human review.

    This is deliberately conservative benchmark pre-label hygiene, not a legal
    rule. A missing suggestion is preferable to presenting an annotator with a
    confident-but-wrong product-name or QR-code-as-barcode box. The annotator
    can still add a genuine field wherever it is visibly printed.
    """
    transcriptions = {
        str(item.get("parentID")): " ".join(item.get("value", {}).get("text", []))
        for item in result
        if item.get("type") == "textarea"
    }
    rejected_ids = {
        str(item.get("id"))
        for item in result
        if item.get("type") == "rectanglelabels"
        and (
            (
                item.get("value", {}).get("rectanglelabels") == ["product_name"]
                and PRODUCT_NAME_REJECT_PATTERN.search(transcriptions.get(str(item.get("id")), ""))
            )
            or (
                item.get("value", {}).get("rectanglelabels") == ["barcode"]
                and not is_valid_ean_upc(transcriptions.get(str(item.get("id")), "").strip())
            )
        )
    }
    if not rejected_ids:
        return result
    return [
        item
        for item in result
        if str(item.get("id")) not in rejected_ids and str(item.get("parentID")) not in rejected_ids
    ]


def normalize_prediction_suggestions(predictions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Apply deterministic suggestion-only hygiene to generated or saved output."""
    removed = 0
    for item in predictions:
        result = item["prediction"].get("result", [])
        cleaned = remove_unreliable_suggestions(result)
        removed += (len(result) - len(cleaned)) // 3
        item["prediction"]["result"] = cleaned
        item["prediction"].setdefault("meta", {})["statutory_prediction_count"] = len(cleaned) // 3
    return predictions, removed


def build_prediction(
    image_path: Path,
    source_image_id: str,
    ocr_engine: PaddleOCREngine,
    extraction_service: DeclarationExtractionService,
    barcode_detector: BarcodeCalibrationDetector,
    max_ocr_edge: int,
) -> dict[str, Any]:
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Could not decode image: {image_path}")
    height, width = image.shape[:2]
    working_image, scale = bounded_working_image(image, max_ocr_edge)
    rgb_image = cv2.cvtColor(working_image, cv2.COLOR_BGR2RGB)
    ocr_result = ocr_engine.extract(rgb_image, source_image_id)
    if scale != 1.0:
        for line in ocr_result.lines:
            line.bounding_box.x /= scale
            line.bounding_box.y /= scale
            line.bounding_box.w /= scale
            line.bounding_box.h /= scale
            line.bounding_box.polygon = [[point[0] / scale, point[1] / scale] for point in line.bounding_box.polygon]
    declarations = extraction_service.extract_from_ocr_result(ocr_result)

    result: list[dict[str, Any]] = []
    for declaration in declarations:
        label = FIELD_LABELS.get(declaration.field_type)
        if label is None:
            continue
        evidence_box, evidence_text, evidence_confidence = declaration_evidence(
            label=label,
            declaration=declaration,
            lines=ocr_result.lines,
        )
        result.extend(
            region_result(
                label=label,
                text=evidence_text,
                confidence=evidence_confidence,
                box=evidence_box,
                width=width,
                height=height,
            )
        )

    calibration = barcode_detector.calibrate(working_image)
    if calibration.is_calibrated and calibration.barcode_bbox:
        barcode_box = map_box_to_source(calibration.barcode_bbox, scale)
        evidence_box, barcode_text = barcode_evidence(
            barcode_box=barcode_box,
            barcode_data=calibration.barcode_data,
            lines=ocr_result.lines,
        )
        result.extend(
            region_result(
                label="barcode",
                text=barcode_text,
                confidence=0.95,
                box=evidence_box,
                width=width,
                height=height,
            )
        )

    result = remove_unreliable_suggestions(result)
    return {
        "model_version": MODEL_VERSION,
        "score": ocr_result.average_confidence,
        "result": result,
        "meta": {
            "engine": ocr_result.engine_used,
            "ocr_line_count": len(ocr_result.lines),
            "statutory_prediction_count": len(result) // 3,
            "barcode_detected": calibration.is_calibrated,
            "working_max_edge_px": max_ocr_edge,
        },
    }


def create_predictions(
    tasks_path: Path, raw_root: Path, output_path: Path, limit: int | None, max_ocr_edge: int
) -> list[dict[str, Any]]:
    tasks = json.loads(tasks_path.read_text(encoding="utf-8-sig"))
    if not isinstance(tasks, list):
        raise ValueError("Task manifest must be a JSON array")

    ocr_engine = PaddleOCREngine()
    extraction_service = DeclarationExtractionService()
    barcode_detector = BarcodeCalibrationDetector()
    predictions: list[dict[str, Any]] = []

    selected_tasks = tasks[:limit] if limit else tasks
    total = len(selected_tasks)
    for index, task in enumerate(selected_tasks, start=1):
        data = task["data"]
        image_path = raw_root / str(data["sample_id"]) / str(data["source_filename"])
        if index == 1 or index == total or index % 10 == 0:
            print(f"OCR [{index}/{total}] {data['sample_id']}/{data['source_filename']}", flush=True)
        prediction = build_prediction(
            image_path=image_path,
            source_image_id=f"{data['sample_id']}/{data['source_filename']}",
            ocr_engine=ocr_engine,
            extraction_service=extraction_service,
            barcode_detector=barcode_detector,
            max_ocr_edge=max_ocr_edge,
        )
        predictions.append(
            {
                "match": {
                    "sample_id": data["sample_id"],
                    "source_filename": data["source_filename"],
                },
                "prediction": prediction,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(predictions, indent=2), encoding="utf-8")
    return predictions


def request_json(session: requests.Session, method: str, url: str, **kwargs: Any) -> Any:
    response = session.request(method, url, timeout=30, **kwargs)
    if not response.ok:
        raise RuntimeError(f"Label Studio {method} {url} failed ({response.status_code}): {response.text[:500]}")
    return response.json() if response.content else None


def paged_items(session: requests.Session, url: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        payload = request_json(session, "GET", url, params={**params, "page": page, "page_size": 100})
        if isinstance(payload, list):
            return payload
        batch = payload.get("tasks") or payload.get("results") or payload
        if not batch:
            return items
        items.extend(batch)
        if not payload.get("next"):
            return items
        page += 1


def apply_predictions(
    predictions: list[dict[str, Any]], base_url: str, project_id: int, api_token: str, replace: bool, auth_scheme: str
) -> None:
    session = requests.Session()
    session.headers.update({"Authorization": f"{auth_scheme} {api_token}", "Content-Type": "application/json"})
    base_url = base_url.rstrip("/")

    tasks = paged_items(session, f"{base_url}/api/tasks", {"project": project_id})
    task_ids = {
        (str(task["data"].get("sample_id")), str(task["data"].get("source_filename"))): task["id"] for task in tasks
    }
    if len(task_ids) != len(tasks):
        raise RuntimeError("Label Studio task data are missing sample_id or source_filename; refusing to import predictions.")

    if replace:
        existing = paged_items(session, f"{base_url}/api/predictions", {"project": project_id})
        for prediction in existing:
            if prediction.get("model_version") == MODEL_VERSION:
                request_json(session, "DELETE", f"{base_url}/api/predictions/{prediction['id']}/")

    total = len(predictions)
    for index, item in enumerate(predictions, start=1):
        match = item["match"]
        task_id = task_ids.get((str(match["sample_id"]), str(match["source_filename"])))
        if task_id is None:
            raise RuntimeError(f"No existing Label Studio task matches {match}")
        payload = {"task": task_id, "project": project_id, **item["prediction"]}
        request_json(session, "POST", f"{base_url}/api/predictions/", json=payload)
        if index == 1 or index == total or index % 10 == 0:
            print(f"Imported prediction [{index}/{total}] for task {task_id}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pre-label NiyamDrishti benchmark tasks using only local PaddleOCR.")
    parser.add_argument("--tasks", type=Path, default=REPOSITORY_ROOT / "test_data" / "label_studio" / "tasks_raw.json")
    parser.add_argument("--raw-root", type=Path, default=REPOSITORY_ROOT / "test_data" / "benchmark_raw")
    parser.add_argument("--output", type=Path, default=REPOSITORY_ROOT / "test_data" / "label_studio" / "local_paddle_predictions.json")
    parser.add_argument(
        "--reuse-output",
        action="store_true",
        help="Attach an existing prediction JSON file without rerunning local OCR.",
    )
    parser.add_argument("--limit", type=int, help="Process only the first N tasks; useful for a smoke test.")
    parser.add_argument(
        "--max-ocr-edge",
        type=int,
        default=1920,
        help="Largest edge PaddleOCR receives; predictions are mapped back to the original image pixels.",
    )
    parser.add_argument("--apply", action="store_true", help="Attach predictions to existing Label Studio tasks after generating them.")
    parser.add_argument("--label-studio-url", default="http://localhost:8080")
    parser.add_argument("--project-id", type=int, default=1)
    parser.add_argument("--replace", action="store_true", help="Remove prior local-Paddle predictions before applying new ones.")
    parser.add_argument("--api-token", default=os.getenv("LABEL_STUDIO_API_TOKEN"), help="Label Studio personal access token (or LABEL_STUDIO_API_TOKEN).")
    parser.add_argument("--auth-scheme", choices=("Token", "Bearer"), default="Token")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.limit is not None and args.limit <= 0:
        raise SystemExit("--limit must be positive")
    if args.max_ocr_edge < 512:
        raise SystemExit("--max-ocr-edge must be at least 512")
    if args.reuse_output:
        if args.limit is not None:
            raise SystemExit("--reuse-output cannot be combined with --limit")
        if not args.output.is_file():
            raise SystemExit(f"Prediction file not found: {args.output}")
        predictions = json.loads(args.output.read_text(encoding="utf-8"))
        if not isinstance(predictions, list):
            raise SystemExit("Prediction file must contain a JSON array")
        predictions, removed = normalize_prediction_suggestions(predictions)
        if removed:
            args.output.write_text(json.dumps(predictions, indent=2), encoding="utf-8")
            print(f"Removed {removed} obviously misclassified field suggestions.")
        print(f"Reusing {len(predictions)} local PaddleOCR predictions: {args.output}")
    else:
        predictions = create_predictions(args.tasks, args.raw_root, args.output, args.limit, args.max_ocr_edge)
        print(f"Created {len(predictions)} local PaddleOCR predictions: {args.output}")
    if args.apply:
        if not args.api_token:
            raise SystemExit("--apply requires --api-token or LABEL_STUDIO_API_TOKEN")
        apply_predictions(predictions, args.label_studio_url, args.project_id, args.api_token, args.replace, args.auth_scheme)
        print("Predictions attached to the existing Label Studio tasks. Refresh Label Studio to review them.")


if __name__ == "__main__":
    main()
