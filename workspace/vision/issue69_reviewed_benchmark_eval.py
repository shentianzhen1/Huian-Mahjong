"""Development-only evaluator for #69 reviewed real-video benchmarks.

Unlike promotion metrics, this diagnostic keeps three questions separate:
1) was an event found near the reviewed time,
2) were actor/action semantics correct,
3) was tile identity correct, wrong, or UNKNOWN.

UNKNOWN remains an abstention for identity and never becomes a correct tile.
"""
from __future__ import annotations

_ACTIONS={"DRAW","DISCARD","CHI","PENG","KONG","MING_GANG","ADD_KONG","PASS","HU"}

def _actor(value):
    return {"SELF":"player","OPPONENT":"opponent","PLAYER":"player"}.get(value,value.lower() if isinstance(value,str) else value)

def _action(row):
    return row.get("action") or row.get("kind")

def _time(row):
    value=row.get("time_seconds", row.get("timestamp_seconds"))
    if isinstance(value,bool) or not isinstance(value,(int,float)) or value < 0:
        raise ValueError("event requires nonnegative time")
    return float(value)

def evaluate_reviewed_benchmark(benchmark, machine_events, *, tolerance_seconds=.6):
    if benchmark.get("schema_version")!="issue69_round8_reviewed_benchmark_v0_1":
        raise ValueError("unsupported benchmark")
    if tolerance_seconds <= 0:
        raise ValueError("tolerance_seconds must be positive")
    expected=[e for e in benchmark.get("events",[]) if e.get("actor")!="SYSTEM" and _action(e) in _ACTIONS]
    observed=[dict(e) for e in machine_events if _action(e) in _ACTIONS]
    candidates=[]
    for ei,e in enumerate(expected):
        for oi,o in enumerate(observed):
            d=abs(_time(e)-_time(o))
            if d <= tolerance_seconds:
                candidates.append((d, int(_action(e)!=_action(o)), ei, oi))
    candidates.sort()
    used_e=set(); used_o=set(); rows=[]
    for d,_,ei,oi in candidates:
        if ei in used_e or oi in used_o: continue
        used_e.add(ei); used_o.add(oi)
        e=expected[ei]; o=observed[oi]
        ea,oa=_action(e),_action(o)
        eactor,oactor=_actor(e.get("actor")),_actor(o.get("actor"))
        et=e.get("tile_id"); ot=o.get("tile_id",o.get("tile"))
        if et in (None,"UNKNOWN"):
            ident="NOT_SCORED"
        elif ot in (None,"UNKNOWN"):
            ident="UNKNOWN"
        elif et==ot:
            ident="CORRECT"
        else:
            ident="WRONG"
        rows.append({
            "expected_index":ei,"observed_index":oi,"delta_seconds":round(d,6),
            "action_correct":ea==oa,"actor_correct":eactor==oactor,
            "identity_result":ident,"expected_tile":et,"observed_tile":ot,
            "observed_evidence_grade":o.get("evidence_grade"),
        })
    identity={"CORRECT":0,"WRONG":0,"UNKNOWN":0,"NOT_SCORED":0}
    for row in rows: identity[row["identity_result"]]+=1
    return {
        "schema_version":"issue69_reviewed_benchmark_eval_v0_1",
        "expected_events":len(expected),"observed_events":len(observed),
        "matched_events":len(rows),"missed_events":len(expected)-len(used_e),
        "extra_events":len(observed)-len(used_o),
        "action_correct":sum(r["action_correct"] for r in rows),
        "actor_correct":sum(r["actor_correct"] for r in rows),
        "identity":identity,
        "unknown_grade_matched":sum(r["observed_evidence_grade"]=="UNKNOWN" for r in rows),
        "rows":rows,
        "formal_promotion_evidence":False,
        "safe_for_runtime":False,
        "safe_for_executor":False,
    }
