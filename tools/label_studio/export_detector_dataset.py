"""Export reviewed Label Studio field boxes as a product-disjoint COCO dataset.

Images remain in test_data/benchmark_raw; only manifests are written. This is
training preparation, never a product-data or Label Studio mutation.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LABELS = ["product_name", "net_quantity", "mrp", "mfg_or_pkd_date", "manufacturer_or_packer", "consumer_care", "country_of_origin", "barcode"]

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", type=Path, default=ROOT / "test_data/label_studio/exports/ground_truth_v1.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "test_data/detector_dataset")
    parser.add_argument("--validation-products", type=int, default=8)
    args = parser.parse_args()
    tasks = json.loads(args.ground_truth.read_text(encoding="utf-8"))
    products = sorted({str(task["data"]["sample_id"]) for task in tasks})
    if not 1 <= args.validation_products < len(products): raise ValueError("validation product count must be between 1 and product count - 1")
    validation = {name for _, name in sorted((hashlib.sha256(name.encode()).hexdigest(), name) for name in products)[:args.validation_products]}
    categories = [{"id": index + 1, "name": label} for index, label in enumerate(LABELS)]
    category_id = {row["name"]: row["id"] for row in categories}
    output = {"train": {"images": [], "annotations": [], "categories": categories}, "validation": {"images": [], "annotations": [], "categories": categories}}
    image_id = annotation_id = 1
    for task in tasks:
        data, annotation = task.get("data", {}), (task.get("annotations") or [])[-1]
        product, filename = str(data["sample_id"]), str(data["source_filename"])
        result = annotation.get("result", [])
        rectangles = [item for item in result if item.get("type") == "rectanglelabels" and item.get("value", {}).get("rectanglelabels", [None])[0] in category_id]
        if not rectangles: continue
        width, height = int(rectangles[0]["original_width"]), int(rectangles[0]["original_height"])
        split = "validation" if product in validation else "train"
        output[split]["images"].append({"id": image_id, "file_name": f"{product}/{filename}", "width": width, "height": height, "product_id": product})
        for item in rectangles:
            value, label = item["value"], item["value"]["rectanglelabels"][0]
            x, y, w, h = width * float(value["x"]) / 100, height * float(value["y"]) / 100, width * float(value["width"]) / 100, height * float(value["height"]) / 100
            output[split]["annotations"].append({"id": annotation_id, "image_id": image_id, "category_id": category_id[label], "bbox": [x, y, w, h], "area": w * h, "iscrowd": 0})
            annotation_id += 1
        image_id += 1
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for split, payload in output.items(): (args.output_dir / f"{split}.coco.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    manifest = {"raw_image_root": str(ROOT / "test_data/benchmark_raw"), "train_products": sorted(set(products)-validation), "validation_products": sorted(validation), "categories": LABELS, "note": "Development-only product-disjoint split; the four separate unlabeled holdout products remain excluded."}
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(output['train']['images'])} train and {len(output['validation']['images'])} validation images; held out {len(validation)} products.")
if __name__ == "__main__": main()
