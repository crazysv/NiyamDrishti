"""Create a transparent, non-destructive Round-1 supplemental-image split.

Original images in test_data/supplemental_raw are never renamed, moved, or
deleted. Review copies are made under supplemental_round1/eligible and
supplemental_round1/excluded, accompanied by a JSON manifest that records the
source, dimensions, SHA-256, and reason for every decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "test_data" / "supplemental_raw"
DEFAULT_OUTPUT = ROOT / "test_data" / "supplemental_round1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_name(destination: Path, source: Path) -> Path:
    candidate = destination / source.name
    if not candidate.exists():
        return candidate
    return destination / f"{source.stem}__{sha256(source)[:10]}{source.suffix.lower()}"


def image_record(path: Path) -> dict[str, object]:
    with Image.open(path) as image:
        width, height = image.size
        image.verify()
    return {
        "source": str(path.relative_to(ROOT)).replace("\\", "/"),
        "filename": path.name,
        "width": width,
        "height": height,
        "short_side": min(width, height),
        "sha256": sha256(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-short-side", type=int, default=600)
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    if not source.is_dir():
        raise SystemExit(f"Source directory does not exist: {source}")
    if args.min_short_side < 1:
        raise SystemExit("--min-short-side must be positive")

    records: list[dict[str, object]] = []
    unreadable: list[dict[str, object]] = []
    for path in sorted(item for item in source.iterdir() if item.is_file()):
        try:
            records.append(image_record(path))
        except Exception as error:  # Manifest preserves failures for review.
            unreadable.append({
                "source": str(path.relative_to(ROOT)).replace("\\", "/"),
                "filename": path.name,
                "decision": "excluded",
                "reason": "unreadable_image",
                "error": str(error),
            })

    by_hash: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        by_hash[str(record["sha256"])].append(record)

    eligible_dir = output / "eligible"
    excluded_dir = output / "excluded"
    if output.exists():
        raise SystemExit(
            f"Refusing to overwrite existing output: {output}. "
            "Choose a different --output path after reviewing it."
        )
    eligible_dir.mkdir(parents=True)
    excluded_dir.mkdir(parents=True)

    selected = excluded = 0
    for digest, group in sorted(by_hash.items()):
        qualifying = [record for record in group if int(record["short_side"]) >= args.min_short_side]
        canonical = qualifying[0] if qualifying else None
        for record in group:
            source_path = ROOT / str(record["source"])
            if canonical is not None and record is canonical:
                record["decision"] = "eligible"
                record["reason"] = "meets_round1_quality_gate"
                destination = copy_name(eligible_dir, source_path)
                selected += 1
            elif int(record["short_side"]) < args.min_short_side:
                record["decision"] = "excluded"
                record["reason"] = f"short_side_under_{args.min_short_side}px"
                destination = copy_name(excluded_dir, source_path)
                excluded += 1
            else:
                record["decision"] = "excluded"
                record["reason"] = "exact_duplicate"
                record["duplicate_of"] = canonical["source"] if canonical else group[0]["source"]
                destination = copy_name(excluded_dir, source_path)
                excluded += 1
            shutil.copy2(source_path, destination)
            record["round1_copy"] = str(destination.relative_to(ROOT)).replace("\\", "/")

    for record in unreadable:
        source_path = ROOT / str(record["source"])
        destination = copy_name(excluded_dir, source_path)
        shutil.copy2(source_path, destination)
        record["round1_copy"] = str(destination.relative_to(ROOT)).replace("\\", "/")

    manifest = {
        "source": str(source.relative_to(ROOT)).replace("\\", "/"),
        "policy": {
            "originals_untouched": True,
            "min_short_side_px": args.min_short_side,
            "duplicate_rule": "Only byte-identical files are deduplicated; visually similar images are retained.",
        },
        "summary": {
            "source_files": len(records) + len(unreadable),
            "eligible": selected,
            "excluded": excluded + len(unreadable),
            "unreadable": len(unreadable),
        },
        "records": sorted(records + unreadable, key=lambda item: str(item["source"])),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["summary"], indent=2))
    print(f"Eligible copies: {eligible_dir}")
    print(f"Excluded copies: {excluded_dir}")
    print(f"Manifest: {output / 'manifest.json'}")


if __name__ == "__main__":
    main()
