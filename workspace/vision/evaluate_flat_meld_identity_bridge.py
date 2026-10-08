"""Reproduce the inspected seven-group FLAT bridge diagnostic; never promote."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def evaluate_flat_bridge(repository_root: str | Path = ".") -> dict:
    from PIL import Image
    from workspace.vision.public_identity_labels import load_public_identity_manifest
    from workspace.vision.public_identity_shadow_v0_2 import build_shadow_bank
    from workspace.vision.public_meld_identity_bridge import classify_public_meld_group
    from workspace.vision.public_meld_synthetic_transfer import _regular_player_meld_samples, _pixel_bbox
    from workspace.vision.public_tile_detector import PublicGeometryCandidate

    root = Path(repository_root).resolve()
    bank = build_shadow_bank(
        load_public_identity_manifest(root / "references/vision/2026-09-22/public_identity_labels_v0_1.json"),
        root, root / "references/vision/2026-09-24/public_identity_source_groups.development.json",
    )
    calibration = json.loads((root / "references/vision/2026-09-22/public_detector_calibration_v0_1.json").read_text())
    rows = []
    reasons = Counter()
    for sample in _regular_player_meld_samples(calibration):
        image_path = (root / sample["image_path"]).resolve()
        if root not in image_path.parents:
            raise ValueError("query path escapes repository")
        if hashlib.sha256(image_path.read_bytes()).hexdigest() != sample["image_sha256"]:
            raise ValueError("reviewed query image SHA mismatch")
        source = bank.sources.get(sample["source_session"])
        if source is None or source.source_sha256 != sample["source_sha256"]:
            raise ValueError("query source registry conflict")
        with Image.open(image_path) as original:
            image = original.convert("RGB")
        group = PublicGeometryCandidate(
            pixel_bbox=_pixel_bbox(sample["bbox"], image.size),
            normalized_bbox=tuple(sample["bbox"]), geometry_kind="bottom_group",
            confidence=1., fill_ratio=1., frame=sample.get("frame_index"),
            session=sample["source_session"],
        )
        result = classify_public_meld_group(
            image, group, bank=bank, source_session=sample["source_session"],
            source_sha256=sample["source_sha256"],
        )
        support = {}
        for tile in sorted(set(sample["expected_tiles"])):
            other_groups = {
                template.match_group for template in bank.templates
                if template.region == "public_meld" and template.tile_id == tile
                and template.match_group != source.match_group
                and template.source_sha256 != source.source_sha256
            }
            support[tile] = len(other_groups)
        face_reasons = [face.get("reason", "UNKNOWN") for face in result.face_results]
        reasons.update(face_reasons)
        rows.append({
            "sample_id": sample["sample_id"], "expected_tiles": sample["expected_tiles"],
            "query_match_group": source.match_group,
            "expected_class_other_original_match_support": support,
            "expected_group_all_classes_supported": all(count >= 2 for count in support.values()),
            "geometry": result.prepared.geometry.stack_state,
            "split_count": len(result.prepared.face_images),
            "tile_ids": list(result.tile_ids), "trusted": result.trusted_for_read_only_runtime,
            "face_reasons": face_reasons, "issues": list(result.issues),
        })
    return {
        "schema_version": "issue69_flat_group_identity_gate_probe_dev_v0_2",
        "bank_scope": "tracked public shadow bank; private SIFT supplements are not this classifier",
        "group_count": len(rows), "face_observations": sum(row["split_count"] for row in rows),
        "trusted_groups": sum(row["trusted"] for row in rows),
        "expected_groups_with_complete_class_support": sum(row["expected_group_all_classes_supported"] for row in rows),
        "face_failure_reasons": dict(sorted(reasons.items())), "rows": rows,
        "query_image_hashes_verified": True, "query_sources_verified": True,
        "crop_boundary_accuracy_measured": False,
        "previously_inspected": True, "blind_validation": False,
        "classifier_or_threshold_changed": False, "development_only": True,
        "formal_promotion_evidence": False, "safe_for_executor": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = evaluate_flat_bridge(args.repository_root)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}))


if __name__ == "__main__":
    main()
