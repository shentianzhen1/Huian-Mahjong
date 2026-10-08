"""Export public-meld spatial SIFT references for private offline diagnostics.

This development-only utility serializes *derived* descriptors and normalized
keypoint positions from the repository's reviewed public-meld crops. It does
not export source pixels and does not alter Runtime scoring, thresholds, Hint,
or Executor behavior.

The intended use is to let private exact-source probes reproduce the same
public reference bank as CI without copying repository screenshots into a
private working directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "public_meld_spatial_reference_bank_dev_v0_1"


def export_public_meld_spatial_reference_bank(
    *,
    repository_root: str | Path = ".",
    output_npz: str | Path,
    output_metadata: str | Path,
) -> dict[str, Any]:
    import importlib.metadata
    import cv2
    import numpy as np
    from PIL import Image

    from workspace.vision.evaluate_sift_symmetric_geometry_probe import (
        normalize_single_face,
    )
    from workspace.vision.public_identity_labels import (
        approved_labels,
        load_public_identity_manifest,
        pixel_bbox,
        verify_repository_files,
    )
    from workspace.vision.public_identity_shadow_v0_2 import (
        load_development_sources,
    )
    from workspace.vision.sift_spatial_consistency_probe import PositionedSift

    root = Path(repository_root).resolve()
    label_path = root / "references/vision/2026-09-22/public_identity_labels_v0_1.json"
    source_path = root / "references/vision/2026-09-24/public_identity_source_groups.development.json"
    manifest = load_public_identity_manifest(label_path)
    integrity = verify_repository_files(manifest, root)
    if integrity:
        raise ValueError(
            "public identity source integrity failed: " + ",".join(integrity)
        )
    sources = load_development_sources(source_path)

    probe = PositionedSift(local_window=True)
    arrays: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    for label in approved_labels(manifest):
        if label.region != "public_meld":
            continue
        source = sources.get(label.source_session)
        if source is None or source.source_sha256 != label.source_sha256:
            raise ValueError("public meld label source registry mismatch")
        image_path = (root / label.image_path).resolve()
        if root not in image_path.parents:
            raise ValueError("public meld source path escapes repository root")
        with Image.open(image_path) as original:
            image = original.convert("RGB")
            x, y, width, height = pixel_bbox(label, image.size)
            crop = image.crop((x, y, x + width, y + height))
        normalized, audit = normalize_single_face(crop)
        if normalized is None:
            raise ValueError(f"normalization failed: {label.label_id}")
        descriptors = probe.extract(normalized)
        if descriptors is None:
            raise ValueError(f"SIFT descriptors absent: {label.label_id}")
        from workspace.vision.sift_spatial_consistency_probe import descriptor_key
        positions = probe.positions[descriptor_key(descriptors)]

        index = len(rows)
        descriptor_key_name = f"d_{index:03d}"
        position_key_name = f"p_{index:03d}"
        arrays[descriptor_key_name] = descriptors
        arrays[position_key_name] = positions
        rows.append({
            "index": index,
            "label_id": label.label_id,
            "tile_id": label.tile_id,
            "source_session": label.source_session,
            "source_sha256": label.source_sha256,
            "match_group": source.match_group,
            "image_path": label.image_path,
            "descriptor_key": descriptor_key_name,
            "position_key": position_key_name,
            "descriptor_count": int(len(descriptors)),
            "normalization": audit,
        })

    if not rows:
        raise ValueError("no public meld references exported")

    output_npz = Path(output_npz)
    output_metadata = Path(output_metadata)
    output_npz.parent.mkdir(parents=True, exist_ok=True)
    output_metadata.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_npz, **arrays)

    report = {
        "schema_version": SCHEMA_VERSION,
        "reference_count": len(rows),
        "tile_ids": sorted({row["tile_id"] for row in rows}),
        "rows": rows,
        "input_sha256": {
            str(label_path.relative_to(root)): hashlib.sha256(label_path.read_bytes()).hexdigest(),
            str(source_path.relative_to(root)): hashlib.sha256(source_path.read_bytes()).hexdigest(),
        },
        "npz_sha256": hashlib.sha256(output_npz.read_bytes()).hexdigest(),
        "dependency_versions": {
            "opencv_cv2": cv2.__version__,
            "opencv_python_headless_distribution": importlib.metadata.version(
                "opencv-python-headless"
            ),
            "numpy": np.__version__,
        },
        "descriptor_extractor": "PositionedSift.extract",
        "symmetric_single_face_normalization": True,
        "local_window_radius": 0.2,
        "source_pixels_exported": False,
        "development_only": True,
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }
    output_metadata.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--output-npz", required=True)
    parser.add_argument("--output-metadata", required=True)
    args = parser.parse_args()
    report = export_public_meld_spatial_reference_bank(
        repository_root=args.repository_root,
        output_npz=args.output_npz,
        output_metadata=args.output_metadata,
    )
    print(json.dumps({
        "reference_count": report["reference_count"],
        "tile_ids": report["tile_ids"],
        "npz_sha256": report["npz_sha256"],
        "dependency_versions": report["dependency_versions"],
        "source_pixels_exported": report["source_pixels_exported"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
