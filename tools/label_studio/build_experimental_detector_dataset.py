"""Package a deliberately isolated trusted-plus-pseudo detector experiment.

The package is not ground truth. It carries provenance for every image and
annotation, and leaves the existing detector dataset/checkpoints untouched.
"""
from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
TRUSTED_ROOT = ROOT / "test_data" / "detector_dataset"
RAW_ROOT = ROOT / "test_data" / "benchmark_raw"
PSEUDO_ROOT = ROOT / "test_data" / "supplemental_round1" / "pseudo_labels_v1" / "records"
OUTPUT_DEFAULT = ROOT / "test_data" / "experimental_detector_v1"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def copy_into(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build isolated trusted-plus-pseudo COCO experiment.")
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing experimental package: {output}")

    trusted_train = load_json(TRUSTED_ROOT / "train.coco.json")
    trusted_validation = load_json(TRUSTED_ROOT / "validation.coco.json")
    categories = trusted_train["categories"]
    category_ids = {item["name"]: item["id"] for item in categories}
    output.mkdir(parents=True)

    train_images: list[dict[str, Any]] = []
    train_annotations: list[dict[str, Any]] = []
    validation_images: list[dict[str, Any]] = []
    validation_annotations: list[dict[str, Any]] = []
    next_image_id, next_annotation_id = 1, 1

    trusted_annotations: dict[int, list[dict[str, Any]]] = {}
    for annotation in trusted_train["annotations"]:
        trusted_annotations.setdefault(annotation["image_id"], []).append(annotation)
    for source_meta in trusted_train["images"]:
        source = RAW_ROOT / source_meta["file_name"]
        target_name = f"images/trusted/{source_meta['file_name']}"
        copy_into(source, output / target_name)
        image_id = next_image_id
        next_image_id += 1
        train_images.append({
            "id": image_id, "file_name": target_name, "width": source_meta["width"], "height": source_meta["height"],
            "product_id": source_meta["product_id"], "provenance": "trusted",
        })
        for annotation in trusted_annotations.get(source_meta["id"], []):
            train_annotations.append({
                "id": next_annotation_id, "image_id": image_id, "category_id": annotation["category_id"],
                "bbox": annotation["bbox"], "area": annotation["area"], "iscrowd": 0, "provenance": "trusted",
            })
            next_annotation_id += 1

    pseudo_counts: Counter[str] = Counter()
    pseudo_images = 0
    for record_path in sorted(PSEUDO_ROOT.glob("*.json")):
        record = load_json(record_path)
        candidates = record["accepted_candidates"]
        if not candidates:
            continue
        source = ROOT / record["source_image"]
        # Raw records are uniquely named by the original downloaded filename.
        target_name = f"images/pseudo/{source.name}"
        copy_into(source, output / target_name)
        image_id = next_image_id
        next_image_id += 1
        pseudo_images += 1
        dimensions = record["source_dimensions"]
        train_images.append({
            "id": image_id, "file_name": target_name, "width": dimensions["width"], "height": dimensions["height"],
            "product_id": f"pseudo_{source.stem}", "provenance": "pseudo_candidate",
            "source_record": str(record_path.relative_to(ROOT)).replace("\\", "/"),
        })
        for candidate in candidates:
            label = candidate["label"]
            box = candidate["bounding_box"]
            train_annotations.append({
                "id": next_annotation_id, "image_id": image_id, "category_id": category_ids[label],
                "bbox": [box["x"], box["y"], box["w"], box["h"]], "area": round(box["w"] * box["h"], 2),
                "iscrowd": 0, "provenance": "pseudo_candidate", "candidate_reason": candidate["reason"],
                "detector_corroborated": candidate["detector_corroboration"] is not None,
            })
            next_annotation_id += 1
            pseudo_counts[label] += 1

    validation_by_image: dict[int, list[dict[str, Any]]] = {}
    for annotation in trusted_validation["annotations"]:
        validation_by_image.setdefault(annotation["image_id"], []).append(annotation)
    for source_meta in trusted_validation["images"]:
        source = RAW_ROOT / source_meta["file_name"]
        target_name = f"images/validation/{source_meta['file_name']}"
        copy_into(source, output / target_name)
        image_id = next_image_id
        next_image_id += 1
        validation_images.append({
            "id": image_id, "file_name": target_name, "width": source_meta["width"], "height": source_meta["height"],
            "product_id": source_meta["product_id"], "provenance": "trusted_frozen_validation",
        })
        for annotation in validation_by_image.get(source_meta["id"], []):
            validation_annotations.append({
                "id": len(validation_annotations) + 1, "image_id": image_id, "category_id": annotation["category_id"],
                "bbox": annotation["bbox"], "area": annotation["area"], "iscrowd": 0, "provenance": "trusted_frozen_validation",
            })

    for name, images, annotations in (
        ("train.coco.json", train_images, train_annotations),
        ("validation.coco.json", validation_images, validation_annotations),
    ):
        (output / name).write_text(json.dumps({"images": images, "annotations": annotations, "categories": categories}, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "purpose": "isolated_noisy_pseudolabel_ablation_not_production_training_data",
        "trusted_training_images": len(trusted_train["images"]),
        "trusted_training_boxes": len(trusted_train["annotations"]),
        "pseudo_candidate_images": pseudo_images,
        "pseudo_candidate_boxes": dict(sorted(pseudo_counts.items())),
        "frozen_validation_images": len(validation_images),
        "frozen_validation_boxes": len(validation_annotations),
        "warnings": [
            "Pseudo annotations are partial and known-noisy; this is an explicit user-authorized experiment.",
            "Never replace the trusted-only checkpoint unless frozen validation improves materially.",
            "The package contains copies only. Original photos and existing datasets remain untouched.",
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    archive = shutil.make_archive(str(output), "zip", root_dir=output)
    print(json.dumps({**manifest, "archive": archive}, indent=2))


if __name__ == "__main__":
    main()
