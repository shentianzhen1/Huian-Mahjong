from dataclasses import replace

from workspace.vision.issue69_public_replay_orchestrator import PublicReplayCandidate
from workspace.vision.issue69_temporal_reconstruction import HandDeltaCandidate, reconstruct_public_candidates


def candidate(channel, timestamp, frame, actor, kind, *, tile=None, tiles=()):
    return PublicReplayCandidate(
        channel, timestamp, frame, actor, kind, "s", "a" * 64, 0,
        (f"{channel}:{frame}",), tile=tile, tiles=tiles,
    )


def replay(rows):
    hand = HandDeltaCandidate(
        117.5, 3525, "opponent", "s", "a" * 64, 0, ("hand:3525",),
        removed_tiles=("P6", "P8"),
    )
    return reconstruct_public_candidates(
        rows, hand_deltas=[hand], claim_window_seconds=1.5,
        assembly_delay_seconds=0,
    )


def test_removal_cannot_supply_discard_even_with_complete_claim_evidence():
    rows = [
        candidate("river", 117.36, 3521, "player", "RIVER_TILE_REMOVED_OR_CLAIMED", tile="P7"),
        candidate("meld", 117.8, 3534, "opponent", "MELD_DELTA", tiles=("P6", "P7", "P8")),
    ]
    report = replay(rows)
    assert not any(a["kind"] in ("DISCARD", "CHI") for a in report["actions"])
    assert report["excluded_context"][0]["candidate_kind"] == "RIVER_TILE_REMOVED_OR_CLAIMED"
    assert report["excluded_context"][0]["evidence_refs"] == ["river:3521"]
    assert report["safe_for_runtime"] is False


def test_structured_meld_identities_can_reconstruct_claim_with_real_discard():
    report = replay([
        candidate("river", 117.0, 3510, "player", "DISCARD", tile="P7"),
        candidate("meld", 117.8, 3534, "opponent", "MELD_DELTA", tiles=("P6", "P7", "P8")),
    ])
    claim = next(a for a in report["actions"] if a["kind"] == "CHI")
    assert claim["meld"] == ["P6", "P7", "P8"]
    assert claim["claimed_tile"] == "P7"


def test_partial_meld_stays_unknown_and_conflicting_representations_rejected():
    discard = candidate("river", 117.0, 3510, "player", "DISCARD", tile="P7")
    partial = candidate("meld", 117.8, 3534, "opponent", "MELD_DELTA", tiles=(None, "P7", "P8"))
    report = replay([discard, partial])
    assert not any(a["kind"] == "CHI" for a in report["actions"])
    assert any(a["kind"] == "UNKNOWN_ACTION" for a in report["actions"])
    try:
        replay([discard, replace(partial, tile="P6,P7,P8")])
    except ValueError as exc:
        assert "identities conflict" in str(exc)
    else:
        raise AssertionError("conflicting identities were accepted")


def test_other_river_candidate_kinds_cannot_become_discards():
    report = replay([candidate("river", 117.0, 3510, "player", "OCCUPANCY_INCREASE")])
    assert report["actions"] == []
    assert len(report["excluded_context"]) == 1
