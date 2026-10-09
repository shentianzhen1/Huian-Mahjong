"""Read-only Tianting status routing for simulator results.

Issue #9: Tianting is a confirmed status marker only. This copy is for
default simulator/match routing. It must not add fan, multiplier, or score,
and it must not invent a marker the environment has not evaluated.
"""
from __future__ import annotations


def snapshot_tianting(first_round):
    """Copy environment Tianting flags into an immutable result payload.

    ``listening`` is ``None`` until that seat has been evaluated, then a
    bool. Waits are copied only for an evaluated listening seat. Bonus fields
    are fixed at the confirmed zero-bonus contract.
    """
    listening = [None, None]
    waits = [[], []]
    evidence_id = None
    if isinstance(first_round, dict):
        evidence_id = first_round.get("evidence_id")
        raw = first_round.get("tianting") or [None, None]
        raw_waits = first_round.get("tianting_waits") or [[], []]
        for seat in (0, 1):
            flag = raw[seat] if seat < len(raw) else None
            if flag is None:
                continue
            listening[seat] = bool(flag)
            seat_waits = raw_waits[seat] if seat < len(raw_waits) else []
            waits[seat] = list(seat_waits) if listening[seat] else []
    return {
        "score_effect": "NONE",
        "bonus_fan": 0,
        "bonus_multiplier": 1,
        "listening": listening,
        "waits": waits,
        "evidence_id": evidence_id,
    }
