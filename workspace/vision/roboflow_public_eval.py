"""Read-only Roboflow comparison against the project's APPROVED public screenshots.

The public archive contains partially labeled screenshots, NOT exhaustively
labeled frames. Thus we measure recall and label correctness only at the
approved face boxes; detections elsewhere are not measurable false positives.
This module does not promote labels, train a model or drive the Executor.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Callable

from workspace.vision.public_identity_labels import (
    approved_labels,
    load_public_identity_manifest,
)

MODEL_ID = "mahjong-baq4s/83"
API_URL = "https://serverless.roboflow.com"
DEFAULT_MANIFEST = "references/vision/2026-09-22/public_identity_labels_v0_1.json"
STANDARD_MAP = {
    **{f"{i}C": f"M{i}" for i in range(1, 10)},
    **{f"{i}D": f"P{i}" for i in range(1, 10)},
    **{f"{i}B": f"S{i}" for i in range(1, 10)},
    "EW": "E", "SW": "SOUTH", "WW": "W", "NW": "N",
    "RD": "R", "GD": "G", "WD": "B",
}


def map_class(name: str) -> str | None:
    """Unsupported source classes (notably 1S..4S) remain UNKNOWN."""
    return STANDARD_MAP.get(name.strip().upper())


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _labeled_images(root: Path, manifest_path: Path) -> dict[str, dict[str, Any]]:
    manifest = load_public_identity_manifest(manifest_path)
    root = root.resolve()
    grouped: dict[str, dict[str, Any]] = {}
    for label in approved_labels(manifest):
        image = (root / label.image_path).resolve()
        if not image.is_relative_to(root) or not image.is_file():
            raise ValueError("approved image missing or outside repository root")
        if image.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            raise ValueError("approved image must be a PNG/JPEG")
        if _sha(image) != label.image_sha256:
            raise ValueError("approved image SHA256 mismatch; no cloud upload")
        relative = str(image.relative_to(root)).replace("\\", "/")
        entry = grouped.setdefault(relative, {
            "absolute_path": image,
            "source_group": label.source_session,
            "labels": [],
        })
        if entry["source_group"] != label.source_session:
            raise ValueError("one approved image cannot belong to two source sessions")
        entry["labels"].append({
            "tile_id": label.tile_id,
            "region": label.region,
            "bbox": list(label.bbox),
        })
    if not grouped:
        raise ValueError("no approved public screenshots available")
    if len(grouped) > 12:
        raise ValueError("trial limited to 12 already-public images to bound API cost")
    return dict(sorted(grouped.items()))


def box_iou(a: list[float] | tuple[float, ...], b: list[float] | tuple[float, ...]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    left, top = max(ax, bx), max(ay, by)
    right, bottom = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    union = aw * ah + bw * bh - intersection
    return intersection / union if union > 0 else 0.0


def _parse_prediction(row: dict[str, Any], image_size: tuple[int, int]) -> dict[str, Any]:
    width, height = image_size
    try:
        klass = str(row["class"])
        cx, cy = float(row["x"]), float(row["y"])
        w, h = float(row["width"]), float(row["height"])
        confidence = float(row["confidence"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid model prediction structure") from exc
    if (not klass or not all(math.isfinite(v) for v in (cx, cy, w, h, confidence))
            or not 0 <= confidence <= 1 or w <= 0 or h <= 0
            or cx - w / 2 < -1 or cy - h / 2 < -1
            or cx + w / 2 > width + 1 or cy + h / 2 > height + 1):
        raise ValueError("invalid model bounding box or confidence")
    return {
        "tile_id": map_class(klass),
        "raw_class": klass,
        "bbox": [(cx - w / 2) / width, (cy - h / 2) / height,
                 w / width, h / height],
        "confidence": confidence,
    }


def score_partial_labels(
    labels: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    *,
    min_iou: float = 0.5,
) -> dict[str, int]:
    """One prediction per approved box; unannotated image regions are ignored."""
    if not 0 < min_iou <= 1:
        raise ValueError("min_iou must be within (0, 1]")
    if not labels:
        raise ValueError("no reviewed labels to score")
    used: set[int] = set()
    scored = Counter()
    for label in labels:
        hits = [(i, box_iou(label["bbox"], row["bbox"]))
                for i, row in enumerate(predictions) if i not in used]
        hits = [(i, overlap) for i, overlap in hits if overlap >= min_iou]
        if not hits:
            scored["missed_box"] += 1
            continue
        # Favor a same-class overlapping face; then rank by geometry.
        chosen, _ = max(hits, key=lambda item: (
            predictions[item[0]]["tile_id"] == label["tile_id"], item[1],
        ))
        used.add(chosen)
        if predictions[chosen]["tile_id"] == label["tile_id"]:
            scored["correct_tile"] += 1
        else:
            scored["wrong_or_unmapped_tile"] += 1
    return {name: scored[name] for name in
            ("correct_tile", "wrong_or_unmapped_tile", "missed_box")}


def run_reviewed_trial(
    root: str | Path, manifest_path: str | Path,
    *, infer: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    items = _labeled_images(root, Path(manifest_path))
    total = sum(len(entry["labels"]) for entry in items.values())
    result: dict[str, Any] = {
        "schema_version": "roboflow_reviewed_public_trial_v0_1",
        "model_id": MODEL_ID,
        "mode": "offline_integrity_only" if infer is None else "cloud_inference",
        "verified_public_images": len(items),
        "approved_face_labels": total,
        "source_groups": len({e["source_group"] for e in items.values()}),
        "model_calls": 0,
        "correct_tile": None,
        "wrong_or_unmapped_tile": None,
        "missed_box": None,
        "approved_box_tile_recall": None,
        "class_accuracy_given_box": None,
        "unmapped_source_classes": {},
        "overall_detection_precision": None,
        "source_disjoint_blind_holdout": False,
        "formal_promotion_evidence": False,
        "runtime_identity_ready": False,
        "safe_for_executor": False,
        "note": "Partial public annotations: no global precision; already-reviewed development sources.",
    }
    if infer is None:
        return result

    from PIL import Image  # optional Vision dependency, only cloud mode needs pixels

    totals: Counter[str] = Counter()
    unknown: Counter[str] = Counter()
    for entry in items.values():
        with Image.open(entry["absolute_path"]) as source:
            size = source.size
            source.verify()
        # Model output never enters the existing runtime detector or action stream.
        response = infer(str(entry["absolute_path"]))
        if not isinstance(response, dict) or not isinstance(response.get("predictions"), list):
            raise ValueError("model response must contain a predictions array")
        reported = response.get("image")
        if isinstance(reported, dict) and "width" in reported and "height" in reported:
            if (int(reported["width"]), int(reported["height"])) != size:
                raise ValueError("model response image size differs from verified input")
        parsed = [_parse_prediction(row, size) for row in response["predictions"]]
        unknown.update(row["raw_class"] for row in parsed if row["tile_id"] is None)
        totals.update(score_partial_labels(entry["labels"], parsed))
        result["model_calls"] += 1
    result.update({
        **{name: totals[name] for name in
           ("correct_tile", "wrong_or_unmapped_tile", "missed_box")},
        "unmapped_source_classes": dict(sorted(unknown.items())),
        "approved_box_tile_recall": round(totals["correct_tile"] / total, 5),
        "class_accuracy_given_box": (
            round(totals["correct_tile"] /
                  (totals["correct_tile"] + totals["wrong_or_unmapped_tile"]), 5)
            if totals["correct_tile"] + totals["wrong_or_unmapped_tile"] else None
        ),
    })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cloud", action="store_true",
                        help="Upload at most 12 ALREADY-PUBLIC screenshot files to Roboflow")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    manifest = (root / args.manifest).resolve()
    if not manifest.is_relative_to(root):
        parser.error("manifest must remain inside repository checkout")
    report_path = Path(args.output).resolve()
    if report_path.is_relative_to(root):
        parser.error("report must be outside public repository checkout")
    infer = None
    if args.cloud:
        api_key = os.environ.get("ROBOFLOW_API_KEY", "")
        if not api_key.strip():
            parser.error("ROBOFLOW_API_KEY environment variable is not configured")
        try:
            from inference_sdk import InferenceConfiguration, InferenceHTTPClient
        except ImportError:
            parser.error("install inference-sdk to run cloud mode")
        client = InferenceHTTPClient(api_url=API_URL, api_key=api_key).configure(
            InferenceConfiguration(api_key_transport="header")
        )
        infer = lambda file_path: client.infer(file_path, model_id=MODEL_ID)
    try:
        report = run_reviewed_trial(root, manifest, infer=infer)
    except Exception as exc:
        # Deliberately do not print SDK exception strings; some contain request data.
        if args.cloud:
            parser.exit(2, "Roboflow trial failed (" + type(exc).__name__
                        + "); inspect model access and source integrity.\n")
        raise
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "mode", "verified_public_images", "approved_face_labels", "model_calls",
        "correct_tile", "approved_box_tile_recall", "safe_for_executor",
    )}))


if __name__ == "__main__":
    main()
