"""Offline ranking for three reviewed visible faces of a STACKED group.

Inputs must already be source-qualified, separately reviewed face scores. This
module does not cut images or infer the identity of an occluded fourth tile.
Backend scores are similarities, never Runtime confidence. No caller in the
Runtime identity bridge uses this development experiment.
"""
from __future__ import annotations

import math
from typing import Mapping

from workspace.vision.public_identity_labels import PUBLIC_STANDARD_CLASSES


VISIBLE_ROLES = ("top", "lower_left", "lower_right")


def rank_stacked_visible_identity(
    face_scores: Mapping[str, Mapping[str, float]],
    *,
    source_frame_verified: bool,
    visible_faces_reviewed: bool,
) -> dict:
    """Compare same-tile hypotheses without turning agreement into acceptance.

Every hypothesis needs a finite score on all three distinct visible faces.
Individual winners remain in the report so a group constraint cannot silently
hide a disagreeing face. Even unanimous winners leave all four physical tile
identities UNKNOWN. Source lineage remains the upstream scorer's responsibility.
    """
    report = {
        "schema_version": "public_meld_stacked_visible_identity_ranking_dev_v0_1",
        "visible_face_roles": list(VISIBLE_ROLES),
        "visible_face_count": 3,
        "physical_tile_count": 4,
        "physical_tile_ids": ["UNKNOWN"] * 4,
        "occluded_face_identity": "UNKNOWN",
        "face_top1": {},
        "same_tile_hypotheses": [],
        "top_tile": None,
        "margin": None,
        "visible_top1_agreement": False,
        "action_kind": "UNKNOWN",
        "development_only": True,
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
        "issues": [],
    }
    if source_frame_verified is not True or visible_faces_reviewed is not True:
        report["issues"].append("source_or_visible_face_review_missing")
        return report
    if set(face_scores) != set(VISIBLE_ROLES):
        report["issues"].append("exact_three_visible_roles_required")
        return report

    cleaned = {}
    for role in VISIBLE_ROLES:
        row = {}
        for tile, value in face_scores[role].items():
            if (tile in PUBLIC_STANDARD_CLASSES
                    and not isinstance(value, bool)
                    and isinstance(value, (int, float))
                    and math.isfinite(value)):
                row[tile] = float(value)
        if not row:
            report["issues"].append(f"{role}_has_no_valid_identity_scores")
            return report
        cleaned[role] = row
        ranked = sorted(row, key=lambda tile: (-row[tile], tile))
        # A tied best score is ambiguous, even if deterministic sorting picks one.
        report["face_top1"][role] = (
            ranked[0] if len(ranked) == 1 or row[ranked[0]] > row[ranked[1]] else None
        )

    common = set.intersection(*(set(row) for row in cleaned.values()))
    hypotheses = []
    for tile in common:
        scores = [cleaned[role][tile] for role in VISIBLE_ROLES]
        hypotheses.append({
            "tile": tile,
            "mean_score": sum(value / 3.0 for value in scores),
            "minimum_face_score": min(scores),
            "face_scores": dict(zip(VISIBLE_ROLES, scores)),
        })
    hypotheses.sort(key=lambda row: (-row["mean_score"], row["tile"]))
    report["same_tile_hypotheses"] = hypotheses
    if not hypotheses:
        report["issues"].append("no_same_tile_hypothesis_supported_by_all_visible_faces")
        return report
    report["top_tile"] = hypotheses[0]["tile"]
    if len(hypotheses) > 1:
        report["margin"] = hypotheses[0]["mean_score"] - hypotheses[1]["mean_score"]
    winners = tuple(report["face_top1"].values())
    report["visible_top1_agreement"] = (
        all(tile == report["top_tile"] for tile in winners)
        and (report["margin"] is None or report["margin"] > 0)
    )
    if not report["visible_top1_agreement"]:
        report["issues"].append("visible_face_winners_conflict_or_tie")
    if len(hypotheses) < 2:
        report["issues"].append("insufficient_competing_same_tile_hypotheses")
    report["issues"].append("ranking_only_occluded_identity_unknown")
    return report
