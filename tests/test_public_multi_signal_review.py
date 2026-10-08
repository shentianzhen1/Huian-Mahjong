"""Synthetic fail-closed tests for the #69 multi-signal temporal gate."""
from dataclasses import replace

from workspace.vision.public_dual_region_transition import DualRegionSourceReview
from workspace.vision.public_independent_hand_count import HandCountTransition
from workspace.vision.public_wall_counter import WallCounterTransition
from workspace.vision.public_multi_signal_review import review_multi_signal_window


def evidence():
    dual = DualRegionSourceReview(
        "SYNCHRONIZED_TWO_REGION_APPEARANCE_CANDIDATE_ONLY",
        "source_reviewed", 20, 21, 3)
    hand = HandCountTransition(
        "INDEPENDENT_HAND_COUNT_DELTA_CANDIDATE_ONLY",
        "stable", 13, 11, -2, (22, 23))
    wall = WallCounterTransition(
        "WALL_COUNT_DECREASE_AUXILIARY_ONLY",
        "stable", 73, 72, -1, (25, 26))
    return dual, hand, wall


def test_independent_three_signal_candidate_is_not_action():
    result = review_multi_signal_window(
        *evidence(), same_original_source_epoch_independently_verified=True,
        hand_roi_distinct_from_lower_meld_roi=True,
        wall_roi_distinct_from_both=True,
        explicit_review_window=(19, 27))
    assert result.status == "MULTI_SIGNAL_OWNER_REVIEW_CANDIDATE_ONLY"
    assert result.hand_delta == -2 and result.wall_delta == -1
    assert result.to_dict()["action_kind"] == "UNKNOWN"
    assert result.to_dict()["verified_real_video_event"] is False


def test_missing_wall_is_optional_but_cannot_be_claimed():
    dual, hand, _ = evidence()
    kwargs = dict(
        same_original_source_epoch_independently_verified=True,
        hand_roi_distinct_from_lower_meld_roi=True,
        wall_roi_distinct_from_both=False,
        explicit_review_window=(19, 27))
    result = review_multi_signal_window(dual, hand, None, **kwargs)
    assert result.status == "MULTI_SIGNAL_OWNER_REVIEW_CANDIDATE_ONLY"
    assert result.wall_delta is None
    assert review_multi_signal_window(
        dual, hand, None, wall_required=True, **kwargs).status == "UNKNOWN"


def test_missing_dual_region_or_hand_abstains():
    dual, hand, wall = evidence()
    for d, h in (
        (replace(dual, status="UNKNOWN"), hand),
        (dual, replace(hand, status="UNKNOWN")),
        (dual, replace(hand, delta=1)),
    ):
        assert review_multi_signal_window(
            d, h, wall,
            same_original_source_epoch_independently_verified=True,
            hand_roi_distinct_from_lower_meld_roi=True,
            wall_roi_distinct_from_both=True,
            explicit_review_window=(19, 27)).status == "UNKNOWN"


def test_source_roi_and_temporal_conflicts_abstain():
    dual, hand, wall = evidence()
    base = dict(
        same_original_source_epoch_independently_verified=True,
        hand_roi_distinct_from_lower_meld_roi=True,
        wall_roi_distinct_from_both=True,
        explicit_review_window=(19, 27))
    for change in (
        {"same_original_source_epoch_independently_verified": False},
        {"hand_roi_distinct_from_lower_meld_roi": False},
        {"wall_roi_distinct_from_both": False},
        {"explicit_review_window": (20, 24)},
        {"explicit_review_window": (22, 27)},
    ):
        assert review_multi_signal_window(
            dual, hand, wall, **(base | change)).status == "UNKNOWN"
