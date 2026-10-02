"""Synthetic slot-level controls for dense river N -> N+1 detection."""
import hashlib
from dataclasses import replace

import pytest

# This module is pytest-only. Core installs skip it; the dedicated Vision job
# installs and executes it with real numpy/OpenCV instead of reporting a false pass.
np = pytest.importorskip("numpy")
pytest.importorskip("cv2")

from workspace.vision.public_dense_river_slots import (
    DenseRiverMaskFrame,
    DenseRiverPrefixGrowth,
    DenseRiverSlotProfile,
    audit_dense_river_stable_masks,
    audit_dense_river_prefix_sequence,
    dense_river_delta_to_transition_fact,
    dense_river_prefix_growth_to_transition_fact,
    probe_anchor_local_river_growth,
    probe_anchor_local_river_prefix_growth,
    probe_dense_river_count_delta,
    source_scoped_dense_river_mask,
)
from workspace.vision.public_meld_gap_onset import SourceScopedOpticalFrame

SHA = "a" * 64
PROFILE = DenseRiverSlotProfile(
    "player",
    ((.10, .20, .10, .20), (.20, .20, .10, .20), (.30, .20, .10, .20)),
)


def test_continuous_prefix_sequence_is_candidate_only_and_reappearance_abstains():
    masks = (
        [(False, False, False)] * 3
        + [(True, False, False)] * 3
        + [(False, False, False)] * 3
        + [(True, False, False)] * 3
        + [(True, True, False)] * 3
    )
    frames = tuple(DenseRiverMaskFrame("hand-01", SHA, 0, index, mask, True)
                   for index, mask in enumerate(masks))
    result = audit_dense_river_prefix_sequence(
        frames, profile=PROFILE, slots_independently_reviewed=True,
    )
    assert result.candidate_prefix_growth == ((3, 0, 1), (12, 1, 2))
    assert result.suppressed_reappearances == 1
    assert result.to_dict()["actual_actions_emitted"] == 0
    assert result.to_dict()["formal_accuracy_eligible"] is False
    assert audit_dense_river_prefix_sequence(
        (frames[0], *frames[2:]), profile=PROFILE,
        slots_independently_reviewed=True,
    ).status == "UNKNOWN"
    assert audit_dense_river_prefix_sequence(
        frames, profile=PROFILE, slots_independently_reviewed=False,
    ).status == "UNKNOWN"


def pixels(mask):
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    image[:, :] = (45, 85, 45)
    for occupied, slot in zip(mask, PROFILE.slots):
        if occupied:
            x, y, width, height = (round(value * 100) for value in slot)
            image[y:y + height, x:x + width] = (235, 235, 235)
    return image


def frame(index, mask, **changes):
    image = pixels(mask)
    base = SourceScopedOpticalFrame(
        source_session="hand-01",
        source_sha256=SHA,
        stream_epoch=0,
        frame_index=index,
        decoded_pixel_sha256=hashlib.sha256(image.tobytes()).hexdigest(),
        bgr_pixels=image,
        original_video_sha_verified=True,
        original_decoded_frame_verified=True,
    )
    return replace(base, **changes)


def run(before_mask=(True, False, False), after_mask=(True, True, False), **changes):
    before = tuple(frame(index, before_mask) for index in range(10, 13))
    after = tuple(frame(index, after_mask) for index in range(20, 23))
    kwargs = dict(
        profile=PROFILE,
        river_slots_independently_verified=True,
        windows_unobscured=True,
        intervening_frames_continuously_reviewed=True,
    )
    kwargs.update(changes)
    return probe_dense_river_count_delta(before, after, **kwargs)


def test_exactly_one_new_dense_slot_emits_count_candidate_only():
    result = run()
    assert result.status == "DENSE_RIVER_COUNT_DELTA_CANDIDATE_ONLY"
    assert (result.before_count, result.after_count, result.delta) == (1, 2, 1)
    data = result.to_dict()
    assert data["tile_identity"] == "UNKNOWN"
    assert data["actual_action_kind"] == "UNKNOWN"
    assert data["actual_actor"] == "UNKNOWN"
    assert data["raw_observation_emitted"] is False
    assert data["safe_for_executor"] is False
    assert SHA not in repr(data)
    assert "hand-01" not in repr(data)


