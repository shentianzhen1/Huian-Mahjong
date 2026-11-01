"""Synthetic fail-closed coverage for the #69 onset/transition join."""
from dataclasses import replace

from workspace.vision.public_action_area_onset import ActionAreaOnsetCandidate
from workspace.vision.public_action_area_transition_join import (
    PublicTransitionFact,
    join_action_area_to_public_transition,
)

SHA = "a" * 64


def onset(**changes):
    base = ActionAreaOnsetCandidate(
        "ACTION_AREA_ONSET_CANDIDATE_ONLY", "candidate", "player",
        9, 10, 11, (1, 2, 3, 4), (2, 3, 3, 4), "hand-01", SHA, 0,
    )
    return replace(base, **changes)


def fact(channel="river", frame=18, actor="player", **changes):
    base = PublicTransitionFact(
        channel, actor, frame, "hand-01", SHA, 0, True,
    )
    return replace(base, **changes)


def join(items, candidate=None, window=30):
    return join_action_area_to_public_transition(
        candidate or onset(), items, max_followup_frames=window,
    )


def test_unique_later_river_change_is_review_candidate_not_action():
    result = join([fact()])
    assert result.status == "PUBLIC_TRANSITION_JOIN_CANDIDATE_ONLY"
    data = result.to_dict()
    assert data["joined_channels"] == ["river"]
    assert data["transition_order"] == "AFTER_ONSET"
    assert data["actual_action_kind"] == "UNKNOWN"
    assert data["actual_actor"] == "UNKNOWN"
    assert data["raw_observation_emitted"] is False
    assert data["safe_for_runtime"] is False
    assert data["safe_for_executor"] is False
    assert SHA not in repr(data)
    assert "hand-01" not in repr(data)


def test_one_hand_count_delta_can_only_corroborate_public_zone_change():
    result = join([fact(), fact("hand_count", 16)])
    assert result.status == "PUBLIC_TRANSITION_JOIN_CANDIDATE_ONLY"
    assert result.joined_channels == ("river", "hand_count")
    assert join([fact("hand_count", 16)]).reason == (
        "hand_count_delta_alone_cannot_confirm_public_action"
    )


def test_unique_meld_change_is_still_semantically_unknown():
    data = join([fact("meld", 20, "opponent")]).to_dict()
    assert data["status"] == "PUBLIC_TRANSITION_JOIN_CANDIDATE_ONLY"
    assert data["transition_actor_hint"] == "opponent"
    assert data["actual_action_kind"] == "UNKNOWN"


def test_multiple_public_zone_changes_fail_closed():
    result = join([fact("river", 18), fact("meld", 19)])
    assert result.status == "UNKNOWN"
    assert result.reason == "ambiguous_multiple_public_zone_transitions"


def test_multiple_hand_deltas_fail_closed():
    result = join([
        fact("river", 18), fact("hand_count", 15), fact("hand_count", 17),
    ])
    assert result.reason == "ambiguous_multiple_hand_count_transitions"


def test_conflicting_transition_actor_hints_fail_closed():
    result = join([fact("river", 18), fact("hand_count", 16, "opponent")])
    assert result.reason == "conflicting_transition_actor_hints"


def test_wrong_source_session_sha_or_epoch_fail_closed():
    variants = (
        fact(source_session="hand-02"),
        fact(source_sha256="b" * 64),
        fact(stream_epoch=1),
    )
    for item in variants:
        assert join([item]).reason == "source_session_sha_or_epoch_changed"


def test_transition_before_onset_is_never_joined():
    assert join([fact(frame=7)]).reason == "no_public_transition_in_window"


def test_transition_during_onset_confirmation_or_too_late_is_not_joined():
    assert join([fact(frame=10)]).reason == "no_public_transition_in_window"
    assert join([fact(frame=11)]).reason == "no_public_transition_in_window"
    assert join([fact(frame=41)], window=30).reason == (
        "no_public_transition_in_window"
    )


def test_public_change_before_onset_does_not_make_later_change_ambiguous():
    result = join([fact(frame=7), fact("meld", 18)])
    assert result.status == "PUBLIC_TRANSITION_JOIN_CANDIDATE_ONLY"
    assert result.joined_channels == ("meld",)


def test_unverified_or_wrong_status_fact_fails_closed():
    assert join([fact(independently_verified=False)]).reason == (
        "invalid_or_unverified_public_transition"
    )
    assert join([fact(status="ACTION")]).reason == (
        "invalid_or_unverified_public_transition"
    )


def test_unknown_or_invalid_onset_is_rejected():
    assert join([fact()], onset(status="UNKNOWN")).reason == (
        "invalid_or_unverified_action_area_onset"
    )
    assert join([fact()], onset(source_sha256="not-a-sha")).reason == (
        "invalid_or_unverified_action_area_onset"
    )


def test_empty_invalid_collection_and_window_are_rejected():
    assert join([]).reason == "no_independent_public_transition"
    assert join_action_area_to_public_transition(
        onset(), "bad", max_followup_frames=30,
    ).reason == "invalid_transition_collection"
    assert join([fact()], window=0).reason == "invalid_transition_window"
