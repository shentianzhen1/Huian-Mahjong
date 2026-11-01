"""Count-only river delta facts for Issue #69 replay diagnostics.

This module intentionally does less than DiscardRiverObserver. It converts an
already-stable river tile-count series into auditable deltas so reconstruction
can distinguish:
- +1: one discard became publicly visible;
- -1: a river tile disappeared, usually because a claim consumed it;
- larger jumps: missed/ambiguous transition, never expanded into invented
  actions.

It does not classify CHI/PENG/KONG and does not infer tile identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class RiverCountSample:
    timestamp_seconds: float
    actor: str
    count: int
    trusted: bool = True

    def __post_init__(self):
        if self.timestamp_seconds < 0:
            raise ValueError("timestamp_seconds must be nonnegative")
        if self.actor not in {"player","opponent"}:
            raise ValueError("actor must be player or opponent")
        if isinstance(self.count,bool) or not isinstance(self.count,int) or self.count < 0:
            raise ValueError("count must be a nonnegative integer")

def extract_river_count_transitions(samples: Iterable[RiverCountSample]) -> list[dict]:
    rows=list(samples)
    out=[]
    previous_by_actor={}
    for row in rows:
        if not row.trusted:
            previous_by_actor.pop(row.actor,None)
            continue
        previous=previous_by_actor.get(row.actor)
        previous_by_actor[row.actor]=row
        if previous is None or row.count == previous.count:
            continue
        delta=row.count-previous.count
        if delta == 1:
            kind="DISCARD_VISIBLE"
            trusted=True
        elif delta == -1:
            kind="RIVER_TILE_REMOVED_OR_CLAIMED"
            trusted=True
        else:
            kind="AMBIGUOUS_RIVER_JUMP"
            trusted=False
        out.append({
            "timestamp_seconds":float(row.timestamp_seconds),
            "actor":row.actor,
            "previous_count":previous.count,
            "current_count":row.count,
            "delta":delta,
            "kind":kind,
            "trusted":trusted,
            "tile_id":"UNKNOWN",
            "formal_promotion_evidence":False,
            "safe_for_executor":False,
        })
    return out
