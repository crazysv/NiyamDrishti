"""Score raw physical-device ML Kit OCR coverage against reviewed field boxes.

This intentionally measures OCR-line geometry only. ML Kit returns no statutory
field labels, so the result is not field extraction accuracy, transcription
accuracy, or a legal-verdict readiness claim.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluate_field_boxes import DEFAULT_GROUND_TRUTH, FIELD_LABELS, Region, collect_ground_truth, load_list

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_OCR = ROOT / "test_data" / "label_studio" / "reports" / "android_mlkit_raw_ocr.json"
DEFAULT_PADDLE = ROOT / "test_data" / "label_studio" / "reports" / "ground_truth_v1_paddle_ocr_coverage.json"
DEFAULT_OUTPUT = ROOT / "test_data" / "label_studio" / "reports" / "ground_truth_v1_android_mlkit_coverage.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score Android ML Kit raw OCR-line coverage inside reviewed field boxes.")
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    parser.add_argument("--raw-ocr", type=Path, default=DEFAULT_RAW_OCR)
    parser.add_argument("--paddle-report", type=Path, default=DEFAULT_PADDLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def line_inside_ratio(field: Region, line: Region) -> float:
    left, top = max(field.x, line.x), max(field.y, line.y)
    right, bottom = min(field.x + field.width, line.x + line.width), min(field.y + field.height, line.y + line.height)
    overlap = max(0.0, right - left) * max(0.0, bottom - top)
    line_area = line.width * line.height
    return overlap / line_area if line_area else 0.0


def read_json(path: Path, description: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"{description} was not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{description} is not valid JSON: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{description} must be a JSON object: {path}")
    return payload


def raw_lines_by_task(raw: dict[str, Any]) -> tuple[dict[tuple[str, str], list[Region]], list[dict[str, Any]]]:
    lines_by_task: dict[tuple[str, str], list[Region]] = {}
    errors: list[dict[str, Any]] = []
    records = raw.get("records")
    if not isinstance(records, list):
        raise ValueError("Raw Android ML Kit report has no records list.")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append({"kind": "malformed_record", "index": index})
            continue
        sample_id, filename = record.get("sample_id"), record.get("source_filename")
        result = record.get("result")
        width, height = result.get("sourceWidth") if isinstance(result, dict) else None, result.get("sourceHeight") if isinstance(result, dict) else None
        if not isinstance(sample_id, str) or not isinstance(filename, str) or not isinstance(width, int) or not isinstance(height, int) or width < 1 or height < 1:
            errors.append({"kind": "missing_task_or_dimensions", "index": index})
            continue
        key = (sample_id, filename)
        if key in lines_by_task:
            errors.append({"kind": "duplicate_task", "task": list(key)})
            continue
        lines: list[Region] = []
        for line_index, line in enumerate(result.get("lines", [])):
            box = line.get("boundingBox") if isinstance(line, dict) else None
            if not isinstance(box, dict):
                errors.append({"kind": "malformed_line", "task": list(key), "index": line_index})
                continue
            try:
                x, y, box_width, box_height = float(box["x"]), float(box["y"]), float(box["w"]), float(box["h"])
            except (KeyError, TypeError, ValueError):
                errors.append({"kind": "invalid_line_geometry", "task": list(key), "index": line_index})
                continue
            if box_width <= 0 or box_height <= 0 or box.get("coordinateSpace") != "source_image_px":
                errors.append({"kind": "invalid_line_contract", "task": list(key), "index": line_index})
                continue
            lines.append(Region(key, str(line.get("text", "")), 100 * x / width, 100 * y / height, 100 * box_width / width, 100 * box_height / height))
        lines_by_task[key] = lines
    return lines_by_task, errors


def coverage_report(truth: dict[tuple[str, str], list[Region]], lines_by_task: dict[tuple[str, str], list[Region]]) -> dict[str, Any]:
    totals: dict[str, Counter[str]] = defaultdict(Counter)
    not_seen: list[dict[str, Any]] = []
    for key, fields in truth.items():
        for field in fields:
            totals[field.label]["reviewed_boxes"] += 1
            best_ratio, best_line = max(
                ((line_inside_ratio(field, line), line) for line in lines_by_task.get(key, [])),
                default=(0.0, None),
                key=lambda candidate: candidate[0],
            )
            if best_ratio >= 0.5:
                totals[field.label]["ocr_seen"] += 1
            else:
                not_seen.append({
                    "task": list(key), "label": field.label,
                    "best_line_inside_ratio": round(best_ratio, 4),
                    "best_line_text": best_line.label if best_line else None,
                })
    fields = {
        label: {
            "reviewed_boxes": totals[label]["reviewed_boxes"],
            "ocr_seen": totals[label]["ocr_seen"],
            "ocr_line_coverage": round(totals[label]["ocr_seen"] / totals[label]["reviewed_boxes"], 4) if totals[label]["reviewed_boxes"] else None,
        }
        for label in sorted(FIELD_LABELS)
    }
    reviewed = sum(row["reviewed_boxes"] for row in fields.values())
    seen = sum(row["ocr_seen"] for row in fields.values())
    return {
        "definition": "A field is seen when at least 50% of one raw ML Kit OCR line lies inside its reviewed field rectangle.",
        "fields": fields,
        "overall": {"reviewed_boxes": reviewed, "ocr_seen": seen, "ocr_line_coverage": round(seen / reviewed, 4) if reviewed else None},
        "not_seen": not_seen,
    }


def markdown(report: dict[str, Any]) -> str:
    coverage = report["coverage"]
    lines = [
        "# Android ML Kit raw OCR coverage diagnostic",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "## Scope",
        "",
        f"- Device: `{report['device'].get('device_serial', 'unknown')}`",
        f"- Reviewed benchmark tasks run: {report['task_count']}/{report['ground_truth_task_count']}",
        f"- Reviewed statutory-field boxes: {coverage['overall']['reviewed_boxes']}",
        f"- {coverage['definition']}",
        "- This is raw OCR geometry coverage only. It is not field-classification, text-transcription, legal-verdict, or independent-holdout accuracy.",
        "",
        "## Coverage",
        "",
        "| Field | Reviewed boxes | ML Kit seen | ML Kit coverage | Paddle diagnostic coverage |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    paddle_fields = report.get("paddle_comparison", {}).get("fields", {})
    for label, row in coverage["fields"].items():
        paddle = paddle_fields.get(label, {}).get("ocr_line_coverage")
        format_pct = lambda value: "—" if value is None else f"{value * 100:.1f}%"
        lines.append(f"| {label} | {row['reviewed_boxes']} | {row['ocr_seen']} | {format_pct(row['ocr_line_coverage'])} | {format_pct(paddle)} |")
    total = coverage["overall"]
    paddle_total = report.get("paddle_comparison", {}).get("overall", {}).get("ocr_line_coverage")
    lines.extend([
        "",
        f"Overall ML Kit raw-line coverage: {total['ocr_seen']}/{total['reviewed_boxes']} ({total['ocr_line_coverage'] * 100:.1f}%).",
        f"Existing local Paddle diagnostic coverage: {paddle_total * 100:.1f}% ." if paddle_total is not None else "No Paddle comparison report was available.",
        "",
        "The images used to create this reviewed benchmark are development data. Do not treat this result as an independent accuracy claim or enable offline statutory verdicts solely from this diagnostic.",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    truth_tasks = load_list(args.ground_truth, "Ground truth")
    truth, audit = collect_ground_truth(truth_tasks)
    if audit["errors"]:
        raise ValueError(f"Ground-truth audit has {len(audit['errors'])} error(s); refusing benchmark score.")
    raw = read_json(args.raw_ocr, "Raw Android ML Kit report")
    lines_by_task, raw_errors = raw_lines_by_task(raw)
    if raw_errors:
        raise ValueError(f"Raw Android ML Kit report has {len(raw_errors)} contract error(s); refusing benchmark score.")
    missing = sorted(set(truth) - set(lines_by_task))
    extra = sorted(set(lines_by_task) - set(truth))
    if missing or extra:
        raise ValueError(f"Raw run does not match frozen benchmark: {len(missing)} missing, {len(extra)} extra task(s).")
    paddle = read_json(args.paddle_report, "Paddle coverage report") if args.paddle_report.exists() else {}
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ground_truth": str(args.ground_truth.resolve()),
        "raw_ocr": str(args.raw_ocr.resolve()),
        "ground_truth_task_count": len(truth),
        "task_count": len(lines_by_task),
        "device": {key: raw.get(key) for key in ("device_serial", "package_name", "bridge", "normalization", "generated_at")},
        "coverage": coverage_report(truth, lines_by_task),
        "paddle_comparison": {"definition": paddle.get("definition"), "fields": paddle.get("fields", {}), "overall": paddle.get("overall", {})},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    overall = report["coverage"]["overall"]
    print(f"Android ML Kit raw-line coverage: {overall['ocr_seen']}/{overall['reviewed_boxes']} ({overall['ocr_line_coverage']:.1%})")
    print(f"Wrote {args.output.resolve()} and {args.output.resolve().with_suffix('.md')}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        print(f"Android ML Kit coverage evaluation failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
