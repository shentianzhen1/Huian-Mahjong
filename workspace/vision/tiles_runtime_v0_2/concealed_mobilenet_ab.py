"""Development-only MobileNetV3 feasibility runner for concealed identities.

This module deliberately does **not** change Runtime Vision. It compares a
pretrained MobileNetV3-Small embedding prototype candidate with the frozen
Template Runtime on the exact same reviewed private crops.

Important boundaries:
- whole original matches are the independence unit when reviewed lineage exists;
- source_session names are never treated as match independence;
- the Runtime confidence threshold remains 0.82;
- MobileNet cosine scores are NOT calibrated to that threshold here, so this
  runner reports raw Top-1 / whole-hand exact feasibility only and explicitly
  blocks Runtime promotion;
- raw/private query crops remain local and are referenced through private://
  manifest paths.

The feature extractor is loaded lazily so normal/core test environments do not
need torch/torchvision. A machine running the actual experiment must provide the
pretrained torchvision weights (cached locally or downloadable there).
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any, Iterable

from workspace.vision.concealed_template_match_lineage import (
    ConcealedTemplateSource,
    load_concealed_template_lineage,
)

from .whole_hand_eval import FROZEN_CONFIDENCE_THRESHOLD, REVIEWED_COMPLETE, validate_manifest


MODEL_NAME = "mobilenet_v3_small_imagenet1k_v1"
EMBEDDING_INPUT_SIZE = 224
CONCEALED_IDENTITY_REGIONS = frozenset({"hand_region", "draw_visual"})
STANDARD_CLASSES = frozenset(
    [f"M{i}" for i in range(1, 10)]
    + [f"P{i}" for i in range(1, 10)]
    + [f"S{i}" for i in range(1, 10)]
    + ["E", "SOUTH", "W", "N", "R", "G", "B"]
)
APPEARANCE_AUGMENTATION_VERSION = "v0_2_real_bottom_shadow"
# The revealed 2026-10-03 pair measured its strongest horizontal shadow in the
# bottom 82%-100% of the normalized tile face. Ordinary samples were about >=-35
# bottom-minus-middle luminance while the shadow state was <=-67. Keep this as a
# deterministic training augmentation only; it is not a Runtime detector/gate.
OBSERVED_SHADOW_FEATHER_START = 0.72
OBSERVED_SHADOW_FULL_BAND_START = 0.82
OBSERVED_SHADOW_DARKEN_DELTA = 72.0


def _approved(row: dict[str, Any]) -> bool:
    return row.get("approved") is True or row.get("status") == "approved"


def select_training_labels(
    labels: Iterable[dict[str, Any]],
    lineage_by_sha: dict[str, ConcealedTemplateSource],
    *,
    query_match_groups: set[str],
    strict_original_match_lineage: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select non-Gold concealed labels without same-match leakage.

    Strict mode excludes every source whose exact SHA has no reviewed
    original-match lineage. Permissive mode is development-only: unresolved
    sources may be used for architecture exploration, but the returned report
    marks them and formal promotion remains blocked.
    """
    if not query_match_groups or any(not group for group in query_match_groups):
        raise ValueError("query_match_groups must contain reviewed non-empty groups")

    accepted: list[dict[str, Any]] = []
    missing_lineage = 0
    same_match = 0
    malformed_source_sha = 0
    unresolved_shas: set[str] = set()
    represented_groups: set[str] = set()

    for row in labels:
        if (
            not _approved(row)
            or row.get("gold_skin_only")
            or row.get("region") not in CONCEALED_IDENTITY_REGIONS
        ):
            continue
        tile_id = row.get("tile_id")
        sha = row.get("sha256")
        if not isinstance(tile_id, str) or tile_id not in STANDARD_CLASSES:
            continue
        if not isinstance(sha, str) or len(sha) != 64:
            malformed_source_sha += 1
            continue

        source = lineage_by_sha.get(sha)
        if source is None:
            missing_lineage += 1
            unresolved_shas.add(sha)
            if strict_original_match_lineage:
                continue
            copied = dict(row)
            copied["_original_match_group"] = None
            copied["_lineage_qualified"] = False
            accepted.append(copied)
            continue

        if source.match_group in query_match_groups:
            same_match += 1
            continue
        copied = dict(row)
        copied["_original_match_group"] = source.match_group
        copied["_lineage_qualified"] = True
        accepted.append(copied)
        represented_groups.add(source.match_group)

    coverage = {row["tile_id"] for row in accepted}
    return accepted, {
        "strict_original_match_lineage": strict_original_match_lineage,
        "selected_label_count": len(accepted),
        "selected_class_count": len(coverage),
        "missing_classes": sorted(STANDARD_CLASSES - coverage),
        "excluded_missing_lineage_count": (
            missing_lineage if strict_original_match_lineage else 0
        ),
        "development_included_unresolved_lineage_count": (
            missing_lineage if not strict_original_match_lineage else 0
        ),
        "development_unresolved_source_shas": (
            sorted(unresolved_shas) if not strict_original_match_lineage else []
        ),
        "excluded_same_original_match_count": same_match,
        "excluded_malformed_source_sha_count": malformed_source_sha,
        "reviewed_training_match_group_count": len(represented_groups),
        "source_session_used_as_independence_signal": False,
        "formal_promotion_evidence": False,
    }


