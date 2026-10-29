"""Synthetic negative controls for the #69 independent hand-count gate."""
from dataclasses import replace

from workspace.vision.public_independent_hand_count import (
    HandCountFrame, review_independent_hand_count,
)

SHA = "a" * 64


def sample():
    return [
        HandCountFrame("session", SHA, 0, n, "lower",
                       13 if n < 3 else 11, True, True, True, True, True)
        for n in range(6)
    ]


def test_stable_independent_delta_is_not_an_action():
    result = review_independent_hand_count(sample(), transition_after_frame=3)
    assert result.status == "INDEPENDENT_HAND_COUNT_DELTA_CANDIDATE_ONLY"
    assert result.delta == -2
    assert result.to_dict()["action_kind"] == "UNKNOWN"
    assert result.to_dict()["safe_for_executor"] is False


def test_shading_or_animation_cannot_supply_hand_evidence():
    frames = sample()
    frames[2] = replace(frames[2], animation_free=False)
    assert review_independent_hand_count(frames, transition_after_frame=3).status == "UNKNOWN"


def test_draw_region_must_be_separate():
    frames = sample()
    frames[4] = replace(frames[4], draw_region_separately_counted=False)
    assert review_independent_hand_count(frames, transition_after_frame=3).status == "UNKNOWN"


def test_epoch_and_frame_discontinuity_fail_closed():
    for change in ({"epoch": 1}, {"frame": 99}, {"source_sha256": "b" * 64}):
        frames = sample()
        frames[3] = replace(frames[3], **change)
        assert review_independent_hand_count(frames, transition_after_frame=3).status == "UNKNOWN"


def test_unstable_plateau_and_no_change_abstain():
    frames = sample()
    frames[1] = replace(frames[1], count=12)
    assert review_independent_hand_count(frames, transition_after_frame=3).status == "UNKNOWN"
    frames = [replace(f, count=13) for f in sample()]
    assert review_independent_hand_count(frames, transition_after_frame=3).status == "UNKNOWN"


def test_no_short_stability_or_missing_boundary():
    assert review_independent_hand_count(sample(), transition_after_frame=3, stable_frames=2).status == "UNKNOWN"
    assert review_independent_hand_count(sample(), transition_after_frame=4).status == "UNKNOWN"