def test_delta_adapts_to_review_candidate_not_runtime_observation():
    fact = dense_river_delta_to_transition_fact(run())
    assert fact is not None
    assert fact.channel == "river"
    assert fact.status == "PUBLIC_TRANSITION_CANDIDATE_ONLY"
    assert dense_river_delta_to_transition_fact(
        replace(run(), status="UNKNOWN")
    ) is None


def test_unchanged_two_appeared_or_disappeared_slots_fail_closed():
    cases = (
        ((True, False, False), (True, False, False)),
        ((False, False, False), (True, True, False)),
        ((True, True, False), (False, True, True)),
    )
    for before, after in cases:
        assert run(before, after).reason == (
            "not_exactly_one_stable_empty_to_occupied_slot"
        )


def test_intermediate_paper_fraction_is_ambiguous_not_empty():
    before = [frame(index, (True, False, False)) for index in range(10, 13)]
    ambiguous = pixels((True, False, False))
    ambiguous[25:33, 22:25] = 235
    after = [frame(index, (True, True, False)) for index in range(20, 23)]
    before[1] = replace(
        before[1], bgr_pixels=ambiguous,
        decoded_pixel_sha256=hashlib.sha256(ambiguous.tobytes()).hexdigest(),
    )
    result = probe_dense_river_count_delta(
        before, after, profile=PROFILE,
        river_slots_independently_verified=True,
        windows_unobscured=True,
        intervening_frames_continuously_reviewed=True,
    )
    assert result.reason == "ambiguous_slot_occupancy"


def test_unstable_slot_mask_fails_closed():
    before = tuple(frame(index, (True, False, False)) for index in range(10, 13))
    after = (
        frame(20, (True, True, False)),
        frame(21, (True, False, False)),
        frame(22, (True, True, False)),
    )
    result = probe_dense_river_count_delta(
        before, after, profile=PROFILE,
        river_slots_independently_verified=True,
        windows_unobscured=True,
        intervening_frames_continuously_reviewed=True,
    )
    assert result.reason == "unstable_dense_river_slot_mask"


def test_mixed_source_epoch_resolution_or_invalid_hash_fails_closed():
    before = tuple(frame(index, (True, False, False)) for index in range(10, 13))
    after = list(frame(index, (True, True, False)) for index in range(20, 23))
    for changed in (
        replace(after[0], source_session="hand-02"),
        replace(after[0], source_sha256="b" * 64),
        replace(after[0], stream_epoch=1),
        replace(after[0], bgr_pixels=np.zeros((101, 100, 3), dtype=np.uint8)),
    ):
        trial = [changed, *after[1:]]
        result = probe_dense_river_count_delta(
            before, trial, profile=PROFILE,
            river_slots_independently_verified=True,
            windows_unobscured=True,
            intervening_frames_continuously_reviewed=True,
        )
        assert result.status == "UNKNOWN"


def test_unverified_slots_occlusion_or_interval_fail_closed():
    flags = (
        {"river_slots_independently_verified": False},
        {"windows_unobscured": False},
        {"intervening_frames_continuously_reviewed": False},
    )
    for change in flags:
        assert run(**change).reason == "river_slots_or_source_interval_unverified"


def test_long_verified_overlay_gap_can_bridge_two_clear_stable_windows():
    before = tuple(frame(index, (True, False, False))
                   for index in range(10, 13))
    after = tuple(frame(index, (True, True, False))
                  for index in range(100, 103))
    options = dict(
        profile=PROFILE,
        river_slots_independently_verified=True,
        windows_unobscured=True,
        intervening_frames_continuously_reviewed=True,
    )
    result = probe_dense_river_count_delta(before, after, **options)
    assert result.status == "DENSE_RIVER_COUNT_DELTA_CANDIDATE_ONLY"
    assert result.first_stable_after_frame == 100
    options["intervening_frames_continuously_reviewed"] = False
    assert probe_dense_river_count_delta(
        before, after, **options,
    ).status == "UNKNOWN"


