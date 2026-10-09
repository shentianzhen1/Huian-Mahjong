"""Fail-closed loader for an unfrozen real-match intake.

Unknown settlement and unhashed clips stay unknown. They must not become a
zero score, a draw, or an AI reward.
"""
from __future__ import annotations

import json
from pathlib import Path


class UnfrozenMatchIntake(ValueError):
    pass


def load_match_intake(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "huian_match_intake_v0_1":
        raise ValueError("unsupported match intake schema")
    clips = payload.get("clips")
    if not isinstance(clips, list) or not clips:
        raise ValueError("match intake requires clips")
    return payload


def require_frozen_ledger(payload):
    """Reject an intake that has not frozen a real settlement ledger."""
    if payload.get("ledger_status") != "FROZEN":
        raise UnfrozenMatchIntake(
            f"{payload.get('match_id', 'match')} ledger is "
            f"{payload.get('ledger_status', 'UNKNOWN')}; refusing numeric use"
        )
    for clip in payload["clips"]:
        settlement = clip.get("settlement")
        if settlement in (None, "UNKNOWN") or not isinstance(settlement, dict):
            raise UnfrozenMatchIntake(
                f"clip {clip.get('index')} settlement is not frozen"
            )
        if clip.get("sha256") in (None, "", "HASH_UNKNOWN"):
            raise UnfrozenMatchIntake(
                f"clip {clip.get('index')} source hash is unknown"
            )
    return payload