def resolve_private_crop(crop_root: str | Path, crop_ref: str) -> Path:
    """Resolve ``private://sample/file`` below one explicit local root."""
    if not isinstance(crop_ref, str) or not crop_ref.startswith("private://"):
        raise ValueError("query crop_ref must use private://")
    relative = crop_ref[len("private://") :]
    if not relative or relative.startswith("/"):
        raise ValueError("invalid private crop_ref")
    root = Path(crop_root).resolve()
    path = (root / relative).resolve()
    if root != path and root not in path.parents:
        raise ValueError("private crop_ref escapes crop root")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _square_tile_canvas(image: Any) -> Any:
    from PIL import Image

    tile = image.convert("RGB")
    target_height = 192
    scale = target_height / max(1, tile.height)
    target_width = max(1, int(round(tile.width * scale)))
    if target_width > 160:
        scale = 160 / max(1, tile.width)
        target_width = 160
        target_height = max(1, int(round(tile.height * scale)))
    resized = tile.resize((target_width, target_height), Image.Resampling.BICUBIC)
    canvas = Image.new("RGB", (EMBEDDING_INPUT_SIZE, EMBEDDING_INPUT_SIZE), "white")
    left = (EMBEDDING_INPUT_SIZE - target_width) // 2
    top = (EMBEDDING_INPUT_SIZE - target_height) // 2
    canvas.paste(resized, (left, top))
    return canvas


def _bottom_shadow_variant(image: Any) -> Any:
    """Apply the observed bottom-band appearance without changing geometry.

    The transform is intentionally simple and deterministic. It starts a linear
    darkening ramp at 72% of the source crop, reaches the observed shadow band at
    82%, then subtracts 72 luminance levels through the bottom. The source crop
    size is preserved so this can only affect learned appearance robustness.
    """
    from PIL import Image
    import numpy as np

    source = image.convert("RGB")
    array = np.asarray(source).astype(np.float32)
    height = array.shape[0]
    feather_start = max(
        0, min(height, int(round(height * OBSERVED_SHADOW_FEATHER_START)))
    )
    full_start = max(
        feather_start,
        min(height, int(round(height * OBSERVED_SHADOW_FULL_BAND_START))),
    )
    if full_start > feather_start:
        ramp = np.linspace(
            0.0,
            OBSERVED_SHADOW_DARKEN_DELTA,
            full_start - feather_start,
            endpoint=False,
            dtype=np.float32,
        ).reshape(-1, 1, 1)
        array[feather_start:full_start] -= ramp
    if full_start < height:
        array[full_start:] -= OBSERVED_SHADOW_DARKEN_DELTA
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8))


def _appearance_variants(image: Any) -> list[Any]:
    """Deterministic development variants requested by the whole-hand audit."""
    from PIL import Image, ImageEnhance
    import numpy as np

    base = _square_tile_canvas(image)
    rows = [base]
    rows.append(ImageEnhance.Brightness(base).enhance(0.72))
    rows.append(ImageEnhance.Brightness(base).enhance(1.18))

    for dx, dy, scale in ((-5, 0, 0.96), (5, 0, 1.04), (0, -4, 1.0)):
        width = max(1, int(round(base.width * scale)))
        height = max(1, int(round(base.height * scale)))
        resized = base.resize((width, height), Image.Resampling.BICUBIC)
        canvas = Image.new("RGB", base.size, "white")
        left = (base.width - width) // 2 + dx
        top = (base.height - height) // 2 + dy
        canvas.paste(resized, (left, top))
        rows.append(canvas)

    rows.append(ImageEnhance.Brightness(base).enhance(0.50))
    rows.append(_square_tile_canvas(_bottom_shadow_variant(image)))

    array = np.asarray(base).astype(np.float32)
    luminance = array.mean(axis=2, keepdims=True) / 255.0
    alpha = np.clip((luminance - 0.45) * 0.55, 0.0, 0.40)
    yellow = np.asarray([255.0, 211.0, 54.0], dtype=np.float32).reshape(1, 1, 3)
    gold = array * (1.0 - alpha) + yellow * alpha
    rows.append(Image.fromarray(np.clip(gold, 0, 255).astype(np.uint8)))
    return rows


