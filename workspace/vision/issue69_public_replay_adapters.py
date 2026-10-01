"""Adapters from existing #69 replay reports into the public replay ledger."""
from __future__ import annotations

from workspace.vision.issue69_public_replay_orchestrator import PublicReplayCandidate


def river_report_candidates(report: dict) -> tuple[PublicReplayCandidate, ...]:
    if report.get("schema_version") != "source_river_action_replay_v0_1":
        raise ValueError("unsupported river replay report")
    source_session = report.get("source_session")
    source_sha = report.get("source_sha256")
    actions = report.get("machine_predictions", {}).get("actions", ())
    rows = []
    for index, action in enumerate(actions):
        if action.get("kind") != "DISCARD":
            continue
        refs = tuple(action.get("evidence_refs") or ())
        if not refs:
            raise ValueError("river prediction missing evidence provenance")
        frame = _frame_from_refs(refs)
        rows.append(PublicReplayCandidate(
            channel="river",
            timestamp_seconds=float(action["timestamp_seconds"]),
            frame_index=frame,
            actor_hint=action.get("actor", "UNKNOWN"),
            kind="DISCARD",
            source_session=source_session,
            source_sha256=source_sha,
            stream_epoch=int(action.get("stream_epoch", 0)),
            evidence_refs=tuple(f"river:{index}:{ref}" for ref in refs),
            tile=action.get("tile"),
        ))
    return tuple(rows)


def action_area_report_candidates(report: dict) -> tuple[PublicReplayCandidate, ...]:
    if report.get("schema_version") != "source_action_area_geometry_v0_1":
        raise ValueError("unsupported action-area replay report")
    session = report.get("source_session")
    sha = report.get("source_sha256")
    rows = []
    for index, item in enumerate(report.get("candidates", ())):
        frame = item.get("frame")
        if type(frame) is not int:
            raise ValueError("action-area candidate missing exact frame")
        rows.append(PublicReplayCandidate(
            channel="action_area",
            timestamp_seconds=float(frame),
            frame_index=frame,
            actor_hint=item.get("region_actor_hint", "UNKNOWN"),
            kind="ACTION_AREA_ONSET",
            source_session=session,
            source_sha256=sha,
            stream_epoch=0,
            evidence_refs=(f"action_area:{index}:frame:{frame}",),
        ))
    return tuple(rows)


def _frame_from_refs(refs: tuple[str, ...]) -> int:
    # Existing river observations encode exact frame provenance as a trailing
    # integer in at least one evidence ref. Do not guess when absent.
    for ref in refs:
        parts = ref.replace("=", ":").split(":")
        for token in reversed(parts):
            if token.isdigit():
                return int(token)
    raise ValueError("river evidence refs do not expose exact source frame")
