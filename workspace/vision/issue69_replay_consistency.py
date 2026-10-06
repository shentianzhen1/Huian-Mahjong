"""Fail-closed consistency checks for Issue #69 reviewed replay events.

This layer validates transitions only. It never invents tile identity and never
turns visual context into action truth.
"""
from __future__ import annotations

_ACTIONS={"DRAW","DISCARD","CHI","PENG","KONG","PASS","HU"}

def check_replay_consistency(events):
    rows=list(events)
    issues=[]
    terminal=False
    last_discard=None
    claim_needs_discard=None
    for i,e in enumerate(rows):
        action=e.get("action")
        actor=e.get("actor")
        tile=e.get("tile_id")
        if action not in _ACTIONS:
            issues.append({"index":i,"reason":"unsupported_action"})
            continue
        if terminal:
            issues.append({"index":i,"reason":"action_after_hu"})
            continue
        if action=="DISCARD":
            last_discard={"actor":actor,"tile_id":tile,"index":i}
            claim_needs_discard=None
        elif action in {"CHI","PENG"}:
            if last_discard is None:
                issues.append({"index":i,"reason":"claim_without_prior_discard"})
            elif last_discard["actor"]==actor:
                issues.append({"index":i,"reason":"claim_on_own_discard"})
            claim_needs_discard=actor
        elif action=="DRAW":
            if claim_needs_discard==actor:
                issues.append({"index":i,"reason":"draw_before_post_claim_discard"})
            last_discard=None
        elif action=="HU":
            source=e.get("hu_source")
            if source=="DISCARD":
                if last_discard is None:
                    issues.append({"index":i,"reason":"discard_hu_without_prior_discard"})
                else:
                    if last_discard["actor"]==actor:
                        issues.append({"index":i,"reason":"hu_on_own_discard"})
                    if tile not in (None,"UNKNOWN") and last_discard["tile_id"] not in (None,"UNKNOWN",tile):
                        issues.append({"index":i,"reason":"winning_tile_conflicts_with_last_discard"})
            terminal=True
    return {
        "schema_version":"issue69_replay_consistency_v0_1",
        "status":"PASS" if not issues else "CONFLICT",
        "issues":issues,
        "formal_promotion_evidence":False,
        "safe_for_runtime":False,
        "safe_for_hint":False,
        "safe_for_executor":False,
    }
