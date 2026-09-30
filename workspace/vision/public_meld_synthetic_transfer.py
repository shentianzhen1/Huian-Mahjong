"""Development-only A/B for synthetic hand-to-meld domain transfer.

This experiment tests one narrow hypothesis before any learned classifier is
introduced: does rendering reviewed concealed-hand tile crops into a
player-side exposed-meld visual domain improve SIFT identity ranking on the
already-reviewed regular public-meld samples?

The experiment is intentionally selection/development evidence:
- it uses previously reviewed public-meld groups;
- synthetic parameters may be changed after looking at these results;
- it does not change Runtime, Hint, Executor, or identity thresholds;
- it is not blind validation and cannot promote the public_meld identity path.

If this small batch is promising, the same interface can later feed a compact
learned classifier and a separately frozen blind holdout.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from PIL import Image

from workspace.vision.public_meld_face_segmentation import prepare_public_meld_faces
from workspace.vision.public_meld_group_identity_decoder import (
    rank_regular_public_meld_identity,
)
from workspace.vision.public_meld_identity_sift import (
    _descriptor_similarity,
    _sift_descriptors,
)
from workspace.vision.public_tile_detector import PublicGeometryCandidate
from workspace.vision.tiles_v0_1.labels import approved_labels


SYNTHETIC_CANONICAL_SIZE = (56, 96)
SYNTHETIC_TILT_FRACTIONS = (-0.05, -0.025, 0.0, 0.025, 0.05)
SYNTHETIC_BLUR_SIGMAS = (0.0, 0.55)
SYNTHETIC_TOP_TAPER_FRACTION = 0.035
MAX_HAND_TEMPLATES_PER_CLASS = 3


@dataclass(frozen=True)
class HandTemplateRecord:
    tile_id: str
    source_session: str | None
    image_path: Path
    raw_descriptors: Any
    synthetic_descriptors: tuple[Any, ...]


def _tight_bright_tile_face(image: Any) -> Any:
    """Crop the dominant bright tile body while retaining colored glyphs."""
    import cv2
    import numpy as np

    rgb = np.asarray(image.convert("RGB"))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    mask = ((hsv[:, :, 1] < 175) & (hsv[:, :, 2] > 95)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        np.ones((5, 5), dtype=np.uint8),
        iterations=1,
    )
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if count <= 1:
        return image.convert("RGB")

    frame_area = rgb.shape[0] * rgb.shape[1]
    candidates: list[tuple[int, int, int, int, int]] = []
    for index in range(1, count):
        x, y, width, height, area = (int(value) for value in stats[index])
        if (
            area >= 0.18 * frame_area
            and width >= 8
            and height >= 12
            and height >= width
        ):
            candidates.append((area, x, y, width, height))
    if not candidates:
        return image.convert("RGB")

    _, x, y, width, height = max(candidates)
    return image.convert("RGB").crop((x, y, x + width, y + height))


def _canonical_face(image: Any) -> Any:
    face = _tight_bright_tile_face(image)
    return face.resize(SYNTHETIC_CANONICAL_SIZE, Image.Resampling.BICUBIC)


def render_self_meld_variants(image: Any) -> tuple[Any, ...]:
    """Render a concealed tile into a small player-side meld-domain family.

    The current public-meld pipeline deskews the three-face row before identity,
    so this first experiment models only residual single-face perspective,
    top-edge taper, interpolation and mild blur. It deliberately avoids tuning
    a large augmentation search space on the same reviewed queries.
    """
    import cv2
    import numpy as np

    base = np.asarray(_canonical_face(image).convert("RGB"), dtype=np.uint8)
    width, height = SYNTHETIC_CANONICAL_SIZE
    source = np.float32(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]]
    )
    taper = float(width * SYNTHETIC_TOP_TAPER_FRACTION)
    variants: list[Any] = []

    for tilt_fraction in SYNTHETIC_TILT_FRACTIONS:
        shift = float(width * tilt_fraction)
        # Keep the projected tile fully inside the canvas. Positive shift moves
        # the top edge right; negative shift moves it left.
        left_top = taper + max(shift, 0.0)
        right_top = (width - 1 - taper) + min(shift, 0.0)
        destination = np.float32(
            [
                [left_top, 1.0],
                [right_top, 1.0],
                [width - 2.0, height - 2.0],
                [1.0, height - 2.0],
            ]
        )
        matrix = cv2.getPerspectiveTransform(source, destination)
        warped = cv2.warpPerspective(
            base,
            matrix,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        for sigma in SYNTHETIC_BLUR_SIGMAS:
            rendered = warped
            if sigma > 0:
                rendered = cv2.GaussianBlur(
                    warped,
                    (0, 0),
                    sigmaX=float(sigma),
                    sigmaY=float(sigma),
                )
            variants.append(Image.fromarray(rendered))

    return tuple(variants)


def _pixel_bbox(
    normalized_bbox: list[float] | tuple[float, float, float, float],
    size: tuple[int, int],
) -> tuple[int, int, int, int]:
    frame_width, frame_height = size
    x, y, width, height = (float(value) for value in normalized_bbox)
    left = max(0, int(round(x * frame_width)))
    top = max(0, int(round(y * frame_height)))
    right = min(frame_width, int(round((x + width) * frame_width)))
    bottom = min(frame_height, int(round((y + height) * frame_height)))
    return left, top, max(0, right - left), max(0, bottom - top)


def _regular_player_meld_samples(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in payload.get("samples", ())
        if (
            row.get("target") == "meld"
            and row.get("actor") == "player"
            and isinstance(row.get("expected_tiles"), list)
            and len(row["expected_tiles"]) == 3
            and row.get("status") == "bbox_reviewed"
        )
    ]


def _balanced_hand_labels(
    dataset_root: Path,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in approved_labels(dataset_root):
        if row.get("region") != "hand_region" or row.get("gold_skin_only"):
            continue
        image_path = row.get("image")
        tile_id = row.get("tile_id")
        if not isinstance(image_path, str) or not isinstance(tile_id, str):
            continue
        grouped[tile_id].append(row)

    selected: list[dict[str, Any]] = []
    for tile_id in sorted(grouped):
        rows = sorted(
            grouped[tile_id],
            key=lambda row: (
                str(row.get("source_session") or ""),
                str(row.get("image") or ""),
                int(row.get("source_frame") or -1),
            ),
        )
        chosen: list[dict[str, Any]] = []
        used_sessions: set[str] = set()
        for row in rows:
            session = str(row.get("source_session") or "")
            if session and session in used_sessions:
                continue
            chosen.append(row)
            if session:
                used_sessions.add(session)
            if len(chosen) >= MAX_HAND_TEMPLATES_PER_CLASS:
                break
        if len(chosen) < MAX_HAND_TEMPLATES_PER_CLASS:
            for row in rows:
                if row in chosen:
                    continue
                chosen.append(row)
                if len(chosen) >= MAX_HAND_TEMPLATES_PER_CLASS:
                    break
        selected.extend(chosen)
    return selected


def _build_hand_template_bank(dataset_root: Path) -> tuple[HandTemplateRecord, ...]:
    records: list[HandTemplateRecord] = []
    for row in _balanced_hand_labels(dataset_root):
        image_path = (dataset_root / row["image"]).resolve()
        if dataset_root.resolve() not in image_path.parents:
            raise ValueError("hand template path escapes dataset root")
        with Image.open(image_path) as source:
            image = source.convert("RGB")
        raw = _sift_descriptors(_canonical_face(image))
        if raw is None:
            continue
        synthetic = tuple(
            descriptors
            for descriptors in (
                _sift_descriptors(variant)
                for variant in render_self_meld_variants(image)
            )
            if descriptors is not None
        )
        if not synthetic:
            continue
        records.append(
            HandTemplateRecord(
                tile_id=row["tile_id"],
                source_session=row.get("source_session"),
                image_path=image_path,
                raw_descriptors=raw,
                synthetic_descriptors=synthetic,
            )
        )
    return tuple(records)


def _class_scores(
    query_descriptors: Any,
    bank: tuple[HandTemplateRecord, ...],
    *,
    synthetic: bool,
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for record in bank:
        candidates = (
            record.synthetic_descriptors
            if synthetic
            else (record.raw_descriptors,)
        )
        best: float | None = None
        for descriptors in candidates:
            score = _descriptor_similarity(query_descriptors, descriptors)
            if score is None:
                continue
            best = score if best is None else max(best, score)
        if best is None:
            continue
        scores[record.tile_id] = max(scores.get(record.tile_id, float("-inf")), best)
    return scores


def _top1(scores: dict[str, float]) -> tuple[str | None, float | None]:
    if not scores:
        return None, None
    tile_id, score = min(scores.items(), key=lambda row: (-row[1], row[0]))
    return tile_id, float(score)


def evaluate_public_meld_synthetic_transfer(
    repository_root: str | Path = ".",
    dataset_root: str | Path = "dataset/tiles_runtime_v0_2",
    calibration_path: str | Path = (
        "references/vision/2026-09-22/public_detector_calibration_v0_1.json"
    ),
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    dataset = (root / dataset_root).resolve()
    calibration = json.loads((root / calibration_path).read_text(encoding="utf-8"))
    samples = _regular_player_meld_samples(calibration)
    bank = _build_hand_template_bank(dataset)
    if not bank:
        raise ValueError("synthetic hand-template bank is empty")

    face_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []

    for sample in samples:
        image_path = (root / sample["image_path"]).resolve()
        if root not in image_path.parents:
            raise ValueError("public meld image escapes repository root")
        with Image.open(image_path) as source:
            image = source.convert("RGB")

        bbox = _pixel_bbox(sample["bbox"], image.size)
        group = PublicGeometryCandidate(
            pixel_bbox=bbox,
            normalized_bbox=tuple(float(value) for value in sample["bbox"]),
            geometry_kind="bottom_group",
            confidence=1.0,
            fill_ratio=1.0,
            frame=sample.get("frame_index"),
            session=sample.get("source_session"),
        )
        prepared = prepare_public_meld_faces(image, group)
        if len(prepared.face_images) != 3:
            group_rows.append(
                {
                    "sample_id": sample["sample_id"],
                    "expected_tiles": list(sample["expected_tiles"]),
                    "prepared_face_count": len(prepared.face_images),
                    "baseline_group_correct": False,
                    "synthetic_group_correct": False,
                    "reason": "not_three_classifier_ready_faces",
                }
            )
            continue

        baseline_face_scores: list[dict[str, float]] = []
        synthetic_face_scores: list[dict[str, float]] = []
        for face_index, (face, expected_tile) in enumerate(
            zip(prepared.face_images, sample["expected_tiles"])
        ):
            query = _sift_descriptors(_canonical_face(face))
            if query is None:
                baseline_scores: dict[str, float] = {}
                synthetic_scores: dict[str, float] = {}
            else:
                baseline_scores = _class_scores(query, bank, synthetic=False)
                synthetic_scores = _class_scores(query, bank, synthetic=True)
            baseline_tile, baseline_score = _top1(baseline_scores)
            synthetic_tile, synthetic_score = _top1(synthetic_scores)
            baseline_face_scores.append(baseline_scores)
            synthetic_face_scores.append(synthetic_scores)
            face_rows.append(
                {
                    "sample_id": sample["sample_id"],
                    "face_index": face_index,
                    "expected_tile": expected_tile,
                    "baseline_top1": baseline_tile,
                    "baseline_score": (
                        round(baseline_score, 8)
                        if baseline_score is not None
                        else None
                    ),
                    "baseline_correct": baseline_tile == expected_tile,
                    "synthetic_top1": synthetic_tile,
                    "synthetic_score": (
                        round(synthetic_score, 8)
                        if synthetic_score is not None
                        else None
                    ),
                    "synthetic_correct": synthetic_tile == expected_tile,
                }
            )

        baseline_group = rank_regular_public_meld_identity(baseline_face_scores)
        synthetic_group = rank_regular_public_meld_identity(synthetic_face_scores)
        expected_sorted = sorted(sample["expected_tiles"])
        baseline_group_correct = (
            baseline_group.top_tiles is not None
            and sorted(baseline_group.top_tiles) == expected_sorted
        )
        synthetic_group_correct = (
            synthetic_group.top_tiles is not None
            and sorted(synthetic_group.top_tiles) == expected_sorted
        )
        group_rows.append(
            {
                "sample_id": sample["sample_id"],
                "expected_tiles": list(sample["expected_tiles"]),
                "prepared_face_count": 3,
                "baseline_group_tiles": (
                    list(baseline_group.top_tiles)
                    if baseline_group.top_tiles is not None
                    else None
                ),
                "baseline_group_correct": baseline_group_correct,
                "synthetic_group_tiles": (
                    list(synthetic_group.top_tiles)
                    if synthetic_group.top_tiles is not None
                    else None
                ),
                "synthetic_group_correct": synthetic_group_correct,
            }
        )

    baseline_face_correct = sum(bool(row["baseline_correct"]) for row in face_rows)
    synthetic_face_correct = sum(bool(row["synthetic_correct"]) for row in face_rows)
    scorable_groups = [
        row for row in group_rows if row.get("prepared_face_count") == 3
    ]
    baseline_group_correct = sum(
        bool(row["baseline_group_correct"]) for row in scorable_groups
    )
    synthetic_group_correct = sum(
        bool(row["synthetic_group_correct"]) for row in scorable_groups
    )

    face_count = len(face_rows)
    group_count = len(scorable_groups)
    baseline_face_accuracy = (
        baseline_face_correct / face_count if face_count else None
    )
    synthetic_face_accuracy = (
        synthetic_face_correct / face_count if face_count else None
    )
    baseline_group_accuracy = (
        baseline_group_correct / group_count if group_count else None
    )
    synthetic_group_accuracy = (
        synthetic_group_correct / group_count if group_count else None
    )

    return {
        "schema_version": "public_meld_synthetic_transfer_v0_1",
        "method": "balanced_hand_templates_to_self_meld_domain_then_sift",
        "profile": {
            "canonical_size": list(SYNTHETIC_CANONICAL_SIZE),
            "tilt_fractions": list(SYNTHETIC_TILT_FRACTIONS),
            "blur_sigmas": list(SYNTHETIC_BLUR_SIGMAS),
            "top_taper_fraction": SYNTHETIC_TOP_TAPER_FRACTION,
            "maximum_hand_templates_per_class": MAX_HAND_TEMPLATES_PER_CLASS,
        },
        "selected_hand_template_count": len(bank),
        "selected_hand_class_count": len({row.tile_id for row in bank}),
        "target_group_count": len(samples),
        "scored_group_count": group_count,
        "target_face_count": sum(len(row["expected_tiles"]) for row in samples),
        "scored_face_count": face_count,
        "baseline": {
            "name": "raw_hand_template_sift",
            "face_top1_correct": baseline_face_correct,
            "face_top1_accuracy": (
                round(baseline_face_accuracy, 6)
                if baseline_face_accuracy is not None
                else None
            ),
            "group_top1_correct": baseline_group_correct,
            "group_top1_accuracy": (
                round(baseline_group_accuracy, 6)
                if baseline_group_accuracy is not None
                else None
            ),
        },
        "synthetic": {
            "name": "synthetic_self_meld_template_sift",
            "face_top1_correct": synthetic_face_correct,
            "face_top1_accuracy": (
                round(synthetic_face_accuracy, 6)
                if synthetic_face_accuracy is not None
                else None
            ),
            "group_top1_correct": synthetic_group_correct,
            "group_top1_accuracy": (
                round(synthetic_group_accuracy, 6)
                if synthetic_group_accuracy is not None
                else None
            ),
        },
        "face_accuracy_delta": (
            round(synthetic_face_accuracy - baseline_face_accuracy, 6)
            if (
                synthetic_face_accuracy is not None
                and baseline_face_accuracy is not None
            )
            else None
        ),
        "group_accuracy_delta": (
            round(synthetic_group_accuracy - baseline_group_accuracy, 6)
            if (
                synthetic_group_accuracy is not None
                and baseline_group_accuracy is not None
            )
            else None
        ),
        "faces": face_rows,
        "groups": group_rows,
        "evidence_role": "development_selection_only",
        "blind_validation": False,
        "opponent_top_group_accuracy_measured": False,
        "opponent_note": (
            "No reviewed opponent exposed-meld identity group is present in the "
            "current calibration set. Do not infer opponent accuracy from the "
            "player-side result."
        ),
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument(
        "--calibration",
        default="references/vision/2026-09-22/public_detector_calibration_v0_1.json",
    )
    parser.add_argument("--output")
    args = parser.parse_args()
    report = evaluate_public_meld_synthetic_transfer(
        args.repository_root,
        args.dataset,
        args.calibration,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