def _load_model() -> tuple[Any, Any, str]:
    import torch
    from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small
    from torchvision.transforms import Compose, Normalize, PILToTensor

    weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1
    try:
        model = mobilenet_v3_small(weights=weights)
    except Exception as exc:  # pragma: no cover - environment/network dependent
        raise RuntimeError(
            "pretrained MobileNetV3-Small weights are unavailable on this machine; "
            "do not substitute random weights for the A/B experiment"
        ) from exc
    model.classifier = torch.nn.Identity()
    model.eval()
    transform = Compose(
        [
            PILToTensor(),
            lambda tensor: tensor.float().div(255.0),
            Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )
    return model, transform, str(weights)


def _embed_images(images: list[Any], model: Any, transform: Any) -> Any:
    import numpy as np
    import torch

    vectors: list[Any] = []
    with torch.inference_mode():
        for start in range(0, len(images), 32):
            batch = torch.stack(
                [transform(image) for image in images[start : start + 32]], dim=0
            )
            output = model(batch).detach().cpu().numpy().astype("float32", copy=False)
            norms = np.maximum(np.linalg.norm(output, axis=1, keepdims=True), 1e-12)
            vectors.append(output / norms)
    return np.concatenate(vectors, axis=0)


def _prototype_bank(
    dataset_root: Path,
    rows: list[dict[str, Any]],
    model: Any,
    transform: Any,
) -> dict[str, Any]:
    import numpy as np
    from PIL import Image

    tile_ids: list[str] = []
    images: list[Any] = []
    root = dataset_root.resolve()
    for row in rows:
        path = (root / row["image"]).resolve()
        if root != path and root not in path.parents:
            raise ValueError("training image escapes dataset root")
        with Image.open(path) as original:
            variants = _appearance_variants(original.convert("RGB"))
        tile_ids.extend([row["tile_id"]] * len(variants))
        images.extend(variants)

    embeddings = _embed_images(images, model, transform)
    grouped: dict[str, list[Any]] = defaultdict(list)
    for tile_id, vector in zip(tile_ids, embeddings):
        grouped[tile_id].append(vector)
    prototypes: dict[str, Any] = {}
    for tile_id, vectors in grouped.items():
        mean = np.mean(np.stack(vectors, axis=0), axis=0).astype("float32", copy=False)
        norm = float(np.linalg.norm(mean))
        if norm > 1e-12:
            prototypes[tile_id] = mean / norm
    return prototypes


def run_feasibility(
    manifest_path: str | Path,
    crop_root: str | Path,
    dataset_root: str | Path,
    lineage_path: str | Path,
    *,
    strict_original_match_lineage: bool = True,
) -> dict[str, Any]:
    import numpy as np
    from PIL import Image

    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    validate_manifest(manifest)
    query_match_groups = {
        str(hand["original_match_group"])
        for hand in manifest["hands"]
        if hand.get("truth_status") == REVIEWED_COMPLETE
    }
    if not query_match_groups:
        raise ValueError("no reviewed complete query hands")

    dataset = Path(dataset_root).resolve()
    labels = [
        json.loads(line)
        for line in (dataset / "labels.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    lineage = load_concealed_template_lineage(lineage_path)
    training_rows, selection = select_training_labels(
        labels,
        lineage,
        query_match_groups=query_match_groups,
        strict_original_match_lineage=strict_original_match_lineage,
    )
    if selection["missing_classes"]:
        raise ValueError(
            "candidate training bank is not 34-class complete under the requested "
            "lineage policy: " + ",".join(selection["missing_classes"])
        )

    model, transform, weight_name = _load_model()
    prototypes = _prototype_bank(dataset, training_rows, model, transform)

    query_images: list[Any] = []
    query_rows: list[dict[str, Any]] = []
    for hand in manifest["hands"]:
        if hand.get("truth_status") != REVIEWED_COMPLETE:
            continue
        for slot in hand["slots"]:
            if slot.get("detection_status") != "matched":
                continue
            crop_ref = slot.get("crop_ref")
            path = resolve_private_crop(crop_root, crop_ref)
            with Image.open(path) as original:
                query_images.append(_square_tile_canvas(original.convert("RGB")))
            query_rows.append(
                {
                    "sample_id": hand["sample_id"],
                    "truth_tile": slot["truth_tile"],
                    "crop_status": slot["crop_status"],
                    "crop_ref": crop_ref,
                    "template_top1": (
                        slot.get("predictions", {}).get("template", {}).get("tile_id")
                    ),
                }
            )

    embeddings = _embed_images(query_images, model, transform)
    prototype_ids = sorted(prototypes)
    matrix = np.stack([prototypes[tile_id] for tile_id in prototype_ids], axis=0)
    raw_confusions: Counter[str] = Counter()
    template_confusions: Counter[str] = Counter()
    candidate_correct = 0
    template_correct = 0
    hand_candidate_ok: dict[str, bool] = defaultdict(lambda: True)
    hand_template_ok: dict[str, bool] = defaultdict(lambda: True)
    results = []

    for row, vector in zip(query_rows, embeddings):
        scores = matrix @ vector
        best = int(np.argmax(scores))
        candidate = prototype_ids[best]
        truth = row["truth_tile"]
        template = row["template_top1"]
        candidate_ok = candidate == truth
        template_ok = template == truth
        candidate_correct += int(candidate_ok)
        template_correct += int(template_ok)
        hand_candidate_ok[row["sample_id"]] &= candidate_ok
        hand_template_ok[row["sample_id"]] &= template_ok
        if not candidate_ok:
            raw_confusions[f"{truth}->{candidate}"] += 1
        if template is not None and not template_ok:
            template_confusions[f"{truth}->{template}"] += 1
        results.append(
            {
                **row,
                "candidate_top1": candidate,
                "candidate_cosine": round(float(scores[best]), 6),
                "candidate_correct": candidate_ok,
                "template_correct": template_ok,
            }
        )

    total = len(results)
    return {
        "schema_version": "concealed_mobilenet_v3_small_feasibility_ab_v0_2",
        "status": "DEVELOPMENT_RAW_TOP1_ONLY_NOT_RUNTIME_CALIBRATED",
        "model": MODEL_NAME,
        "weights": weight_name,
        "pretrained_weights_required": True,
        "appearance_augmentation_version": APPEARANCE_AUGMENTATION_VERSION,
        "observed_bottom_shadow_augmentation": {
            "enabled": True,
            "feather_start_fraction": OBSERVED_SHADOW_FEATHER_START,
            "full_band_start_fraction": OBSERVED_SHADOW_FULL_BAND_START,
            "darken_delta": OBSERVED_SHADOW_DARKEN_DELTA,
            "runtime_gate": False,
        },
        "training_selection": selection,
        "query_match_groups": sorted(query_match_groups),
        "same_query_crops_for_template_and_candidate": True,
        "query_tile_count": total,
        "template_raw_top1_correct": template_correct,
        "template_raw_top1_accuracy": template_correct / total if total else None,
        "candidate_raw_top1_correct": candidate_correct,
        "candidate_raw_top1_accuracy": candidate_correct / total if total else None,
        "template_whole_hand_exact_count": sum(hand_template_ok.values()),
        "candidate_whole_hand_exact_count": sum(hand_candidate_ok.values()),
        "reviewed_complete_hand_count": len(hand_candidate_ok),
        "candidate_raw_confusions": dict(raw_confusions.most_common()),
        "template_raw_confusions": dict(template_confusions.most_common()),
        "frozen_runtime_confidence_threshold": FROZEN_CONFIDENCE_THRESHOLD,
        "candidate_confidence_calibration": "NOT_ESTABLISHED",
        "candidate_threshold_acceptance_metrics_valid": False,
        "promotion_blockers": [
            "candidate cosine is not calibrated to Runtime 0.82 confidence",
            "requires independent original-match whole-hand validation after model selection",
        ],
        "results": results,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("crop_root")
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument(
        "--lineage",
        default=(
            "references/vision/2026-10-01/"
            "concealed_template_match_lineage.development.json"
        ),
    )
    parser.add_argument(
        "--allow-unresolved-development-sources",
        action="store_true",
        help="architecture exploration only; never formal promotion evidence",
    )
    parser.add_argument("--output")
    args = parser.parse_args()
    report = run_feasibility(
        args.manifest,
        args.crop_root,
        args.dataset,
        args.lineage,
        strict_original_match_lineage=(
            not args.allow_unresolved_development_sources
        ),
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