def test_gapped_stable_window_reverse_order_and_too_few_frames_fail_closed():
    before = tuple(frame(index, (True, False, False)) for index in (10, 12, 13))
    after = tuple(frame(index, (True, True, False)) for index in range(20, 23))
    kwargs = dict(
        profile=PROFILE, river_slots_independently_verified=True,
        windows_unobscured=True, intervening_frames_continuously_reviewed=True,
    )
    assert probe_dense_river_count_delta(before, after, **kwargs).reason == (
        "stable_window_frames_not_adjacent"
    )
    contiguous_before = tuple(
        frame(index, (True, False, False)) for index in range(10, 13)
    )
    assert probe_dense_river_count_delta(after, contiguous_before, **kwargs).reason == (
        "river_windows_not_forward_ordered"
    )
    assert probe_dense_river_count_delta(before[:2], after, **kwargs).reason == (
        "insufficient_stable_river_frames"
    )


def test_invalid_overlapping_profile_and_stability_rejected():
    overlapping = replace(
        PROFILE,
        slots=((.1, .2, .1, .2), (.15, .2, .1, .2)),
    )
    assert run(profile=overlapping).reason == (
        "invalid_source_scoped_dense_river_profile"
    )
    assert run(stable_frames=2).reason == "invalid_stability_requirement"


def test_sequence_audit_suppresses_disappear_then_same_slot_reappears():
    audit = audit_dense_river_stable_masks((
        (True, True, False, False),
        (True, True, True, False),
        (True, True, False, False),
        (True, True, True, False),
        (True, True, True, True),
    ))
    assert audit.status == "DENSE_RIVER_SEQUENCE_AUDIT_ONLY"
    assert audit.candidate_count_changes == ((2, 3), (3, 4))
    assert audit.suppressed_reappearances == 1
    assert audit.ambiguous_or_disappearing_transitions == 1
    data = audit.to_dict()
    assert data["slot_indexes_exposed"] is False
    assert data["actual_actions_emitted"] == 0


def test_sequence_audit_rejects_invalid_masks_and_marks_multi_change_ambiguous():
    assert audit_dense_river_stable_masks(()).status == "UNKNOWN"
    assert audit_dense_river_stable_masks(((True,), (True, False))).status == "UNKNOWN"
    assert audit_dense_river_stable_masks(((1,), (True,))).status == "UNKNOWN"
    audit = audit_dense_river_stable_masks((
        (False, False, False),
        (True, True, False),
    ))
    assert audit.candidate_count_changes == ()
    assert audit.ambiguous_or_disappearing_transitions == 1


def local(masks, *, anchor=15, followup=8, **changes):
    frames = tuple(source_scoped_dense_river_mask(
        frame(10 + offset, mask), PROFILE,
    ) for offset, mask in enumerate(masks))
    options = dict(profile=PROFILE, anchor_frame=anchor,
                   max_followup_frames=followup,
                   river_slots_independently_verified=True,
                   interval_continuously_reviewed=True,
                   new_slot_never_seen_in_epoch=True,
                   source_window_from_continuous_decode=True)
    options.update(changes)
    return probe_anchor_local_river_growth(frames, **options)


def test_local_anchor_accepts_only_later_unique_growth_without_action():
    old, new = (True, False, False), (True, True, False)
    assert local((old,) * 4 + (new,) * 6).reason == (
        "river_growth_outside_anchor_window"
    )
    result = local((old,) * 7 + (new,) * 3)
    assert result.status == "DENSE_RIVER_COUNT_DELTA_CANDIDATE_ONLY"
    assert (result.before_count, result.after_count) == (1, 2)
    assert result.first_stable_after_frame > 15
    assert result.to_dict()["actual_action_kind"] == "UNKNOWN"


def test_local_anchor_rejects_persistent_multi_slot_overlay_and_reversion():
    old = (True, False, False)
    new = (True, True, False)
    overlay = (True, True, True)
    assert local((old,) * 3 + (overlay,) * 3 + (new,) * 4).reason == (
        "competing_stable_river_mask"
    )
    assert local((old,) * 3 + (new,) * 3 + (old,) * 3 + (new,) * 3).reason == (
        "stable_river_reversion"
    )


