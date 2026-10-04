"""Development-only group decoder for regular three-face exposed meld identity.

A regular exposed meld can only be a suited three-tile sequence or a triplet.
This decoder consumes per-face class scores from any identity backend (SIFT,
future learned model, etc.) and ranks only Mahjong-valid three-face identity
combinations.

It deliberately does not infer CHI/PENG as canonical action truth, does not
handle stacked KONG geometry, and never marks output safe for Runtime/Hint/
Executor.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations
import math
from typing import Mapping, Sequence

from workspace.vision.public_identity_labels import PUBLIC_STANDARD_CLASSES


@dataclass(frozen=True)
class PublicMeldGroupIdentityRanking:
    top_tiles: tuple[str, str, str] | None
    top_score: float | None
    runner_up_tiles: tuple[str, str, str] | None
    runner_up_score: float | None
    margin: float | None
    canonical_candidate_count: int
    development_proposal_tiles: tuple[str, str, str] | None
    issues: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_meld_group_identity_ranking_v0_1",
            "top_tiles": list(self.top_tiles) if self.top_tiles else None,
            "top_score": self.top_score,
            "runner_up_tiles": (
                list(self.runner_up_tiles) if self.runner_up_tiles else None
            ),
            "runner_up_score": self.runner_up_score,
            "margin": self.margin,
            "canonical_candidate_count": self.canonical_candidate_count,
            "development_proposal_tiles": (
                list(self.development_proposal_tiles)
                if self.development_proposal_tiles else None
            ),
            "action_kind": "UNKNOWN",
            "development_only": True,
            "changes_runtime_behavior": False,
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_hint": False,
            "safe_for_executor": False,
            "issues": list(self.issues),
        }


def _canonical_melds() -> tuple[tuple[str, tuple[str, str, str]], ...]:
    rows: list[tuple[str, tuple[str, str, str]]] = []
    for suit in ("M", "P", "S"):
        for start in range(1, 8):
            rows.append((
                f"sequence:{suit}{start}",
                (
                    f"{suit}{start}",
                    f"{suit}{start + 1}",
                    f"{suit}{start + 2}",
                ),
            ))
    for tile in sorted(PUBLIC_STANDARD_CLASSES):
        rows.append((f"triplet:{tile}", (tile, tile, tile)))
    return tuple(rows)


_CANONICAL_MELDS = _canonical_melds()


def rank_regular_public_meld_identity(
    face_scores: Sequence[Mapping[str, float]],
    *,
    minimum_group_margin: float | None = None,
    minimum_face_score: float | None = None,
) -> PublicMeldGroupIdentityRanking:
    """Rank valid sequence/triplet assignments for exactly three visible faces.

    face_scores[i] maps tile_id -> backend similarity for face i. Scores only
    need to be comparable within the supplied backend. Sequences are allowed in
    any on-screen order; the best permutation is retained for each canonical
    meld, so the runner-up is always a genuinely different meld identity rather
    than another permutation of the same three tiles.

    When no margin is supplied, this function is ranking-only and never emits a
    development proposal. Supplying a margin creates only a development
    proposal; Runtime remains forbidden.
    """
    if len(face_scores) != 3:
        raise ValueError("regular public meld identity requires exactly 3 faces")
    if minimum_group_margin is not None:
        if (
            isinstance(minimum_group_margin, bool)
            or not isinstance(minimum_group_margin, (int, float))
            or minimum_group_margin < 0
        ):
            raise ValueError("minimum_group_margin must be nonnegative")
        minimum_group_margin = float(minimum_group_margin)
    if minimum_face_score is not None:
        if (
            isinstance(minimum_face_score, bool)
            or not isinstance(minimum_face_score, (int, float))
        ):
            raise ValueError("minimum_face_score must be numeric")
        minimum_face_score = float(minimum_face_score)

    cleaned: list[dict[str, float]] = []
    for index, scores in enumerate(face_scores):
        row: dict[str, float] = {}
        for tile_id, raw_score in scores.items():
            if tile_id not in PUBLIC_STANDARD_CLASSES:
                continue
            if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)):
                continue
            score = float(raw_score)
            if not math.isfinite(score):
                continue
            row[tile_id] = score
        if not row:
            return PublicMeldGroupIdentityRanking(
                top_tiles=None,
                top_score=None,
                runner_up_tiles=None,
                runner_up_score=None,
                margin=None,
                canonical_candidate_count=0,
                development_proposal_tiles=None,
                issues=(f"face_{index}_has_no_valid_identity_scores",),
            )
        cleaned.append(row)

    candidates: list[tuple[float, str, tuple[str, str, str], tuple[float, ...]]] = []
    for canonical_id, canonical_tiles in _CANONICAL_MELDS:
        assignments = (
            {canonical_tiles}
            if len(set(canonical_tiles)) == 1
            else set(permutations(canonical_tiles))
        )
        best: tuple[float, tuple[str, str, str], tuple[float, ...]] | None = None
        for assignment in assignments:
            if not all(assignment[i] in cleaned[i] for i in range(3)):
                continue
            values = tuple(cleaned[i][assignment[i]] for i in range(3))
            mean_score = sum(values) / 3.0
            if best is None or mean_score > best[0]:
                best = (mean_score, assignment, values)
        if best is not None:
            candidates.append((best[0], canonical_id, best[1], best[2]))

    candidates.sort(key=lambda row: (-row[0], row[1], row[2]))
    if not candidates:
        return PublicMeldGroupIdentityRanking(
            top_tiles=None,
            top_score=None,
            runner_up_tiles=None,
            runner_up_score=None,
            margin=None,
            canonical_candidate_count=0,
            development_proposal_tiles=None,
            issues=("no_mahjong_valid_three_face_identity_combination",),
        )

    top_score, _top_id, top_tiles, top_face_scores = candidates[0]
    runner = candidates[1] if len(candidates) > 1 else None
    runner_score = runner[0] if runner else None
    margin = top_score - runner_score if runner_score is not None else None

    issues = ["mahjong_valid_group_identity_ranked"]
    proposal: tuple[str, str, str] | None = None
    if minimum_group_margin is None:
        issues.append("development_margin_gate_not_configured")
    else:
        margin_ok = margin is None or margin >= minimum_group_margin
        face_ok = (
            minimum_face_score is None
            or min(top_face_scores) >= minimum_face_score
        )
        if margin_ok and face_ok:
            proposal = top_tiles
            issues.append("development_group_identity_margin_passed")
        else:
            if not margin_ok:
                issues.append("development_group_identity_margin_too_small")
            if not face_ok:
                issues.append("development_group_identity_face_score_too_low")

    return PublicMeldGroupIdentityRanking(
        top_tiles=top_tiles,
        top_score=round(float(top_score), 8),
        runner_up_tiles=runner[2] if runner else None,
        runner_up_score=(
            round(float(runner_score), 8) if runner_score is not None else None
        ),
        margin=round(float(margin), 8) if margin is not None else None,
        canonical_candidate_count=len(candidates),
        development_proposal_tiles=proposal,
        issues=tuple(issues),
    )
