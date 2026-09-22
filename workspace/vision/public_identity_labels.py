"""Separate development label contract for public tile identity.

This module intentionally does not reuse the concealed hand/draw/gold label
schema. Public Identity Shadow V0.1 showed that those template domains do not
transfer reliably to public detector crops.

V0.1 is an intake/provenance layer only. It can validate labels, verify source
image hashes, export reviewed crops locally, and report coverage. It never
claims that public identity is runtime-ready.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

from workspace.vision.tiles_v0_1.taxonomy import HONORS, SUITED, category_for


SCHEMA_VERSION = "public_identity_labels_v0_1"
PUBLIC_REGIONS = frozenset({"public_action", "public_single", "public_meld"})
LABEL_STATUSES = frozenset({"approved", "review", "rejected"})
PUBLIC_STANDARD_CLASSES = frozenset(SUITED) | frozenset(HONORS)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _strings(value: Any, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        raise ValueError(f"{name} must be a sequence")
    result = tuple(str(item) for item in value)
    if any(not item for item in result):
        raise ValueError(f"{name} contains an empty value")
    return result


def _normalized_bbox(value: Any) -> tuple[float, float, float, float]:
    try:
        values = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise ValueError("bbox must contain four numeric values") from exc
    if len(values) != 4:
        raise ValueError("bbox must contain x, y, width, height")
    x, y, width, height = values
    if (
        x < 0
        or y < 0
        or width <= 0
        or height <= 0
        or x + width > 1.000001
        or y + height > 1.000001
    ):
        raise ValueError("bbox must be normalized inside the image")
    return values


@dataclass(frozen=True)
class PublicIdentityLabel:
    label_id: str
    source_calibration_sample_id: str
    source_session: str
    source_sha256: str
    image_path: str
    image_sha256: str
    frame_index: int
    time_ms: int
    region: str
    tile_id: str
    bbox: tuple[float, float, float, float]
    status: str = "approved"
    annotator: str = "pixel_review"
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.label_id or not self.source_calibration_sample_id:
            raise ValueError(
                "label_id and source_calibration_sample_id are required"
            )
        if not self.source_session:
            raise ValueError("source_session is required")

        for name in ("source_sha256", "image_sha256"):
            value = str(getattr(self, name)).lower()
            if not _SHA256.fullmatch(value):
                raise ValueError(f"{name} must be a SHA256 hex digest")
            object.__setattr__(self, name, value)

        if not self.image_path or Path(self.image_path).is_absolute():
            raise ValueError(
                "image_path must be a nonempty repository-relative path"
            )
        if (
            isinstance(self.frame_index, bool)
            or not isinstance(self.frame_index, int)
            or self.frame_index < 0
        ):
            raise ValueError("frame_index must be a nonnegative integer")
        if (
            isinstance(self.time_ms, bool)
            or not isinstance(self.time_ms, int)
            or self.time_ms < 0
        ):
            raise ValueError("time_ms must be a nonnegative integer")
        if self.region not in PUBLIC_REGIONS:
            raise ValueError(f"unsupported public identity region: {self.region}")
        if self.tile_id not in PUBLIC_STANDARD_CLASSES:
            # category_for produces the stable project error for malformed IDs.
            category_for(self.tile_id)
            raise ValueError(
                f"public identity V0.1 only accepts 34 standard classes: {self.tile_id}"
            )
        if self.status not in LABEL_STATUSES:
            raise ValueError(f"unsupported label status: {self.status}")
        if not self.annotator:
            raise ValueError("annotator is required")
        object.__setattr__(self, "bbox", _normalized_bbox(self.bbox))
        object.__setattr__(self, "notes", _strings(self.notes, "notes"))


@dataclass(frozen=True)
class PublicIdentityManifest:
    labels: tuple[PublicIdentityLabel, ...]
    excluded_from_formal_promotion: bool
    development_only_reason: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        object.__setattr__(self, "labels", tuple(self.labels))
        ids = [label.label_id for label in self.labels]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate public identity label_id")
        if not self.excluded_from_formal_promotion:
            raise ValueError(
                "reviewed public identity intake must stay excluded from formal promotion"
            )
        if not self.development_only_reason:
            raise ValueError("development_only_reason is required")


def label_from_dict(row: dict[str, Any]) -> PublicIdentityLabel:
    return PublicIdentityLabel(
        label_id=str(row["label_id"]),
        source_calibration_sample_id=str(
            row["source_calibration_sample_id"]
        ),
        source_session=str(row["source_session"]),
        source_sha256=str(row["source_sha256"]),
        image_path=str(row["image_path"]),
        image_sha256=str(row["image_sha256"]),
        frame_index=row["frame_index"],
        time_ms=row["time_ms"],
        region=str(row["region"]),
        tile_id=str(row["tile_id"]),
        bbox=row["bbox"],
        status=str(row.get("status", "approved")),
        annotator=str(row.get("annotator", "pixel_review")),
        notes=tuple(row.get("notes", ())),
    )


def manifest_from_dict(data: dict[str, Any]) -> PublicIdentityManifest:
    return PublicIdentityManifest(
        labels=tuple(
            label_from_dict(row)
            for row in data.get("labels", ())
        ),
        excluded_from_formal_promotion=bool(
            data.get("excluded_from_formal_promotion")
        ),
        development_only_reason=str(
            data.get("development_only_reason", "")
        ),
        schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
    )


def load_public_identity_manifest(
    path: str | Path,
) -> PublicIdentityManifest:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("public identity manifest root must be an object")
    return manifest_from_dict(data)


def approved_labels(
    manifest: PublicIdentityManifest,
) -> tuple[PublicIdentityLabel, ...]:
    return tuple(
        label for label in manifest.labels
        if label.status == "approved"
    )


def readiness_report(
    manifest: PublicIdentityManifest,
) -> dict[str, Any]:
    approved = approved_labels(manifest)
    by_region = Counter(label.region for label in approved)
    classes = {label.tile_id for label in approved}
    sessions_by_region: dict[str, set[str]] = defaultdict(set)
    sessions_by_class: dict[str, set[str]] = defaultdict(set)
    classes_by_region: dict[str, set[str]] = defaultdict(set)

    for label in approved:
        sessions_by_region[label.region].add(label.source_session)
        sessions_by_class[label.tile_id].add(label.source_session)
        classes_by_region[label.region].add(label.tile_id)

    cross_session_classes = sorted(
        tile_id
        for tile_id, sessions in sessions_by_class.items()
        if len(sessions) >= 2
    )
    missing = sorted(PUBLIC_STANDARD_CLASSES - classes)

    return {
        "schema_version": manifest.schema_version,
        "labels_total": len(manifest.labels),
        "approved_labels": len(approved),
        "regions": {
            region: {
                "labels": by_region[region],
                "distinct_classes": len(classes_by_region[region]),
                "source_sessions": len(sessions_by_region[region]),
            }
            for region in sorted(PUBLIC_REGIONS)
        },
        "standard_class_coverage": {
            "covered": len(classes),
            "total": len(PUBLIC_STANDARD_CLASSES),
            "missing": missing,
        },
        "cross_session_classes": cross_session_classes,
        "cross_session_class_count": len(cross_session_classes),
        "runtime_identity_ready": False,
        "runtime_identity_reason": (
            "V0.1 is a development intake schema only; no public-region "
            "classifier/promotion gate is frozen. Keep runtime tile_id UNKNOWN."
        ),
        "formal_promotion_eligible": False,
        "formal_promotion_reason": (
            "already-reviewed development sources; formal Vision promotion "
            "requires a separate untouched source-disjoint batch"
        ),
    }


def verify_repository_files(
    manifest: PublicIdentityManifest,
    repository_root: str | Path,
) -> tuple[str, ...]:
    root = Path(repository_root)
    issues: list[str] = []
    seen_images: dict[str, str] = {}
    for label in manifest.labels:
        path = root / label.image_path
        if not path.is_file():
            issues.append(f"{label.label_id}:missing_file")
            continue
        digest = seen_images.get(label.image_path)
        if digest is None:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            seen_images[label.image_path] = digest
        if digest != label.image_sha256:
            issues.append(f"{label.label_id}:image_sha256_mismatch")
    return tuple(issues)


def validate_against_calibration_rows(
    manifest: PublicIdentityManifest,
    calibration_rows: Iterable[dict[str, Any]],
) -> tuple[str, ...]:
    """Cross-check public labels against detector-calibration provenance."""
    rows = {
        str(row["sample_id"]): row
        for row in calibration_rows
    }
    issues: list[str] = []
    for label in manifest.labels:
        row = rows.get(label.source_calibration_sample_id)
        if row is None:
            issues.append(
                f"{label.label_id}:missing_calibration_sample"
            )
            continue
        expected = {
            "source_session": label.source_session,
            "source_sha256": label.source_sha256,
            "image_path": label.image_path,
            "image_sha256": label.image_sha256,
            "frame_index": label.frame_index,
            "time_ms": label.time_ms,
        }
        for key, value in expected.items():
            if row.get(key) != value:
                issues.append(
                    f"{label.label_id}:calibration_{key}_mismatch"
                )

        if label.region in {"public_action", "public_single"}:
            if row.get("target") != "discard":
                issues.append(
                    f"{label.label_id}:calibration_target_mismatch"
                )
            if row.get("expected_tile") != label.tile_id:
                issues.append(
                    f"{label.label_id}:calibration_expected_tile_mismatch"
                )
        elif label.region == "public_meld":
            if row.get("target") != "meld":
                issues.append(
                    f"{label.label_id}:calibration_target_mismatch"
                )
            expected_tiles = tuple(row.get("expected_tiles") or ())
            if label.tile_id not in expected_tiles:
                issues.append(
                    f"{label.label_id}:calibration_expected_tiles_mismatch"
                )

        try:
            row_bbox = _normalized_bbox(row.get("bbox"))
        except (TypeError, ValueError):
            issues.append(f"{label.label_id}:calibration_bbox_missing")
        else:
            if label.region in {"public_action", "public_single"}:
                if any(
                    abs(first - second) > 1e-6
                    for first, second in zip(label.bbox, row_bbox)
                ):
                    issues.append(
                        f"{label.label_id}:calibration_bbox_mismatch"
                    )
            else:
                # public_meld labels are individual visible face crops nested
                # inside the reviewed exposed-group bbox.
                lx, ly, lw, lh = label.bbox
                rx, ry, rw, rh = row_bbox
                tolerance = 0.005
                if not (
                    lx >= rx - tolerance
                    and ly >= ry - tolerance
                    and lx + lw <= rx + rw + tolerance
                    and ly + lh <= ry + rh + tolerance
                ):
                    issues.append(
                        f"{label.label_id}:calibration_face_outside_group_bbox"
                    )
    return tuple(issues)


def pixel_bbox(
    label: PublicIdentityLabel,
    image_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    width, height = image_size
    if width <= 0 or height <= 0:
        raise ValueError("image_size must be positive")
    x, y, box_width, box_height = label.bbox
    left = max(0, int(round(x * width)))
    top = max(0, int(round(y * height)))
    right = min(width, int(round((x + box_width) * width)))
    bottom = min(height, int(round((y + box_height) * height)))
    if right <= left or bottom <= top:
        raise ValueError(f"empty pixel bbox for {label.label_id}")
    return left, top, right - left, bottom - top


def export_reviewed_crops(
    manifest: PublicIdentityManifest,
    repository_root: str | Path,
    output_root: str | Path,
) -> tuple[Path, ...]:
    """Export approved public-region crops locally with deterministic names.

    PIL is imported lazily so schema/provenance validation remains usable in
    core environments that do not install Vision extras.
    """
    from PIL import Image  # type: ignore

    root = Path(repository_root)
    output = Path(output_root)
    paths: list[Path] = []
    integrity = verify_repository_files(manifest, root)
    if integrity:
        raise ValueError(
            "cannot export crops with source integrity failures: "
            + ", ".join(integrity)
        )

    for label in approved_labels(manifest):
        with Image.open(root / label.image_path) as source:
            image = source.convert("RGB")
            x, y, width, height = pixel_bbox(label, image.size)
            crop = image.crop((x, y, x + width, y + height))

        destination = (
            output
            / label.region
            / label.tile_id
            / f"{label.label_id}.png"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        crop.save(destination)
        paths.append(destination)

    return tuple(paths)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate/export development public identity labels"
    )
    parser.add_argument(
        "--manifest",
        default="references/vision/2026-09-22/public_identity_labels_v0_1.json",
    )
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--export-crops")
    args = parser.parse_args()

    manifest = load_public_identity_manifest(args.manifest)
    report = readiness_report(manifest)
    report["file_integrity_issues"] = list(
        verify_repository_files(manifest, args.repository_root)
    )
    if args.export_crops:
        paths = export_reviewed_crops(
            manifest,
            args.repository_root,
            args.export_crops,
        )
        report["exported_crops"] = len(paths)
        report["export_root"] = str(args.export_crops)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
