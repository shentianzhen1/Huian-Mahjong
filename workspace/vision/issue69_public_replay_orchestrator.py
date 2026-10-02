"""Issue #69 source-scoped join for independent public replay channels.

This is an orchestration layer, not an action classifier. It merges already
produced river, meld and action-area candidates into one deterministic ledger
while preserving UNKNOWN semantics. Action-area onset never becomes an action
by itself.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Sequence

from workspace.vision.issue69_claim_correlation import correlate_claims

_SHA = re.compile(r"^[a-f0-9]{64}$")
_CHANNEL_ORDER = {"river": 0, "meld": 1, "action_area": 2}
_CHANNELS = frozenset(_CHANNEL_ORDER)
_ACTORS = frozenset(("player", "opponent", "UNKNOWN"))


@dataclass(frozen=True)
class PublicReplayCandidate:
    channel: str
    timestamp_seconds: float
    frame_index: int
    actor_hint: str
    kind: str
    source_session: str
    source_sha256: str
    stream_epoch: int
    evidence_refs: tuple[str, ...]
    tile: str | None = None
    status: str = "CANDIDATE_ONLY"
    tiles: tuple[str | None, ...] = ()

    def __post_init__(self) -> None:
        if self.channel not in _CHANNELS:
            raise ValueError("unsupported public replay channel")
        if self.actor_hint not in _ACTORS:
            raise ValueError("invalid actor hint")
        if not isinstance(self.timestamp_seconds, (int, float)) or self.timestamp_seconds < 0:
            raise ValueError("timestamp must be nonnegative")
        if type(self.frame_index) is not int or self.frame_index < 0:
            raise ValueError("frame index must be nonnegative integer")
        if not self.source_session or not _SHA.fullmatch(self.source_sha256):
            raise ValueError("exact source session and SHA256 required")
        if type(self.stream_epoch) is not int or self.stream_epoch < 0:
            raise ValueError("stream epoch must be nonnegative integer")
        if not self.kind or not self.evidence_refs:
            raise ValueError("kind and evidence provenance required")
        object.__setattr__(self, "tiles", tuple(self.tiles))
        if self.status != "CANDIDATE_ONLY":
            raise ValueError("orchestrator accepts candidate-only inputs")


def assemble_public_replay_candidates(
    candidates: Sequence[PublicReplayCandidate] | Iterable[PublicReplayCandidate],
) -> dict:
    rows = tuple(candidates)
    if not rows:
        return {
            "schema_version": "issue69_public_replay_orchestrator_v0_1",
            "status": "EMPTY",
            "ledger": [],
            "conflicts": [],
            "safe_for_runtime": False,
            "safe_for_executor": False,
        }
    if any(not isinstance(row, PublicReplayCandidate) for row in rows):
        raise ValueError("all rows must be PublicReplayCandidate")

    scopes = {
        (row.source_session, row.source_sha256, row.stream_epoch)
        for row in rows
    }
    if len(scopes) != 1:
        raise ValueError("candidate streams must share exact source scope")
    if len({ref for row in rows for ref in row.evidence_refs}) != sum(
        len(row.evidence_refs) for row in rows
    ):
        raise ValueError("evidence refs must not be reused across independent channels")

    ordered = sorted(
        rows,
        key=lambda row: (
            row.timestamp_seconds,
            row.frame_index,
            _CHANNEL_ORDER[row.channel],
            row.actor_hint,
            row.kind,
        ),
    )
    conflicts = []
    by_frame: dict[int, list[PublicReplayCandidate]] = {}
    for row in ordered:
        by_frame.setdefault(row.frame_index, []).append(row)
    for frame, frame_rows in sorted(by_frame.items()):
        public = [row for row in frame_rows if row.channel in ("river", "meld")]
        actors = {row.actor_hint for row in public if row.actor_hint != "UNKNOWN"}
        if len(actors) > 1:
            conflicts.append({
                "frame_index": frame,
                "reason": "conflicting_public_actor_hints_same_frame",
                "channels": sorted({row.channel for row in public}),
            })

    ledger = []
    for row in ordered:
        semantic_kind = row.kind if row.channel in ("river", "meld") else "UNKNOWN"
        ledger.append({
            "timestamp_seconds": round(float(row.timestamp_seconds), 6),
            "frame_index": row.frame_index,
            "channel": row.channel,
            "actor_hint": row.actor_hint,
            "candidate_kind": row.kind,
            "ledger_kind": semantic_kind,
            "tile": row.tile if row.channel in ("river", "meld") else None,
            "tiles": list(row.tiles) if row.channel == "meld" else [],
            "evidence_grade": "UNKNOWN",
            "runtime_action": False,
        })
    claim_correlation = correlate_claims(
        [
            {"timestamp_seconds": row.timestamp_seconds, "actor": row.actor_hint,
             "kind": row.kind, "trusted": row.actor_hint != "UNKNOWN"}
            for row in ordered if row.channel == "river"
        ],
        [
            {"timestamp_seconds": row.timestamp_seconds, "actor": row.actor_hint,
             "kind": row.kind, "tiles": row.tiles,
             "trusted": row.actor_hint != "UNKNOWN"}
            for row in ordered if row.channel == "meld"
        ],
    )
    return {
        "schema_version": "issue69_public_replay_orchestrator_v0_1",
        "status": "CONFLICT" if conflicts else "ORDERED_CANDIDATES_ONLY",
        "source_session": ordered[0].source_session,
        "stream_epoch": ordered[0].stream_epoch,
        "ledger": ledger,
        "conflicts": conflicts,
        "corroborated_claims": claim_correlation["claims"],
        "unmatched_claim_removals": claim_correlation["unmatched_removals"],
        "unmatched_claim_melds": claim_correlation["unmatched_melds"],
        "action_area_policy": "onset_is_context_only_never_action_truth",
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }
