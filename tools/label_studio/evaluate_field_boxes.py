"""Audit reviewed statutory-field boxes and score local Paddle suggestions.

This evaluates only source-image geometry and field labels. The first review
pass intentionally permits box-only annotations, so it must not claim OCR-text
accuracy. Predictions and reviewed annotations remain local benchmark data.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GROUND_TRUTH = ROOT / "test_data" / "label_studio" / "exports" / "ground_truth_v1.json"
DEFAULT_PREDICTIONS = ROOT / "test_data" / "label_studio" / "local_paddle_predictions.json"
DEFAULT_OUTPUT = ROOT / "test_data" / "label_studio" / "reports" / "ground_truth_v1_paddle_metrics.json"
FIELD_LABELS = {
    "product_name",
    "net_quantity",
    "mrp",
    "mfg_or_pkd_date",
    "manufacturer_or_packer",
    "consumer_care",
    "country_of_origin",
    "barcode",
}


@dataclass(frozen=True)
class Region:
    task_key: tuple[str, str]
    label: str
    x: float
    y: float
    width: float
    height: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Label Studio boxes and score local Paddle predictions.")
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    return parser.parse_args()


def load_list(path: Path, description: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"{description} file was not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{description} is not valid JSON: {path}") from error
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError(f"{description} must be a JSON list of objects: {path}")
    return payload


def task_key(task: dict[str, Any]) -> tuple[str, str] | None:
    data = task.get("data")
    if not isinstance(data, dict):
        return None
    sample_id, filename = data.get("sample_id"), data.get("source_filename")
    if sample_id is None or filename is None:
        return None
    return str(sample_id), str(filename)


def prediction_key(prediction: dict[str, Any]) -> tuple[str, str] | None:
    match = prediction.get("match")
    if not isinstance(match, dict):
        return None
    sample_id, filename = match.get("sample_id"), match.get("source_filename")
    if sample_id is None or filename is None:
        return None
    return str(sample_id), str(filename)


def rectangle_regions(task_key_value: tuple[str, str], result: Iterable[Any], issues: list[dict[str, Any]], source: str) -> list[Region]:
    regions: list[Region] = []
    for index, item in enumerate(result):
        if not isinstance(item, dict) or item.get("type") != "rectanglelabels":
            continue
        value = item.get("value")
        if not isinstance(value, dict):
            issues.append(issue("malformed_value", task_key_value, source, index))
            continue
        labels = value.get("rectanglelabels")
        if not isinstance(labels, list) or len(labels) != 1 or not isinstance(labels[0], str):
            issues.append(issue("invalid_label_payload", task_key_value, source, index))
            continue
        label = labels[0]
        if label not in FIELD_LABELS:
            issues.append(issue("unknown_label", task_key_value, source, index, label=label))
            continue
        try:
            x, y = float(value["x"]), float(value["y"])
            width, height = float(value["width"]), float(value["height"])
        except (KeyError, TypeError, ValueError):
            issues.append(issue("invalid_geometry", task_key_value, source, index, label=label))
            continue
        if not all(math.isfinite(number) for number in (x, y, width, height)) or width <= 0 or height <= 0:
            issues.append(issue("non_positive_geometry", task_key_value, source, index, label=label))
            continue
        if x < 0 or y < 0 or x + width > 100.0001 or y + height > 100.0001:
            issues.append(issue("out_of_bounds", task_key_value, source, index, label=label))
            continue
        regions.append(Region(task_key_value, label, x, y, width, height))
    return regions


def issue(kind: str, task_key_value: tuple[str, str], source: str, index: int, **extra: Any) -> dict[str, Any]:
    return {"kind": kind, "task": list(task_key_value), "source": source, "result_index": index, **extra}


def intersection_over_union(first: Region, second: Region) -> float:
    left = max(first.x, second.x)
    top = max(first.y, second.y)
    right = min(first.x + first.width, second.x + second.width)
    bottom = min(first.y + first.height, second.y + second.height)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    union = first.width * first.height + second.width * second.height - intersection
    return intersection / union if union > 0 else 0.0


def duplicate_regions(regions: list[Region]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    by_task_label: dict[tuple[tuple[str, str], str], list[Region]] = defaultdict(list)
    for region in regions:
        by_task_label[(region.task_key, region.label)].append(region)
    for (key, label), candidates in by_task_label.items():
        for index, first in enumerate(candidates):
            for second in candidates[index + 1 :]:
                overlap = intersection_over_union(first, second)
                if overlap >= 0.98:
                    warnings.append({"kind": "near_duplicate_box", "task": list(key), "label": label, "iou": round(overlap, 4)})
    return warnings


def latest_annotation(task: dict[str, Any]) -> dict[str, Any] | None:
    annotations = task.get("annotations")
    if not isinstance(annotations, list) or not annotations:
        return None
    valid = [annotation for annotation in annotations if isinstance(annotation, dict)]
    return max(valid, key=lambda item: (str(item.get("updated_at", "")), int(item.get("id", 0)))) if valid else None


def collect_ground_truth(tasks: list[dict[str, Any]]) -> tuple[dict[tuple[str, str], list[Region]], dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    regions_by_task: dict[tuple[str, str], list[Region]] = {}
    key_counts: Counter[tuple[str, str]] = Counter()
    annotation_count = 0
    for task in tasks:
        key = task_key(task)
        if key is None:
            issues.append({"kind": "missing_task_key", "source": "ground_truth"})
            continue
        key_counts[key] += 1
        annotations = task.get("annotations")
        if not isinstance(annotations, list) or not annotations:
            issues.append({"kind": "missing_annotation", "task": list(key), "source": "ground_truth"})
            continue
        annotation_count += len(annotations)
        if len(annotations) > 1:
            warnings.append({"kind": "multiple_annotations_using_latest", "task": list(key), "count": len(annotations)})
        annotation = latest_annotation(task)
        result = annotation.get("result", []) if annotation else []
        regions_by_task[key] = rectangle_regions(key, result if isinstance(result, list) else [], issues, "ground_truth")
    for key, count in key_counts.items():
        if count > 1:
            issues.append({"kind": "duplicate_task_key", "task": list(key), "source": "ground_truth", "count": count})
    regions = [region for candidates in regions_by_task.values() for region in candidates]
    warnings.extend(duplicate_regions(regions))
    return regions_by_task, {
        "task_count": len(tasks),
        "annotated_task_count": len(regions_by_task),
        "annotation_count": annotation_count,
        "box_count": len(regions),
        "label_counts": dict(sorted(Counter(region.label for region in regions).items())),
        "errors": issues,
        "warnings": warnings,
    }


def collect_predictions(items: list[dict[str, Any]]) -> tuple[dict[tuple[str, str], list[Region]], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    regions_by_task: dict[tuple[str, str], list[Region]] = {}
    seen: Counter[tuple[str, str]] = Counter()
    for item in items:
        key = prediction_key(item)
        if key is None:
            issues.append({"kind": "missing_task_key", "source": "prediction"})
            continue
        seen[key] += 1
        prediction = item.get("prediction")
        result = prediction.get("result", []) if isinstance(prediction, dict) else []
        regions_by_task[key] = rectangle_regions(key, result if isinstance(result, list) else [], issues, "prediction")
    for key, count in seen.items():
        if count > 1:
            issues.append({"kind": "duplicate_task_key", "task": list(key), "source": "prediction", "count": count})
    return regions_by_task, issues


def score(predictions: dict[tuple[str, str], list[Region]], ground_truth: dict[tuple[str, str], list[Region]], threshold: float) -> dict[str, Any]:
    totals: dict[str, Counter[str]] = defaultdict(Counter)
    per_task: list[dict[str, Any]] = []
    all_keys = sorted(set(predictions) | set(ground_truth))
    for key in all_keys:
        predicted, expected = predictions.get(key, []), ground_truth.get(key, [])
        unmatched_prediction = set(range(len(predicted)))
        matches: list[tuple[int, int, float]] = []
        for truth_index, truth in enumerate(expected):
            choices = [
                (intersection_over_union(truth, predicted[prediction_index]), prediction_index)
                for prediction_index in unmatched_prediction
                if predicted[prediction_index].label == truth.label
            ]
            if choices:
                best_iou, prediction_index = max(choices)
                if best_iou >= threshold:
                    unmatched_prediction.remove(prediction_index)
                    matches.append((truth_index, prediction_index, best_iou))
        matched_truth = {truth_index for truth_index, _, _ in matches}
        for truth_index, _, _ in matches:
            totals[expected[truth_index].label]["tp"] += 1
        for truth_index, truth in enumerate(expected):
            if truth_index not in matched_truth:
                totals[truth.label]["fn"] += 1
        for prediction_index in unmatched_prediction:
            totals[predicted[prediction_index].label]["fp"] += 1
        missing = [expected[index].label for index in range(len(expected)) if index not in matched_truth]
        extra = [predicted[index].label for index in unmatched_prediction]
        if missing or extra:
            per_task.append({"task": list(key), "missing_labels": missing, "extra_labels": extra})
    fields: dict[str, dict[str, Any]] = {}
    aggregate = Counter()
    for label in sorted(FIELD_LABELS):
        counts = totals[label]
        tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
        aggregate.update(counts)
        fields[label] = metric_row(tp, fp, fn)
    return {
        "iou_threshold": threshold,
        "aggregate": metric_row(aggregate["tp"], aggregate["fp"], aggregate["fn"]),
        "fields": fields,
        "tasks_with_mismatch": per_task,
    }


def metric_row(tp: int, fp: int, fn: int) -> dict[str, Any]:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
    }


def markdown_report(report: dict[str, Any]) -> str:
    audit, metrics = report["audit"], report["metrics"]
    lines = [
        "# NiyamDrishti benchmark geometry report",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "## Ground-truth audit",
        "",
        f"- Tasks: {audit['task_count']} (annotated: {audit['annotated_task_count']})",
        f"- Submitted annotations: {audit['annotation_count']}",
        f"- Reviewed statutory-field boxes: {audit['box_count']}",
        f"- Errors: {len(audit['errors'])}; warnings: {len(audit['warnings'])}",
        "",
        "## Local Paddle versus reviewed boxes",
        "",
        f"IoU match threshold: {metrics['iou_threshold']:.2f}. This measures field class and box geometry only; box-first labels are not text-transcription ground truth.",
        "",
        "| Field | TP | FP | FN | Precision | Recall | F1 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in metrics["fields"].items():
        lines.append(
            f"| {label} | {row['true_positive']} | {row['false_positive']} | {row['false_negative']} | "
            f"{format_metric(row['precision'])} | {format_metric(row['recall'])} | {format_metric(row['f1'])} |"
        )
    aggregate = metrics["aggregate"]
    lines.extend(
        [
            "",
            (
                f"Overall: TP {aggregate['true_positive']}, FP {aggregate['false_positive']}, FN {aggregate['false_negative']}; "
                f"precision {format_metric(aggregate['precision'])}, recall {format_metric(aggregate['recall'])}, F1 {format_metric(aggregate['f1'])}."
            ),
            f"Tasks with one or more mismatch: {len(metrics['tasks_with_mismatch'])}.",
            "",
            "The raw benchmark was used to create these labels, so this is a development diagnostic, not an independent holdout result.",
        ]
    )
    return "\n".join(lines) + "\n"


def format_metric(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def write_output(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.with_suffix(".md").write_text(markdown_report(report), encoding="utf-8")


def main() -> None:
    args = parse_args()
    if not 0 < args.iou_threshold <= 1:
        raise SystemExit("--iou-threshold must be greater than 0 and at most 1.")
    truth_tasks = load_list(args.ground_truth, "Ground truth")
    prediction_items = load_list(args.predictions, "Prediction")
    truth, audit = collect_ground_truth(truth_tasks)
    predictions, prediction_issues = collect_predictions(prediction_items)
    metrics = score(predictions, truth, args.iou_threshold)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ground_truth": str(args.ground_truth.resolve()),
        "predictions": str(args.predictions.resolve()),
        "audit": audit,
        "prediction_errors": prediction_issues,
        "metrics": metrics,
    }
    write_output(args.output.resolve(), report)
    print(f"Audit: {audit['task_count']} tasks, {audit['box_count']} reviewed boxes, {len(audit['errors'])} errors, {len(audit['warnings'])} warnings.")
    aggregate = metrics["aggregate"]
    print(f"Paddle @ IoU {args.iou_threshold:.2f}: precision={format_metric(aggregate['precision'])}, recall={format_metric(aggregate['recall'])}, F1={format_metric(aggregate['f1'])}.")
    print(f"Wrote {args.output.resolve()} and {args.output.resolve().with_suffix('.md')}")
    if audit["errors"]:
        raise SystemExit(2)


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        print(f"Benchmark evaluation failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
