"""Fuse fail-closed river-removal facts with exposed-meld deltas.

A river -1 only says a public discard disappeared. A meld +1 only says a new
exposed group appeared. When they are close in time and belong to opposite
actors, this layer links the evidence without inventing CHI/PENG/KONG unless
the meld faces themselves support an exact semantic classification.
"""
from __future__ import annotations

def _meld_kind(tiles):
    tiles=tuple(tiles or ())
    if len(tiles)==4 and len(set(tiles))==1 and tiles[0] not in (None,"UNKNOWN"):
        return "MING_GANG"
    known=[t for t in tiles if t not in (None,"UNKNOWN")]
    if len(tiles)==3 and len(known)==3:
        if len(set(known))==1:
            return "PENG"
        parsed=[]
        for t in known:
            if len(t)!=2 or t[0] not in "MPS" or not t[1].isdigit():
                return "UNKNOWN_CLAIM"
            parsed.append((t[0],int(t[1])))
        if len({s for s,_ in parsed})==1:
            ranks=sorted(r for _,r in parsed)
            if ranks[1]==ranks[0]+1 and ranks[2]==ranks[1]+1:
                return "CHI"
    return "UNKNOWN_CLAIM"

def correlate_claims(river_transitions, meld_deltas, *, tolerance_seconds=1.5):
    if tolerance_seconds <= 0:
        raise ValueError("tolerance_seconds must be positive")
    removals=[
        (i,r) for i,r in enumerate(river_transitions)
        if r.get("kind")=="RIVER_TILE_REMOVED_OR_CLAIMED" and r.get("trusted",True)
    ]
    melds=[
        (i,m) for i,m in enumerate(meld_deltas)
        if m.get("kind")=="MELD_DELTA" and m.get("trusted",True)
    ]
    candidates=[]
    for ri,r in removals:
        for mi,m in melds:
            if r.get("actor")==m.get("actor"):
                continue
            dt=abs(float(r["timestamp_seconds"])-float(m["timestamp_seconds"]))
            if dt <= tolerance_seconds:
                candidates.append((dt,ri,mi,r,m))
    candidates.sort(key=lambda x:x[0])
    used_r=set(); used_m=set(); out=[]
    for dt,ri,mi,r,m in candidates:
        if ri in used_r or mi in used_m:
            continue
        used_r.add(ri); used_m.add(mi)
        tiles=tuple(m.get("tiles") or ())
        action=_meld_kind(tiles)
        out.append({
            "timestamp_seconds":max(float(r["timestamp_seconds"]),float(m["timestamp_seconds"])),
            "actor":m["actor"],
            "action":action,
            "claimed_from_actor":r["actor"],
            "delta_seconds":round(dt,6),
            "meld_tiles":list(tiles),
            "identity_complete":bool(tiles) and all(t not in (None,"UNKNOWN") for t in tiles),
            "evidence_grade":"CORROBORATED" if action!="UNKNOWN_CLAIM" else "INFERRED",
            "formal_promotion_evidence":False,
            "safe_for_executor":False,
        })
    return {
        "claims":out,
        "unmatched_removals":[r for i,r in removals if i not in used_r],
        "unmatched_melds":[m for i,m in melds if i not in used_m],
        "formal_promotion_evidence":False,
        "safe_for_executor":False,
    }
