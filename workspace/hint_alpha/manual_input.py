"""User-entered Alpha observations, separate from Vision and rule settlement.

Manual values can unlock ordinary structural shanten after the same physical
checks. They are never machine-recognition evidence or official rule results.
"""
from __future__ import annotations

from numbers import Integral

from huian.rules.dealer_base import MATCH_TOTAL_SCORE
from huian.rules.config import EvidenceStatus
from huian.rules.registry import DEFAULT_RULE_SNAPSHOT, RuleDomain
from workspace.vision.current_state_snapshot import CurrentTableSnapshot
from .current_snapshot_advisor import analyze_snapshot_shanten


def manual_snapshot(*, session_id, revision, captured, hand, gold_tile, own_meld_count):
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("manual session ID required")
    if isinstance(revision, bool) or not isinstance(revision, Integral) or revision < 0:
        raise ValueError("manual revision must be nonnegative")
    if (isinstance(own_meld_count, bool) or not isinstance(own_meld_count, Integral)
            or not 0 <= own_meld_count <= 5):
        raise ValueError("own meld count must be 0..5")
    if not isinstance(hand, (tuple, list)):
        raise ValueError("hand must be an explicit tile sequence")
    return CurrentTableSnapshot(
        timestamp_seconds=captured,
        source_session="manual:" + session_id,
        stream_epoch=revision,
        stable_frames=0,
        own_hand=tuple(hand),
        gold_tile=gold_tile,
        rivers=((), ()),
        # Only the count is asserted. Do not invent a PENG/CHI/KONG shape.
        melds=(tuple((None,) for _ in range(own_meld_count)), ()),
        hand_trusted=bool(hand) and all(tile is not None for tile in hand),
        gold_trusted=gold_tile is not None,
        river_trusted=(False, False),
        meld_trusted=(True, False),
        adapter_issues=("user_entered_unverified",),
        input_source="user_entered",
    )


def evaluate_manual_input(**kwargs):
    snapshot = manual_snapshot(**kwargs)
    return snapshot, analyze_snapshot_shanten(snapshot)


def observed_score_entry(*, scores_before, scores_after, unresolved_rule_id):
    """Validate a user's transcription; do not calculate or book a settlement."""
    if not isinstance(unresolved_rule_id, str) or not unresolved_rule_id.strip():
        raise ValueError("an unresolved rule ID is required")
    rule_id = unresolved_rule_id.strip()
    try:
        rule = DEFAULT_RULE_SNAPSHOT.get(rule_id)
    except KeyError as exc:
        raise ValueError("rule ID is not in the current RuleSnapshot") from exc
    if rule.domain != RuleDomain.SETTLEMENT or rule.status == EvidenceStatus.CONFIRMED:
        raise ValueError("rule ID must be an unconfirmed settlement rule")
    pairs = []
    for name, pair in (("before", scores_before), ("after", scores_after)):
        if (not isinstance(pair, (tuple, list)) or len(pair) != 2
                or any(isinstance(x, bool) or not isinstance(x, Integral)
                       or not 0 <= x <= MATCH_TOTAL_SCORE for x in pair)
                or sum(pair) != MATCH_TOTAL_SCORE):
            raise ValueError(f"{name} scores must conserve {MATCH_TOTAL_SCORE}")
        pairs.append(tuple(pair))
    before, after = pairs
    delta = (after[0] - before[0], after[1] - before[1])
    if sum(delta) != 0:
        raise ValueError("score change must be zero-sum")
    return {
        "status": "OBSERVED_ONLY",
        "input_source": "USER_ENTERED_UNVERIFIED",
        "scores_before": list(before),
        "scores_after": list(after),
        "score_delta": list(delta),
        "unresolved_rule_ids": [rule_id],
        "automatic_settlement": False,
        "confirmed_rule_evidence": False,
        "official_ai_reward_eligible": False,
        "safe_for_executor": False,
    }
