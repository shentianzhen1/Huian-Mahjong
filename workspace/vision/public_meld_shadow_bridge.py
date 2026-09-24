"""Issue #69: source-verified development bridge from public meld geometry
to independent per-face identity SHADOW proposals. Never an action or runtime
prediction. Only use reviewed screenshots and original-match-separated labels.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
from pathlib import Path
from typing import Any

from workspace.vision.public_detector_calibration import (
    CalibrationSample, load_manifest,
)
from workspace.vision.public_identity_labels import (
    PublicIdentityManifest, load_public_identity_manifest,
    validate_against_calibration_rows,
)
from workspace.vision.public_identity_shadow_v0_2 import (
    ShadowBank, build_shadow_bank, propose_shadow_identity,
)
from workspace.vision.public_meld_face_segmentation import (
    segment_regular_meld_faces,
)
from workspace.vision.public_tile_detector import (
    PublicGeometryCandidate, PublicGeometryFrame,
    detect_public_tile_geometry, target_coverage,
)


@dataclass(frozen=True)
class ShadowMeldFace:
    face_index: int
    normalized_bbox: tuple[float, float, float, float]
    shadow_proposal: str | None
    reason: str
    eligible_class_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "face_index": self.face_index,
            "normalized_bbox": list(self.normalized_bbox),
            "tile_id": "UNKNOWN",
            "evidence_grade": "UNKNOWN",
            "shadow_proposal": self.shadow_proposal,
            "shadow_reason": self.reason,
            "eligible_class_count": self.eligible_class_count,
            "safe_for_runtime_identity": False,
        }


@dataclass(frozen=True)
class ShadowMeldProbe:
    sample_id: str
    frame_index: int
    group_bbox: tuple[float, float, float, float] | None
    faces: tuple[ShadowMeldFace, ...]
    issues: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "public_meld_shadow_bridge_development_v0_1",
            "development_only": True,
            "sample_id": self.sample_id,
            "frame_index": self.frame_index,
            "group_bbox": list(self.group_bbox) if self.group_bbox else None,
            "faces": [face.to_dict() for face in self.faces],
            "issues": list(self.issues),
            "actor": "UNKNOWN",
            "turn_actor": "UNKNOWN",
            "action_kind": "UNKNOWN",
            "tile_ids": ["UNKNOWN"] * len(self.faces),
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
        }


def select_reviewed_group(
    detection: PublicGeometryFrame,
    reviewed_bbox: tuple[float, float, float, float],
) -> tuple[PublicGeometryCandidate | None, tuple[str, ...]]:
    """No nearest-neighbor guess when zero or multiple bottom groups overlap."""
    qualified: list[PublicGeometryCandidate] = []
    for candidate in detection.candidates:
        if candidate.geometry_kind != "bottom_group":
            continue
        intersection = (
            target_coverage(candidate.normalized_bbox, reviewed_bbox)
            * reviewed_bbox[2] * reviewed_bbox[3]
        )
        candidate_area = candidate.normalized_bbox[2] * candidate.normalized_bbox[3]
        if (
            target_coverage(candidate.normalized_bbox, reviewed_bbox) >= 0.90
            and candidate_area > 0
            and intersection / candidate_area >= 0.60
        ):
            qualified.append(candidate)
    if len(qualified) == 1:
        return qualified[0], ()
    if qualified:
        return None, ("ambiguous_overlapping_meld_groups",)
    return None, ("reviewed_meld_group_not_detected",)


def probe_reviewed_meld_shadow(
    sample: CalibrationSample,
    repository_root: str | Path,
    bank: ShadowBank,
) -> ShadowMeldProbe:
    """Actual detector -> 3-face segmenter -> PR #110 shadow classifier.

    Calibration group bbox is *human reviewed* and used only to select the
    matching geometry on already-inspected development screenshots. Approved
    individual face labels and expected tiles NEVER enter this function.
    """
    from PIL import Image

    if sample.target != "meld" or sample.status != "bbox_reviewed" or not sample.bbox:
        raise ValueError("only previously reviewed source-scoped meld bboxes")
    source = bank.sources.get(sample.source_session)
    if source is None or source.source_sha256 != sample.source_sha256:
        raise ValueError("source session/SHA is not locked in shadow bank")

    root = Path(repository_root).resolve()
    relative = Path(sample.image_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("reviewed image path must stay inside repository")
    image_path = (root / relative).resolve()
    if root not in image_path.parents:
        raise ValueError("reviewed image path escapes repository")
    content = image_path.read_bytes()
    if hashlib.sha256(content).hexdigest() != sample.image_sha256:
        raise ValueError("reviewed source image SHA256 mismatch")

    with Image.open(BytesIO(content)) as img:
        image = img.convert("RGB")
    detection = detect_public_tile_geometry(
        image, frame=sample.frame_index, session=sample.source_session
    )
    if detection.frame != sample.frame_index or detection.session != sample.source_session:
        raise ValueError("detector provenance does not match reviewed sample")

    group, issues = select_reviewed_group(detection, sample.bbox)
    if group is None:
        return ShadowMeldProbe(sample.sample_id, sample.frame_index, None, (), issues)
    segmentation = segment_regular_meld_faces(group, image.size)
    if len(segmentation.faces) != 3:
        return ShadowMeldProbe(
            sample.sample_id, sample.frame_index,
            group.normalized_bbox, (), segmentation.issues
        )

    faces: list[ShadowMeldFace] = []
    for face in segmentation.faces:
        x, y, width, height = face.pixel_bbox
        result = propose_shadow_identity(
            bank,
            image.crop((x, y, x + width, y + height)),
            region="public_meld",
            source_session=sample.source_session,
            source_sha256=sample.source_sha256,
        )
        # Future classifier revisions cannot silently promote a shadow result
        # into a live ID/evidence/action even if they change their output API.
        if (
            result.get("tile_id") != "UNKNOWN"
            or result.get("evidence_grade") != "UNKNOWN"
            or result.get("safe_for_runtime") is not False
            or result.get("safe_for_executor") is not False
            or result.get("formal_promotion_evidence") is not False
        ):
            raise ValueError("unsafe shadow classifier output")
        faces.append(ShadowMeldFace(
            face.face_index, face.normalized_bbox,
            result.get("shadow_proposal"),
            str(result.get("reason", "UNKNOWN")),
            int(result.get("eligible_class_count", 0)),
        ))
    return ShadowMeldProbe(
        sample.sample_id, sample.frame_index,
        group.normalized_bbox, tuple(faces), segmentation.issues,
    )


def audit_reviewed_meld_shadow(
    repository_root: str | Path,
    calibration_path: str | Path,
    identity_path: str | Path,
    registry_path: str | Path,
) -> dict[str, Any]:
    """Score 4 reviewed ordinary groups + negative stacked-Kong group.

    Approved truth is inspected AFTER predictions and is never allowed into
    segmentation or shadow-identity inference. This is development regression
    only, not a new blind accuracy figure.
    """
    from workspace.vision.public_identity_labels import (
        approved_labels, verify_repository_files,
    )

    calibration = load_manifest(calibration_path)
    manifest: PublicIdentityManifest = load_public_identity_manifest(identity_path)
    if not calibration.excluded_from_formal_promotion:
        raise ValueError("reviewed calibration cannot be formal promotion evidence")
    issues = validate_against_calibration_rows(
        manifest, [vars(sample) for sample in calibration.samples]
    )
    # Public calibration rows and public identity labels have equivalent
    # dataclass field types for the legacy expected-tile/source checks.
    if issues:
        raise ValueError("reviewed public-face label provenance: " + ",".join(issues))
    if verify_repository_files(manifest, repository_root):
        raise ValueError("approved public-face source integrity failed")
    bank = build_shadow_bank(manifest, repository_root, registry_path)
    expected_by_sample: dict[str, list[Any]] = {}
    for label in approved_labels(manifest):
        if label.region == "public_meld":
            expected_by_sample.setdefault(label.source_calibration_sample_id, []).append(label)

    rows = [sample for sample in calibration.samples if sample.target == "meld"]
    checked: list[dict[str, Any]] = []
    covered = 0
    approved_total = 0
    rejected_stack = 0
    proposals = 0
    face_count = 0
    for sample in rows:
        result = probe_reviewed_meld_shadow(sample, repository_root, bank)
        labels = sorted(
            expected_by_sample.get(sample.sample_id, []),
            key=lambda label: label.bbox[0],
        )
        approved_total += len(labels)
        face_count += len(result.faces)
        proposals += sum(face.shadow_proposal is not None for face in result.faces)
        for face, label in zip(result.faces, labels):
            if target_coverage(face.normalized_bbox, label.bbox) >= 0.80:
                covered += 1
        if len(sample.expected_tiles) == 4 and not result.faces:
            rejected_stack += 1
        checked.append({
            "sample_id": sample.sample_id,
            "face_count": len(result.faces),
            "shadow_proposals": sum(
                face.shadow_proposal is not None for face in result.faces
            ),
            "issues": list(result.issues),
        })
    return {
        "schema_version": "public_meld_shadow_bridge_audit_v0_1",
        "development_only": True,
        "reviewed_group_count": len(checked),
        "reviewed_approved_face_count": approved_total,
        "geometry_face_count": face_count,
        "approved_faces_covered_80pct": covered,
        "stacked_kong_groups_abstained": rejected_stack,
        "shadow_proposals": proposals,
        "shadow_abstentions": face_count - proposals,
        "proposal_accuracy": None if proposals == 0 else "not_scored_in_bridge",
        "source_disjoint_holdout": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_executor": False,
        "samples": checked,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--calibration", default=(
            "references/vision/2026-09-22/public_detector_calibration_v0_1.json"
        )
    )
    parser.add_argument(
        "--identity", default=(
            "references/vision/2026-09-22/public_identity_labels_v0_1.json"
        )
    )
    parser.add_argument(
        "--registry", default=(
            "references/vision/2026-09-24/public_identity_source_groups.development.json"
        )
    )
    args = parser.parse_args()
    print(json.dumps(audit_reviewed_meld_shadow(
        args.root, args.calibration, args.identity, args.registry
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
