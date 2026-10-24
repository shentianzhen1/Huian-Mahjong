"""Separate action reconstruction quality from tile-identity quality for #69.

A correct action must never hide a wrong tile identity. UNKNOWN remains a valid
fail-closed identity outcome and is reported separately from wrong identity.
"""
from __future__ import annotations

def score_reviewed_events(expected, observed):
    exp=list(expected); obs=list(observed)
    rows=[]; action_ok=identity_ok=unknown=wrong=0
    n=max(len(exp),len(obs))
    for i in range(n):
        e=exp[i] if i<len(exp) else {}
        o=obs[i] if i<len(obs) else {}
        a=(e.get("actor"),e.get("action"))==(o.get("actor"),o.get("action"))
        if a: action_ok+=1
        et=e.get("tile_id"); ot=o.get("tile_id")
        if et in (None,"UNKNOWN"):
            identity="NOT_SCORED"
        elif ot in (None,"UNKNOWN"):
            identity="UNKNOWN"; unknown+=1
        elif et==ot:
            identity="CORRECT"; identity_ok+=1
        else:
            identity="WRONG"; wrong+=1
        rows.append({"index":i,"action_correct":a,"identity_result":identity,
                     "expected_tile":et,"observed_tile":ot})
    scored=sum(1 for e in exp if e.get("tile_id") not in (None,"UNKNOWN"))
    return {
        "schema_version":"issue69_action_identity_metrics_v0_1",
        "action":{"correct":action_ok,"total_expected":len(exp)},
        "identity":{"correct":identity_ok,"wrong":wrong,"unknown":unknown,
                    "scored_expected":scored},
        "rows":rows,
        "policy":"UNKNOWN and WRONG are distinct; action correctness cannot mask identity error",
        "formal_promotion_evidence":False,
        "safe_for_executor":False,
    }
