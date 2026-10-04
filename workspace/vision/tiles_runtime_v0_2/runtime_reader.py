"""Fail-closed, read-only Runtime Vision V0.2 smoke reader.

This module joins dynamic geometry and the reviewed template classifier.  It
does not mutate GameState, call Hint Alpha, or expose any UI automation.  The
returned candidate identity is diagnostic; ``tile_id`` is emitted only after
the conservative runtime gates pass.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Iterable

import cv2
from PIL import Image

from workspace.vision.tiles_v0_1.labels import approved_labels
from workspace.vision.tiles_v0_1.taxonomy import HONORS, SUITED, category_for
from workspace.vision.tiles_v0_1.template_classifier import TemplateTileClassifier

from .dynamic_geometry import detect_dynamic_geometry, fuse_dynamic_geometry
from .tile_crop import classification_crop_bbox


STANDARD_CLASSES = frozenset(SUITED) | frozenset(HONORS)
CLASSIFIER_REGIONS = {
    "hand": "hand_region",
    "draw_visual": "draw_visual",
    "gold": "gold_region",
}


def _canonical_region(region: str) -> str:
    return "draw_visual" if region == "draw_region" else region


CONCEALED_IDENTITY_GATE_REGION = "concealed_identity"
CONCEALED_IDENTITY_SOURCE_REGIONS = frozenset({"hand_region", "draw_visual"})
GOLD_IDENTITY_GATE_REGION = "gold_identity"
GOLD_IDENTITY_SOURCE_REGIONS = frozenset({"hand_region", "draw_visual", "gold_region"})


def _gold_skin_covered_classes(labels: list[dict]) -> set[str]:
    """Return classes with at least one reviewed real yellow Gold-skin crop."""
    return {
        row["tile_id"]
        for row in labels
        if row.get("approved") and row.get("gold_skin_only")
    }


def _coverage(
    labels: list[dict],
) -> tuple[set[str], dict[str, set[str]], dict[str, set[str]]]:
    """Return global reporting coverage plus classifier-domain safety coverage."""
    covered = {row["tile_id"] for row in labels if row.get("approved")}
    covered_by_region: dict[str, set[str]] = defaultdict(set)
    sessions: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    concealed_identity_sessions: dict[str, set[str]] = defaultdict(set)
    concealed_identity_covered: set[str] = set()
    gold_identity_sessions: dict[str, set[str]] = defaultdict(set)
    gold_identity_covered: set[str] = set()
    for row in labels:
        if not row.get("approved"):
            continue
        region = _canonical_region(row["region"])
        tile_id = row["tile_id"]
        source_session = row.get("source_session") or row.get("source_id") or "unknown"
        gold_skin_only = bool(row.get("gold_skin_only"))
        if not gold_skin_only:
            covered_by_region[region].add(tile_id)
            sessions[region][tile_id].add(source_session)
            if region in CONCEALED_IDENTITY_SOURCE_REGIONS:
                concealed_identity_covered.add(tile_id)
                concealed_identity_sessions[tile_id].add(source_session)
        if region in GOLD_IDENTITY_SOURCE_REGIONS or gold_skin_only:
            gold_identity_covered.add(tile_id)
            gold_identity_sessions[tile_id].add(source_session)
    cross_session = {
        region: {tile_id for tile_id, values in classes.items() if len(values) >= 2}
        for region, classes in sessions.items()
    }
    # Hand and draw_visual use the same tile-face normalization and are two
    # geometric positions of the same concealed visual domain. Pool them for
    # identity while keeping their geometry/event semantics separate.
    covered_by_region[CONCEALED_IDENTITY_GATE_REGION] = concealed_identity_covered
    cross_session[CONCEALED_IDENTITY_GATE_REGION] = {
        tile_id
        for tile_id, values in concealed_identity_sessions.items()
        if len(values) >= 2
    }

    # Gold-skin classification removes the yellow UI skin and ranks the
    # underlying face against the complete reviewed template bank. Its own
    # domain therefore aggregates only the regions actually used by that bank.
    # A future public-river/meld M2 must not silently make concealed-hand Wan
    # classification look complete.
    covered_by_region[GOLD_IDENTITY_GATE_REGION] = gold_identity_covered
    cross_session[GOLD_IDENTITY_GATE_REGION] = {
        tile_id
        for tile_id, values in gold_identity_sessions.items()
        if len(values) >= 2
    }
    return covered, dict(covered_by_region), cross_session


def _training_labels(labels: list[dict], session: str | None) -> list[dict]:
    """Exclude the current known session so replay smoke tests emulate an unseen session."""
    if not session:
        return labels
    return [
        row for row in labels
        if (row.get("source_session") or row.get("source_id") or "unknown") != session
    ]


def identity_gate(
    candidate_tile_id: str,
    confidence: float,
    *,
    region: str,
    covered_classes: set[str],
    cross_session_classes: dict[str, set[str]],
    confidence_threshold: float,
) -> tuple[str, str]:
    """Return an exact ID or UNKNOWN with an auditable rejection reason."""
    if confidence < confidence_threshold:
        return "UNKNOWN", "below_confidence_threshold"
    missing = STANDARD_CLASSES - covered_classes
    candidate_category = category_for(candidate_tile_id)
    if any(category_for(tile_id) == candidate_category for tile_id in missing):
        return "UNKNOWN", "category_has_missing_standard_class"
    if candidate_tile_id not in cross_session_classes.get(region, set()):
        return "UNKNOWN", "class_not_cross_session_validated_in_region"
    return candidate_tile_id, "accepted"


def read_stable_frames(
    images: Iterable[Image.Image],
    dataset_root: str | Path = "dataset/tiles_runtime_v0_2",
    *,
    frame_ids: Iterable[str | int] | None = None,
    session: str | None = None,
    confidence_threshold: float = 0.82,
) -> dict:
    """Read one 3--5 frame burst and return conservative tile observations."""
    images = [image.convert("RGB") for image in images]
    if not 3 <= len(images) <= 5:
        raise ValueError("Runtime stability fusion requires 3 to 5 frames")
    frame_ids = list(frame_ids) if frame_ids is not None else list(range(len(images)))
    if len(frame_ids) != len(images):
        raise ValueError("frame_ids must match images")

    root = Path(dataset_root)
    labels = approved_labels(root)
    training_labels = _training_labels(labels, session)
    covered, covered_by_region, cross_session = _coverage(training_labels)
    # Gold-skin review is an appearance qualification, not an identity
    # template. Keep the current runtime session excluded from classifier
    # training and cross-session identity support, but allow any approved
    # reviewed Gold-skin crop to prove that this class has been observed under
    # the target yellow UI skin. This cannot make a class pass identity_gate().
    gold_skin_covered = _gold_skin_covered_classes(labels)
    classifier = TemplateTileClassifier.from_labels(root, training_labels)
    geometry_frames = [
        detect_dynamic_geometry(image, frame=frame_id, session=session)
        for image, frame_id in zip(images, frame_ids)
    ]
    fused = fuse_dynamic_geometry(geometry_frames, minimum_frames=3)
    missing = sorted(STANDARD_CLASSES - covered)
    base = {
        "schema_version": "vision_runtime_v0_2_smoke",
        "session": session,
        "current_session_excluded_from_templates": bool(session),
        "frames": frame_ids,
        "confidence_threshold": confidence_threshold,
        "standard_class_coverage": {
            "covered": len(covered & STANDARD_CLASSES),
            "total": len(STANDARD_CLASSES),
            "missing": missing,
        },
        "classification_domain_coverage": {
            region: {
                "covered": len(classes & STANDARD_CLASSES),
                "total": len(STANDARD_CLASSES),
                "missing": sorted(STANDARD_CLASSES - classes),
            }
            for region, classes in sorted(covered_by_region.items())
        },
        "real_gold_skin_evidence": {
            "covered": len(gold_skin_covered & STANDARD_CLASSES),
            "total": len(STANDARD_CLASSES),
            "classes": sorted(gold_skin_covered & STANDARD_CLASSES),
        },
        "geometry_untrusted": fused.geometry_untrusted,
        "geometry_issues": list(fused.issues),
        "safe_for_hint": False,
        "safe_for_executor": False,
    }
    if fused.geometry_untrusted:
        return {
            **base,
            "components": [],
            "concealed_tile_count": None,
            "all_concealed_tile_ids_trusted": False,
            "reason": "geometry_not_stable",
        }

    chosen_index = max(
        index for index, geometry in enumerate(geometry_frames)
        if geometry.frame == fused.frame and not geometry.geometry_untrusted
    )
    image = images[chosen_index]
    all_boxes = [component.pixel_bbox for component in fused.components]
    observations = []
    for component in fused.components:
        item = component.to_dict()
        item.update({
            "candidate_tile_id": None,
            "tile_id": "UNKNOWN",
            "tile_confidence": 0.0,
            "identity_reason": "region_not_classified",
        })
        classifier_region = (
            "gold_region"
            if component.gold_skin
            else CLASSIFIER_REGIONS.get(component.region_candidate)
        )
        if classifier_region is not None:
            crop_bbox = classification_crop_bbox(
                component.pixel_bbox,
                frame_size=image.size,
                neighbors=[box for box in all_boxes if box != component.pixel_bbox],
            )
            x, y, width, height = crop_bbox
            crop = image.crop((x, y, x + width, y + height))
            try:
                if component.gold_skin:
                    prediction = classifier.classify_gold_skin(crop)
                elif component.region_candidate in {"hand", "draw_visual"}:
                    prediction = classifier.classify(
                        crop,
                        region=CONCEALED_IDENTITY_GATE_REGION,
                    )
                else:
                    prediction = classifier.classify(
                        crop,
                        region=classifier_region,
                    )
            except ValueError:
                item["identity_reason"] = "no_templates_for_region"
            else:
                gate_region = (
                    GOLD_IDENTITY_GATE_REGION
                    if component.gold_skin
                    else (
                        CONCEALED_IDENTITY_GATE_REGION
                        if component.region_candidate in {"hand", "draw_visual"}
                        else classifier_region
                    )
                )
                tile_id, reason = identity_gate(
                    prediction.tile_id,
                    prediction.confidence,
                    region=gate_region,
                    covered_classes=covered_by_region.get(gate_region, set()),
                    cross_session_classes=cross_session,
                    confidence_threshold=confidence_threshold,
                )
                if (
                    component.gold_skin
                    and tile_id != "UNKNOWN"
                    and prediction.tile_id not in gold_skin_covered
                ):
                    tile_id = "UNKNOWN"
                    reason = "class_missing_real_gold_skin_example"
                item.update({
                    "classification_crop_bbox": list(crop_bbox),
                    "candidate_tile_id": prediction.tile_id,
                    "tile_id": tile_id,
                    "tile_confidence": round(prediction.confidence, 6),
                    "identity_reason": reason,
                })
        observations.append(item)

    concealed = [
        item for item in observations
        if item["region_candidate"] in {"hand", "draw_visual"}
    ]
    return {
        **base,
        "components": observations,
        "concealed_tile_count": len(concealed),
        "all_concealed_tile_ids_trusted": bool(concealed) and all(
            item["tile_id"] != "UNKNOWN" for item in concealed
        ),
        "reason": "read_only_smoke_observation",
    }


def _video_frames(path: Path, start_frame: int, count: int, stride: int) -> tuple[list[Image.Image], list[int]]:
    capture = cv2.VideoCapture(str(path))
    images, frame_ids = [], []
    try:
        for offset in range(count):
            frame_id = start_frame + offset * stride
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
            ok, frame = capture.read()
            if not ok:
                raise ValueError(f"Cannot read frame {frame_id} from {path}")
            images.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
            frame_ids.append(frame_id)
    finally:
        capture.release()
    return images, frame_ids


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Runtime Vision V0.2 smoke reader")
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument("--video", required=True)
    parser.add_argument("--start-frame", type=int, required=True)
    parser.add_argument("--frames", type=int, default=5, choices=(3, 4, 5))
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument("--session")
    parser.add_argument("--confidence", type=float, default=0.82)
    parser.add_argument("--output")
    args = parser.parse_args()
    images, frame_ids = _video_frames(Path(args.video), args.start_frame, args.frames, args.stride)
    report = read_stable_frames(
        images,
        args.dataset,
        frame_ids=frame_ids,
        session=args.session,
        confidence_threshold=args.confidence,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
