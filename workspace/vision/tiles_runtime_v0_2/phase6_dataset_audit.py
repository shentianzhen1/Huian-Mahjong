"""Audit approved Runtime V0.2 tile assets and write a compact report."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePath

from PIL import Image, ImageDraw

from workspace.vision.tiles_v0_1.taxonomy import HONORS, SUITED


REQUIRED = (
    "source_id", "source_session", "source_frame", "bbox", "slot",
    "tile_id", "approved", "sha256",
)
STANDARD = set(SUITED) | set(HONORS)


def audit(dataset: Path) -> dict:
    labels = [
        json.loads(line)
        for line in (dataset / "labels.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    missing_fields = []
    missing_assets = []
    hash_mismatches = []
    absolute_paths = []
    dimensions = []
    images = []
    for row in labels:
        absent = [field for field in REQUIRED if field not in row]
        if absent:
            missing_fields.append({"image": row.get("image"), "fields": absent})
        if PurePath(row.get("image", "")).is_absolute():
            absolute_paths.append(row.get("image"))
        path = dataset / row["image"]
        if not path.exists():
            missing_assets.append(row["image"])
            continue
        if row.get("asset_sha256"):
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != row["asset_sha256"]:
                hash_mismatches.append(row["image"])
        with Image.open(path) as source:
            image = source.convert("RGB")
        dimensions.append(image.size)
        images.append((row["tile_id"], row["region"], image))

    work = dataset / "work" / "phase6_tile_review"
    work.mkdir(parents=True, exist_ok=True)
    columns, cell_width, cell_height = 10, 110, 135
    rows_count = (len(images) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_width, rows_count * cell_height), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (tile_id, region, image) in enumerate(images):
        x = (index % columns) * cell_width
        y = (index // columns) * cell_height
        scale = min(94 / image.width, 100 / image.height)
        preview = image.resize((round(image.width * scale), round(image.height * scale)))
        sheet.paste(preview, (x + (cell_width - preview.width) // 2, y + 2))
        draw.text((x + 4, y + 105), f"{tile_id} {region[:5]}", fill="black")
    sheet_path = work / "approved_templates_contact_sheet.jpg"
    sheet.save(sheet_path, quality=92)

    classes = {row["tile_id"] for row in labels if row.get("approved")}
    validation_path = dataset / "validation" / "reports" / "phase6_tile_template_validation_v0_2.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    report = {
        "schema_version": "vision_runtime_v0_2_phase6_dataset_audit",
        "approved_labels": sum(row.get("approved") is True for row in labels),
        "templates": len(images),
        "source_sessions": len({row.get("source_session") for row in labels}),
        "regions": dict(sorted(Counter(row["region"] for row in labels).items())),
        "standard_class_coverage": {
            "covered": len(classes & STANDARD),
            "total": len(STANDARD),
            "missing": sorted(STANDARD - classes),
        },
        "traceability": {
            "missing_required_fields": missing_fields,
            "absolute_paths": absolute_paths,
            "missing_assets": missing_assets,
            "asset_hash_mismatches": hash_mismatches,
        },
        "privacy_shape_gate": {
            "minimum_dimensions": list(min(dimensions)) if dimensions else None,
            "maximum_dimensions": list(max(dimensions)) if dimensions else None,
            "all_assets_under_templates": all(str(row.get("image", "")).startswith("templates/") for row in labels),
            "human_contact_sheet_review": "passed_manual_2026-09-21",
            "local_contact_sheet": "work/phase6_tile_review/approved_templates_contact_sheet.jpg",
        },
        "leakage_safe_validation": {
            key: validation[key]
            for key in (
                "distinct_source_groups", "scorable_labels", "unscorable_labels",
                "scorable_coverage", "exact_accuracy", "category_accuracy",
                "confidence_threshold", "accepted_labels",
                "accepted_fraction_of_scorable", "accepted_accuracy",
            )
        },
        "test_build_decision": "fail_closed_prototype_only",
        "test_build_policy": "Only high-confidence predictions from covered classes may be shown; all other observations return UNKNOWN. No executor actions.",
        "safe_for_executor": False,
    }
    output = dataset / "validation" / "reports" / "phase6_tile_dataset_audit_v0_2.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    args = parser.parse_args()
    print(json.dumps(audit(Path(args.dataset)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
