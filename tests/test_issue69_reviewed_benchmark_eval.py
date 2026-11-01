from workspace.vision.issue69_reviewed_benchmark_eval import evaluate_reviewed_benchmark

BENCH={
 "schema_version":"issue69_round8_reviewed_benchmark_v0_1",
 "events":[
  {"time_seconds":116.8,"actor":"SELF","action":"DISCARD","tile_id":"P7"},
  {"time_seconds":177.5,"actor":"SELF","action":"DISCARD","tile_id":"P4"},
  {"time_seconds":178.0,"actor":"OPPONENT","action":"HU","tile_id":"P4"},
  {"time_seconds":185.5,"actor":"SYSTEM","action":"SETTLEMENT"}
 ]
}

def test_p7_p8_is_action_correct_identity_wrong():
    r=evaluate_reviewed_benchmark(BENCH,[
      {"timestamp_seconds":116.7,"actor":"player","kind":"DISCARD","tile":"P8","evidence_grade":"UNKNOWN"}
    ])
    assert r["matched_events"]==1
    assert r["action_correct"]==1
    assert r["actor_correct"]==1
    assert r["identity"]["WRONG"]==1
    assert r["unknown_grade_matched"]==1

def test_unknown_identity_is_separate_abstention():
    r=evaluate_reviewed_benchmark(BENCH,[
      {"timestamp_seconds":177.45,"actor":"player","kind":"DISCARD","tile":None,"evidence_grade":"UNKNOWN"},
      {"timestamp_seconds":178.05,"actor":"opponent","kind":"HU","tile":"P4","evidence_grade":"CORROBORATED"},
    ])
    assert r["matched_events"]==2
    assert r["identity"]["UNKNOWN"]==1
    assert r["identity"]["CORRECT"]==1

def test_wrong_actor_is_not_hidden_by_time_match():
    r=evaluate_reviewed_benchmark(BENCH,[
      {"timestamp_seconds":178.0,"actor":"player","kind":"HU","tile":"P4","evidence_grade":"DIRECT"}
    ])
    assert r["matched_events"]==1
    assert r["action_correct"]==1
    assert r["actor_correct"]==0

def test_system_settlement_not_scored_as_public_action():
    r=evaluate_reviewed_benchmark(BENCH,[])
    assert r["expected_events"]==3
