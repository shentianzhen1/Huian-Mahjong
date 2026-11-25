from workspace.vision.issue69_replay_consistency import check_replay_consistency

def test_discard_hu_chain_passes():
    events=[
        {"actor":"SELF","action":"DRAW","tile_id":"UNKNOWN"},
        {"actor":"SELF","action":"DISCARD","tile_id":"P4"},
        {"actor":"OPPONENT","action":"HU","tile_id":"P4","hu_source":"DISCARD"},
    ]
    assert check_replay_consistency(events)["status"]=="PASS"

def test_claim_requires_opponent_discard():
    report=check_replay_consistency([
        {"actor":"SELF","action":"DISCARD","tile_id":"M9"},
        {"actor":"SELF","action":"PENG","tile_id":"M9"},
    ])
    assert report["status"]=="CONFLICT"
    assert report["issues"][0]["reason"]=="claim_on_own_discard"

def test_post_claim_draw_before_discard_conflicts():
    report=check_replay_consistency([
        {"actor":"OPPONENT","action":"DISCARD","tile_id":"M9"},
        {"actor":"SELF","action":"PENG","tile_id":"M9"},
        {"actor":"SELF","action":"DRAW","tile_id":"UNKNOWN"},
    ])
    assert any(x["reason"]=="draw_before_post_claim_discard" for x in report["issues"])

def test_unknown_identity_does_not_block_action_chain():
    report=check_replay_consistency([
        {"actor":"OPPONENT","action":"DISCARD","tile_id":"UNKNOWN"},
        {"actor":"SELF","action":"CHI","tile_id":"UNKNOWN"},
        {"actor":"SELF","action":"DISCARD","tile_id":"UNKNOWN"},
    ])
    assert report["status"]=="PASS"
