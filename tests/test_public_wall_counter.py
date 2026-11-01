"""Synthetic controls for source-scoped auxiliary wall counter."""
from dataclasses import replace

from workspace.vision.public_wall_counter import (
    WallCounterFrame, review_wall_counter_transition,
)


def frames():
    return [
        WallCounterFrame("session", "a" * 64, 0, n,
                         73 if n < 3 else 72, True, True, True, True)
        for n in range(6)
    ]


def test_stable_73_to_72_is_auxiliary_not_a_draw():
    result = review_wall_counter_transition(frames(), boundary_frame=3)
    assert result.status == "WALL_COUNT_DECREASE_AUXILIARY_ONLY"
    assert result.delta == -1
    assert result.to_dict()["actor"] == "UNKNOWN"
    assert result.to_dict()["draw_event"] == "UNKNOWN"


def test_ambiguous_ocr_and_animation_abstain():
    for change in ({"count": None}, {"animation_free": False},
                   {"counter_visible": False},
                   {"independent_counter_roi_verified": False}):
        sample = frames()
        sample[2] = replace(sample[2], **change)
        assert review_wall_counter_transition(sample, boundary_frame=3).status == "UNKNOWN"


def test_source_frame_and_epoch_changes_abstain():
    for change in ({"source_sha256": "b" * 64}, {"epoch": 1},
                   {"frame": 99}):
        sample = frames()
        sample[3] = replace(sample[3], **change)
        assert review_wall_counter_transition(sample, boundary_frame=3).status == "UNKNOWN"


def test_no_decrease_or_increase_abstain():
    for after in (73, 74):
        sample = [replace(f, count=73 if f.frame < 3 else after)
                  for f in frames()]
        assert review_wall_counter_transition(sample, boundary_frame=3).status == "UNKNOWN"


def test_unstable_or_short_plateau_abstains():
    sample = frames()
    sample[1] = replace(sample[1], count=72)
    assert review_wall_counter_transition(sample, boundary_frame=3).status == "UNKNOWN"
    assert review_wall_counter_transition(frames(), boundary_frame=4).status == "UNKNOWN"
    assert review_wall_counter_transition(frames(), boundary_frame=3, stable_frames=2).status == "UNKNOWN"
