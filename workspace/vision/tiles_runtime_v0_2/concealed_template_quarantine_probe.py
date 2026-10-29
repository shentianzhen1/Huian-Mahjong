"""Development-only audit for exact concealed-template quarantine candidates.

This helper deliberately does not mutate labels or Runtime behavior.  It can
remove one or more exact reviewed asset paths from an in-memory training bank
and re-run the existing leave-source-session-out diagnostic.  Storage session
separation is only a development regression check; it is not independent
original-match promotion evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path


CONCEALED_REGIONS = frozenset({"hand_region", "draw_region", "draw_visual"})


def concealed_labels(labels):
    return tuple(
        row for row in labels
        if row.get("region") in CONCEALED_REGIONS
        and not row.get("gold_skin_only")
    )


def filter_exact_images(labels, candidate_images):
    """Return labels excluding only exact candidate image paths."""
    candidates = frozenset(str(value).replace("\\", "/") for value in candidate_images)
    return tuple(
        row for row in labels
        if str(row.get("image", "")).replace("\\", "/") not in candidates
    )


def support_summary(labels, candidate_images=()):
    before = concealed_labels(labels)
    after = filter_exact_images(before, candidate_images)
    before_counts = Counter(row["tile_id"] for row in before)
    after_counts = Counter(row["tile_id"] for row in after)
    return {
        "concealed_label_count_before": len(before),
        "concealed_label_count_after": len(after),
        "removed_label_count": len(before) - len(after),
        "class_count_before": len(before_counts),
        "class_count_after": len(after_counts),
        "classes_losing_all_support": sorted(
            tile_id for tile_id in before_counts if not after_counts[tile_id]
        ),
        "support_before": dict(sorted(before_counts.items())),
        "support_after": dict(sorted(after_counts.items())),
    }


def leave_source_session_out(dataset_root, candidate_images=()):
    """Run the existing template path with exact candidates omitted in memory.

    The result is diagnostic only.  `source_session` is explicitly not an
    independence key and these numbers must not be used for formal promotion.
    Vision dependencies stay lazy so core tests do not require OpenCV/Pillow.
    """
    from workspace.vision.tiles_v0_1.evaluate_tiles import _crop_label, _group_key
    from workspace.vision.tiles_v0_1.labels import approved_labels
    from workspace.vision.tiles_v0_1.template_classifier import TemplateTileClassifier

    root = Path(dataset_root)
    labels = concealed_labels(approved_labels(root))
    groups = defaultdict(list)
    for row in labels:
        groups[_group_key(row)].append(row)

    predictions = []
    unscorable = []
    for held_out, test_labels in sorted(groups.items()):
        train_labels = filter_exact_images(
            (row for row in labels if _group_key(row) != held_out),
            candidate_images,
        )
        train_classes = {row["tile_id"] for row in train_labels}
        if not train_classes:
            continue
        classifier = TemplateTileClassifier.from_labels(root, train_labels)
        for row in test_labels:
            if row["tile_id"] not in train_classes:
                unscorable.append({
                    "group": held_out,
                    "image": row["image"],
                    "tile_id": row["tile_id"],
                    "reason": "true_class_missing_outside_holdout_group",
                })
                continue
            prediction = classifier.classify(_crop_label(root, row), region=None)
            predictions.append({
                "group": held_out,
                "image": row["image"],
                "true_tile": row["tile_id"],
                "predicted_tile": prediction.tile_id,
                "confidence": prediction.confidence,
                "correct": prediction.tile_id == row["tile_id"],
            })

    correct = sum(row["correct"] for row in predictions)
    confusion = Counter(
        (row["true_tile"], row["predicted_tile"])
        for row in predictions if not row["correct"]
    )
    return {
        "schema_version": "concealed_template_quarantine_probe_v0_1",
        "method": "leave_source_session_out_concealed_identity",
        "source_session_is_independence_evidence": False,
        "formal_promotion_evidence": False,
        "candidate_images": sorted(str(value).replace("\\", "/") for value in candidate_images),
        "support": support_summary(labels, candidate_images),
        "scorable": len(predictions),
        "correct": correct,
        "accuracy": correct / len(predictions) if predictions else None,
        "unscorable": len(unscorable),
        "confusions": {
            f"{truth}->{predicted}": count
            for (truth, predicted), count in sorted(confusion.items())
        },
        "predictions": predictions,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", default="dataset/tiles_runtime_v0_2")
    parser.add_argument("--candidate-image", action="append", default=[])
    parser.add_argument("--output")
    args = parser.parse_args()
    report = leave_source_session_out(args.dataset_root, args.candidate_image)
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