def test_local_anchor_rejects_wrong_scope_gap_and_unverified_interval():
    old, new = (True, False, False), (True, True, False)
    frames = tuple(source_scoped_dense_river_mask(
        frame(i, old if i < 15 else new), PROFILE,
    ) for i in range(10, 20))
    args = dict(profile=PROFILE, anchor_frame=15, max_followup_frames=8,
                river_slots_independently_verified=True,
                interval_continuously_reviewed=True,
                new_slot_never_seen_in_epoch=True,
                source_window_from_continuous_decode=True)
    for variant in (
        (*frames[:5], replace(frames[5], frame_index=16), *frames[6:]),
        (*frames[:5], replace(frames[5], source_sha256="b" * 64), *frames[6:]),
        (*frames[:5], replace(frames[5], source_pixels_verified=False), *frames[6:]),
        (*frames[:5], replace(frames[5], slot_mask=(1, False, False)), *frames[6:]),
    ):
        assert probe_anchor_local_river_growth(variant, **args).status == "UNKNOWN"
    assert local((old,) * 5 + (new,) * 5,
                 interval_continuously_reviewed=False).status == "UNKNOWN"
    assert local((old,) * 5 + (new,) * 5,
                 new_slot_never_seen_in_epoch=False).status == "UNKNOWN"
    assert local((old,) * 5 + (new,) * 5,
                 source_window_from_continuous_decode=False).status == "UNKNOWN"


def test_local_mask_builder_rejects_unverified_source_pixels():
    original = frame(10, (True, False, False))
    assert source_scoped_dense_river_mask(
        replace(original, decoded_pixel_sha256="0" * 64), PROFILE,
    ) is None
    packet = source_scoped_dense_river_mask(original, PROFILE)
    assert isinstance(packet, DenseRiverMaskFrame)


def prefix_local(
    before=(True, False, None),
    after=(True, True, None),
    *,
    expected=1,
    suffix=(),
    **changes,
):
    masks = (before,) * 6 + (after,) * 5 + tuple(suffix)
    packets = tuple(DenseRiverMaskFrame(
        "hand-01", SHA, 0, 10 + offset, mask, True,
    ) for offset, mask in enumerate(masks))
    options = dict(
        profile=PROFILE, anchor_frame=15, expected_before_prefix=expected,
        max_followup_frames=12, river_slots_independently_verified=True,
        interval_continuously_reviewed=True,
        source_window_from_continuous_decode=True,
        expected_prefix_from_prior_chain=True,
    )
    options.update(changes)
    return probe_anchor_local_river_prefix_growth(packets, **options)


def test_prefix_growth_accepts_one_confirmed_step_with_unknown_later_slots():
    result = prefix_local()
    assert isinstance(result, DenseRiverPrefixGrowth)
    assert result.status == "DENSE_RIVER_PREFIX_GROWTH_CANDIDATE_ONLY"
    assert (result.before_confirmed_prefix,
            result.after_confirmed_prefix) == (1, 2)
    data = result.to_dict()
    assert data["exact_total_count_known"] is False
    assert data["actual_action_kind"] == "UNKNOWN"
    fact = dense_river_prefix_growth_to_transition_fact(result)
    assert fact is not None and fact.channel == "river"
    assert dense_river_prefix_growth_to_transition_fact(
        replace(result, status="UNKNOWN")
    ) is None


def test_prefix_growth_rejects_preexisting_larger_prefix_and_later_reversion():
    assert prefix_local(
        before=(True, True, None), expected=1,
    ).reason == "expected_stable_prefix_baseline_absent"
    reversion = ((True, False, None),) * 3
    assert prefix_local(suffix=reversion).reason == (
        "stable_prefix_reversion_or_competing_growth"
    )


def test_prefix_growth_requires_prior_chain_and_continuous_decode():
    for change in (
        {"expected_prefix_from_prior_chain": False},
        {"source_window_from_continuous_decode": False},
        {"interval_continuously_reviewed": False},
    ):
        assert prefix_local(**change).status == "UNKNOWN"


def test_prefix_growth_tolerates_only_lower_pre_anchor_occlusion():
    masks = (
        ((True, False, None),) * 3
        + ((False, False, None),) * 3
        + ((True, True, None),) * 4
    )
    packets = tuple(DenseRiverMaskFrame(
        "hand-01", SHA, 0, 10 + offset, mask, True,
    ) for offset, mask in enumerate(masks))
    result = probe_anchor_local_river_prefix_growth(
        packets, profile=PROFILE, anchor_frame=15, expected_before_prefix=1,
        max_followup_frames=8, river_slots_independently_verified=True,
        interval_continuously_reviewed=True,
        source_window_from_continuous_decode=True,
        expected_prefix_from_prior_chain=True,
    )
    assert result.status == "DENSE_RIVER_PREFIX_GROWTH_CANDIDATE_ONLY"
