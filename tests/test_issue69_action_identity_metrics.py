from workspace.vision.issue69_action_identity_metrics import score_reviewed_events

def test_correct_action_wrong_identity_stays_wrong():
    expected=[{"actor":"SELF","action":"DISCARD","tile_id":"P7"}]
    observed=[{"actor":"SELF","action":"DISCARD","tile_id":"P8"}]
    r=score_reviewed_events(expected,observed)
    assert r["action"]["correct"]==1
    assert r["identity"]["wrong"]==1
    assert r["rows"][0]["identity_result"]=="WRONG"

def test_unknown_is_not_counted_as_wrong():
    expected=[{"actor":"SELF","action":"DISCARD","tile_id":"P7"}]
    observed=[{"actor":"SELF","action":"DISCARD","tile_id":"UNKNOWN"}]
    r=score_reviewed_events(expected,observed)
    assert r["identity"]["wrong"]==0
    assert r["identity"]["unknown"]==1

def test_terminal_p4_chain_scores_actions_and_identity():
    expected=[
        {"actor":"SELF","action":"DISCARD","tile_id":"P4"},
        {"actor":"OPPONENT","action":"HU","tile_id":"P4"},
    ]
    r=score_reviewed_events(expected,expected)
    assert r["action"]=={"correct":2,"total_expected":2}
    assert r["identity"]["correct"]==2
