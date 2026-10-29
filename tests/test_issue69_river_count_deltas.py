from workspace.vision.issue69_river_count_deltas import RiverCountSample, extract_river_count_transitions

def test_plus_one_is_visible_discard_without_identity_guess():
    r=extract_river_count_transitions([
        RiverCountSample(163.5,"player",10),
        RiverCountSample(164.0,"player",11),
    ])
    assert r[0]["kind"]=="DISCARD_VISIBLE"
    assert r[0]["tile_id"]=="UNKNOWN"
    assert r[0]["trusted"] is True

def test_minus_one_is_claim_evidence_not_claim_action():
    r=extract_river_count_transitions([
        RiverCountSample(116.8,"player",4),
        RiverCountSample(117.2,"player",3),
    ])
    assert r[0]["kind"]=="RIVER_TILE_REMOVED_OR_CLAIMED"
    assert "CHI" not in r[0]["kind"]
    assert "PENG" not in r[0]["kind"]

def test_large_jump_fails_closed_instead_of_inventing_discards():
    r=extract_river_count_transitions([
        RiverCountSample(130.0,"player",4),
        RiverCountSample(140.0,"player",7),
    ])
    assert r[0]["kind"]=="AMBIGUOUS_RIVER_JUMP"
    assert r[0]["trusted"] is False
    assert r[0]["delta"]==3

def test_untrusted_sample_breaks_continuity():
    r=extract_river_count_transitions([
        RiverCountSample(10.0,"opponent",3),
        RiverCountSample(11.0,"opponent",4,False),
        RiverCountSample(12.0,"opponent",5),
    ])
    assert r==[]

def test_actor_streams_are_independent():
    r=extract_river_count_transitions([
        RiverCountSample(1.0,"player",2),
        RiverCountSample(1.0,"opponent",3),
        RiverCountSample(2.0,"player",3),
        RiverCountSample(2.0,"opponent",2),
    ])
    assert [x["kind"] for x in r]==["DISCARD_VISIBLE","RIVER_TILE_REMOVED_OR_CLAIMED"]
