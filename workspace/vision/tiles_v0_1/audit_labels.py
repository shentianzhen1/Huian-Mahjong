"""Audit reviewed Vision labels without silently rewriting ground truth.

A human-reviewed label can still be wrong. This helper runs the same strict
leave-session-out/same-region evaluator used for the real baseline and surfaces
labels that deserve another visual review:

- predicted class disagrees with the reviewed class;
- confidence is below a review threshold;
- a class/region is unscorable because it lacks an independent source session.

It never edits labels and is never an Executor gate.
"""
import argparse
import json
from pathlib import Path

from .evaluate_tiles import evaluate_template_dataset


def audit_labels(dataset_root, *, review_confidence=0.80):
    if isinstance(review_confidence, bool) or not isinstance(
        review_confidence, (int, float)
    ):
        raise ValueError("review_confidence must be numeric")
    if not 0 <= review_confidence <= 1:
        raise ValueError("review_confidence must be between 0 and 1")

    report = evaluate_template_dataset(
        dataset_root,
        confidence_threshold=review_confidence,
        template_scope="same_region",
    )

    review = []
    for row in report["predictions"]:
        reasons = []
        if not row["correct"]:
            reasons.append("model_disagrees_with_label")
        if row["confidence"] < review_confidence:
            reasons.append("low_holdout_confidence")
        if reasons:
            review.append({
                "group": row["group"],
                "image": row["image"],
                "region": row["region"],
                "reviewed_tile": row["true_tile"],
                "holdout_prediction": row["predicted_tile"],
                "confidence": row["confidence"],
                "reasons": reasons,
            })

    for row in report["unscorable"]:
        review.append({
            "group": row["group"],
            "image": row["image"],
            "region": row["region"],
            "reviewed_tile": row["tile_id"],
            "holdout_prediction": None,
            "confidence": None,
            "reasons": ["needs_independent_source_coverage"],
        })

    disagreement_count = sum(
        "model_disagrees_with_label" in row["reasons"] for row in review
    )
    low_confidence_count = sum(
        "low_holdout_confidence" in row["reasons"] for row in review
    )
    coverage_count = sum(
        "needs_independent_source_coverage" in row["reasons"] for row in review
    )

    return {
        "method": "human_label_review_queue_from_strict_holdout",
        "review_confidence": float(review_confidence),
        "approved_labels": report["total_approved_labels"],
        "scorable_labels": report["scorable_labels"],
        "exact_accuracy": report["exact_accuracy"],
        "accepted_accuracy": report["accepted_accuracy"],
        "review_queue_size": len(review),
        "model_disagreements": disagreement_count,
        "low_confidence_items": low_confidence_count,
        "coverage_items": coverage_count,
        "review_queue": review,
        "auto_corrections": 0,
        "safe_for_executor": False,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Build a human-review queue for Tiles V0.1 labels")
    parser.add_argument("--dataset", default="dataset/tiles_v0_1")
    parser.add_argument("--confidence", type=float, default=0.80)
    parser.add_argument("--output")
    args = parser.parse_args()

    report = audit_labels(
        args.dataset, review_confidence=args.confidence
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
