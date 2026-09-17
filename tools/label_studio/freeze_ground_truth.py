"""Freeze reviewed Label Studio annotations into a private benchmark export.

The export is deliberately kept outside Git because it contains private package
photos and reviewer-produced ground truth. It is an immutable input to local
benchmark evaluation, never an inspection result or a training upload.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "test_data" / "label_studio" / "exports" / "ground_truth_v1.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze reviewed Label Studio ground truth locally.")
    parser.add_argument("--label-studio-url", default="http://localhost:8080")
    parser.add_argument("--project-id", type=int, default=1)
    parser.add_argument("--api-token", default=os.getenv("LABEL_STUDIO_API_TOKEN"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--expected-task-count", type=int, default=92)
    parser.add_argument(
        "--allow-unannotated",
        action="store_true",
        help="Permit a task without a submitted annotation. The default protects a completed benchmark.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing frozen export intentionally.")
    return parser.parse_args()


def fetch_export(base_url: str, project_id: int, token: str) -> list[dict[str, Any]]:
    response = requests.get(
        f"{base_url.rstrip('/')}/api/projects/{project_id}/export",
        params={"exportType": "JSON"},
        headers={"Authorization": f"Token {token}"},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise TypeError("Label Studio export is not a task list; refusing to freeze it.")
    if not all(isinstance(task, dict) for task in payload):
        raise ValueError("Label Studio export contains a non-object task; refusing to freeze it.")
    return payload


def validate_completed_export(tasks: list[dict[str, Any]], expected_count: int, allow_unannotated: bool) -> None:
    if len(tasks) != expected_count:
        raise ValueError(f"Expected {expected_count} benchmark tasks, received {len(tasks)}. Nothing was written.")
    duplicate_ids = len({task.get("id") for task in tasks}) != len(tasks)
    if duplicate_ids:
        raise ValueError("Export contains duplicate task IDs. Nothing was written.")
    if allow_unannotated:
        return
    missing = [task.get("id") for task in tasks if not task.get("annotations")]
    if missing:
        preview = ", ".join(map(str, missing[:10]))
        raise ValueError(f"{len(missing)} task(s) lack submitted annotations ({preview}). Nothing was written.")


def write_json_atomically(path: Path, payload: list[dict[str, Any]], overwrite: bool) -> str:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Frozen export already exists: {path}. Use --overwrite only for an intentional re-freeze.")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encoded)
    temporary.replace(path)
    return hashlib.sha256(encoded).hexdigest()


def main() -> None:
    args = parse_args()
    if not args.api_token:
        raise SystemExit("Set LABEL_STUDIO_API_TOKEN or pass --api-token. The token is used only for the local export request.")
    tasks = fetch_export(args.label_studio_url, args.project_id, args.api_token)
    validate_completed_export(tasks, args.expected_task_count, args.allow_unannotated)
    digest = write_json_atomically(args.output.resolve(), tasks, args.overwrite)
    annotation_count = sum(len(task.get("annotations") or []) for task in tasks)
    print(f"Frozen {len(tasks)} tasks and {annotation_count} annotations: {args.output.resolve()}")
    print(f"SHA256 {digest}")


if __name__ == "__main__":
    try:
        main()
    except (requests.RequestException, TypeError, ValueError, FileExistsError) as error:
        print(f"Ground-truth freeze failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
