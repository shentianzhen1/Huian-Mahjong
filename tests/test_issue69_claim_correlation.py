from workspace.vision.issue69_claim_correlation import correlate_claims

def rem(t,actor):
    return {"timestamp_seconds":t,"actor":actor,"kind":"RIVER_TILE_REMOVED_OR_CLAIMED","trusted":True}
def meld(t,actor,tiles):
    return {"timestamp_seconds":t,"actor":actor,"kind":"MELD_DELTA","tiles":tiles,"trusted":True}

def test_opposite_actor_removal_plus_triplet_is_peng():
    r=correlate_claims([rem(115.0,"opponent")],[meld(115.4,"player",["M9","M9","M9"])])
    assert r["claims"][0]["action"]=="PENG"
    assert r["claims"][0]["claimed_from_actor"]=="opponent"

def test_opposite_actor_removal_plus_sequence_is_chi():
    r=correlate_claims([rem(117.0,"player")],[meld(117.3,"opponent",["P6","P7","P8"])])
    assert r["claims"][0]["action"]=="CHI"

def test_incomplete_identity_stays_unknown_claim():
    r=correlate_claims([rem(129.0,"opponent")],[meld(129.4,"player",[None,"S3","S4"])])
    assert r["claims"][0]["action"]=="UNKNOWN_CLAIM"
    assert r["claims"][0]["identity_complete"] is False

def test_same_actor_does_not_pair():
    r=correlate_claims([rem(10,"player")],[meld(10.2,"player",["M1","M2","M3"])])
    assert r["claims"]==[]
    assert len(r["unmatched_removals"])==1
    assert len(r["unmatched_melds"])==1

def test_outside_time_window_does_not_pair():
    r=correlate_claims([rem(10,"opponent")],[meld(12,"player",["M9","M9","M9"])],tolerance_seconds=1.5)
    assert r["claims"]==[]

def test_four_identical_faces_is_ming_gang():
    r=correlate_claims([rem(20,"opponent")],[meld(20.5,"player",["P6"]*4)])
    assert r["claims"][0]["action"]=="MING_GANG"
