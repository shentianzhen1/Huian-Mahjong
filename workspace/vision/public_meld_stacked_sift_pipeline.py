"""Offline reviewed-crop SIFT -> STACKED decoder; no automatic splitter.

Readable-face reviews are caller-supplied evidence, not classifier outputs.
Tile backs/occlusions never enter a standard 34-class tile scorer.
"""
from __future__ import annotations

from typing import Any, Mapping

from workspace.vision.public_meld_identity_sift import (
    PublicMeldSiftBank,
    rank_public_meld_sift,
)
from workspace.vision.public_meld_stacked_identity_decoder import (
    VISIBLE_ROLES,
    rank_stacked_visible_identity,
)


def score_reviewed_stacked_faces(
    faces: Mapping[str, Any],
    *,
    bank: PublicMeldSiftBank,
    source_session: str,
    source_sha256: str,
    source_frame_verified: bool,
    readable_face_review: Mapping[str, bool],
) -> dict:
    """Score only a complete reviewed readable-face packet under frozen SIFT.

Caller must bind crops to decoded source pixels and preserve frame/crop
lineage. This function verifies registered source SHA and role/review gates,
then uses the unchanged scorer with >=2 other original-match groups.
There is no production confidence threshold or physical-identity acceptance.
    """
    source = bank.sources.get(source_session)
    issues = []
    if source is None or source.source_sha256 != source_sha256:
        issues.append("query_source_session_or_sha_conflict")
    if source_frame_verified is not True:
        issues.append("source_frame_unverified")
    if set(faces) != set(VISIBLE_ROLES) or set(readable_face_review) != set(VISIBLE_ROLES):
        issues.append("exact_three_visible_roles_required")
    elif any(readable_face_review[role] is not True for role in VISIBLE_ROLES):
        issues.append("one_or_more_visible_faces_unreadable_or_unreviewed")

    rankings = {}
    if not issues:
        for role in VISIBLE_ROLES:
            rankings[role] = rank_public_meld_sift(
                bank, faces[role], source_session=source_session,
                source_sha256=source_sha256, minimum_other_match_groups=2,
                include_class_scores=True,
            )
    decoded = rank_stacked_visible_identity(
        {role: ranking["class_scores"] for role, ranking in rankings.items()},
        source_frame_verified=not issues,
        visible_faces_reviewed=not issues,
    )
    return {
        "schema_version": "public_meld_stacked_reviewed_sift_pipeline_dev_v0_1",
        "source_session": source_session,
        "source_sha256": source_sha256,
        "source_match_group": source.match_group if source else None,
        "readable_face_review": dict(readable_face_review),
        "minimum_other_match_groups": 2,
        "face_rankings": rankings,
        "decoder": decoded,
        "issues": issues,
        "automatic_splitter": False,
        "development_only": True,
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }
