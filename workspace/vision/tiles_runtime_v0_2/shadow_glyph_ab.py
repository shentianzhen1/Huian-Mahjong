"""Development-only raw A/B for the shadow glyph-mask identity feature.

The glyph-mask NCC score is not calibrated to the production template score,
so this evaluator intentionally reports raw Top-1 and confusion structure only.
It must not use the Runtime 0.82 threshold as an acceptance metric.

`source_session` leave-one-out is a historical regression diagnostic, not proof
of independent original matches.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path

from workspace.vision.tiles_runtime_v0_2.concealed_shadow_appearance_probe import (
    shadow_glyph_mask_feature,
)
from workspace.vision.tiles_runtime_v0_2.template_preprocess_ab import (
    SampleResult,
    baseline_feature,
    evaluate_feature,
)


def _raw_summary(results: list[SampleResult]) -> dict[str, object]:
    scorable = [row for row in results if row.predicted is not None]
    correct = sum(row.correct for row in scorable)
    confusions = Counter(
        f"{row.truth}->{row.predicted}"
        for row in scorable
        if not row.correct
    )
    return {
        "total": len(results),
        "scorable": len(scorable),
        "raw_correct": correct,
        "raw_accuracy": correct / len(scorable) if scorable else 0.0,
        "confusions": dict(
            sorted(confusions.items(), key=lambda item: (-item[1], item[0]))
        ),
    }


def build_shadow_glyph_ab_report(dataset_root: str | Path) -> dict[str, object]:
    report: dict[str, object] = {
        "schema_version": "concealed_shadow_glyph_raw_ab_v0_1",
        "development_only": True,
        "runtime_changed": False,
        "source_session_is_independent_match_evidence": False,
        "candidate_score_calibrated_to_runtime_confidence": False,
        "runtime_threshold_metrics_valid_for_candidate": False,
        "purpose": (
            "Check whether glyph-mask invariance destroys ordinary class "
            "separability before spending effort on a shadow-specific bank."
        ),
        "modes": {},
    }
    for mode_name, pooled in (("pooled_concealed", True), ("same_region", False)):
        baseline = evaluate_feature(
            dataset_root, baseline_feature, pooled_concealed=pooled
        )
        glyph = evaluate_feature(
            dataset_root, shadow_glyph_mask_feature, pooled_concealed=pooled
        )
        baseline_keys = [row.sample_key for row in baseline]
        glyph_keys = [row.sample_key for row in glyph]
        if baseline_keys != glyph_keys:
            raise AssertionError("baseline and glyph candidate must use identical queries")
        report["modes"][mode_name] = {
            "same_query_count": len(baseline_keys),
            "baseline_raw": _raw_summary(baseline),
            "glyph_raw": _raw_summary(glyph),
        }
    return report


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    args = parser.parse_args()
    print(json.dumps(build_shadow_glyph_ab_report(args.dataset), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
