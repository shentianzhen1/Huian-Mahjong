"""Convert a closed Hint Alpha evidence session into a review-only Hand Timeline draft.

The bridge is deliberately conservative:
- the caller must choose the hand index;
- machine observations remain evidence_level="unknown";
- PublicState/OCR values are preserved only in event details, never promoted into
  HandContext or HandSettlement truth;
- settlement markers remain candidates until a human reviews the saved frame;
- no rule or score inference is performed.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from huian.evidence.timeline import (
    HandContext,
    HandSettlement,
    HandTimeline,
    TimelineEvent,
    render_markdown,
)


_ELIGIBLE_KINDS = frozenset({
    "PUBLIC_STATE",
    "SETTLEMENT_PAGE",
    "RULE_EVIDENCE",
    "RECOGNITION_ERROR",
    "AI_ADVICE_ERROR",
    "UNKNOWN_RULE",
    "HAND_RECORDING_SAVED",
    "BLACK_FRAME",
})

_PLAYER_MARKERS = frozenset({
    "RULE_EVIDENCE",
    "RECOGNITION_ERROR",
    "AI_ADVICE_ERROR",
})

_KIND_MAP = {
    "PUBLIC_STATE": "HINT_ALPHA_PUBLIC_STATE",
    "SETTLEMENT_PAGE": "SETTLEMENT_PAGE_CANDIDATE",
    "RULE_EVIDENCE": "RULE_EVIDENCE_MARKER",
    "RECOGNITION_ERROR": "RECOGNITION_ERROR",
    "AI_ADVICE_ERROR": "AI_ADVICE_ERROR",
    "UNKNOWN_RULE": "UNKNOWN_RULE",
    "HAND_RECORDING_SAVED": "HAND_RECORDING_SAVED",
    "BLACK_FRAME": "BLACK_FRAME",
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _parse_at(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("Hint Alpha event 'at' must be a nonempty ISO timestamp")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid Hint Alpha event timestamp: {value!r}") from exc


def load_closed_session(session_dir: str | Path) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Load a stable, closed Hint Alpha session.

    Live/incomplete sessions are rejected so a timeline draft cannot silently
    change while it is being reviewed.
    """
    root = Path(session_dir)
    manifest_path = root / "session.json"
    events_path = root / "events.jsonl"
    completion_path = root / "completion.json"
    for path in (manifest_path, events_path, completion_path):
        if not path.is_file():
            raise ValueError(f"closed Hint Alpha session is missing {path.name}")

    manifest = _load_json(manifest_path)
    completion = _load_json(completion_path)
    if manifest.get("session_id") != completion.get("session_id"):
        raise ValueError("session/completion IDs disagree")

    rows: list[dict[str, Any]] = []
    previous_seq = 0
    for line_number, line in enumerate(events_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"events.jsonl line {line_number} is not an object")
        seq = row.get("seq")
        if type(seq) is not int or seq <= previous_seq:
            raise ValueError("Hint Alpha event sequence must be strictly increasing")
        _parse_at(row.get("at"))
        previous_seq = seq
        rows.append(row)

    if completion.get("events_written") != len(rows):
        raise ValueError("completion events_written does not match events.jsonl")
    return manifest, tuple(rows)


def _unknown_rules(row: dict[str, Any]) -> tuple[str, ...]:
    if row.get("kind") != "UNKNOWN_RULE":
        return ()
    payload = row.get("payload")
    if not isinstance(payload, dict):
        return ()
    ids = payload.get("rule_ids", ())
    if isinstance(ids, str):
        ids = (ids,)
    return tuple(str(item) for item in ids if str(item))


def _screen_evidence(row: dict[str, Any]) -> str | None:
    payload = row.get("payload")
    if not isinstance(payload, dict):
        return None
    frame = payload.get("frame")
    if isinstance(frame, str) and frame:
        return frame
    path = payload.get("path")
    if isinstance(path, str) and path:
        return path
    return None


def _details(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "origin": "hint_alpha",
        "machine_generated_or_unreviewed": True,
        "requires_human_review": True,
        "hint_alpha_seq": row["seq"],
        "payload": dict(row.get("payload") or {}),
        "source": dict(row.get("source") or {}),
        "rule_snapshot_id": row.get("rule_snapshot_id"),
        "agent_version": row.get("agent_version"),
    }


def _interpretation(kind: str) -> str:
    if kind == "PUBLIC_STATE":
        return "Machine PublicState observation; preserved for review, not accepted as truth."
    if kind == "SETTLEMENT_PAGE":
        return "User-marked settlement-page candidate; values require human review."
    if kind == "RULE_EVIDENCE":
        return "User marked a possible rule-evidence frame; rule meaning is not inferred."
    if kind == "RECOGNITION_ERROR":
        return "User marked a recognition error for later diagnosis."
    if kind == "AI_ADVICE_ERROR":
        return "User marked an AI-advice error for later diagnosis."
    if kind == "UNKNOWN_RULE":
        return "Runtime explicitly encountered unresolved rule IDs."
    if kind == "HAND_RECORDING_SAVED":
        return "Recorder saved a hand recording reference; gameplay events are not inferred."
    if kind == "BLACK_FRAME":
        return "Capture health marked a black-frame anomaly."
    return "Unreviewed Hint Alpha event."


def build_timeline_draft(
    session_dir: str | Path,
    *,
    hand_index: int,
    start_seq: int | None = None,
    end_seq: int | None = None,
    source_sha256: str | None = None,
    source_label: str | None = None,
) -> HandTimeline:
    """Build a canonical HandTimeline object whose evidence is still UNKNOWN.

    Sequence bounds let a reviewer select one hand from a longer Hint Alpha
    session without asking the bridge to infer hand boundaries.
    """
    manifest, rows = load_closed_session(session_dir)
    if type(hand_index) is not int or not 1 <= hand_index <= 8:
        raise ValueError("hand_index must be 1..8")
    if start_seq is not None and (type(start_seq) is not int or start_seq < 1):
        raise ValueError("start_seq must be a positive integer or None")
    if end_seq is not None and (type(end_seq) is not int or end_seq < 1):
        raise ValueError("end_seq must be a positive integer or None")
    if start_seq is not None and end_seq is not None and start_seq > end_seq:
        raise ValueError("start_seq must not exceed end_seq")

    selected = [
        row
        for row in rows
        if row.get("kind") in _ELIGIBLE_KINDS
        and (start_seq is None or row["seq"] >= start_seq)
        and (end_seq is None or row["seq"] <= end_seq)
    ]
    if not selected:
        raise ValueError("selected sequence range contains no reviewable Hint Alpha events")

    base_time = _parse_at(selected[0]["at"])
    events = []
    for row in selected:
        at = _parse_at(row["at"])
        offset = (at - base_time).total_seconds()
        if offset < 0:
            raise ValueError("Hint Alpha event timestamps regress inside selected sequence")
        kind = str(row["kind"])
        events.append(
            TimelineEvent(
                timestamp_seconds=offset,
                actor="player" if kind in _PLAYER_MARKERS else "system",
                kind=_KIND_MAP[kind],
                evidence_level="unknown",
                screen_evidence=_screen_evidence(row),
                state_interpretation=_interpretation(kind),
                evidence_refs=(f"hint_alpha:{manifest['session_id']}:seq:{row['seq']}",),
                unknown_rules=_unknown_rules(row),
                details=_details(row),
            )
        )

    session_id = str(manifest["session_id"])
    return HandTimeline(
        evidence_id=f"hint_alpha_{session_id}_hand_{hand_index:02d}_draft",
        hand_index=hand_index,
        source_sha256=source_sha256,
        duration_seconds=None,
        geometry=None,
        source_label=source_label or f"Hint Alpha session {session_id}",
        context=HandContext(
            room_options=("hint_alpha_draft", "requires_human_review"),
            notes=(
                "Hand index and optional source hash are reviewer-supplied.",
                "Machine/PublicState values remain event details until manually reviewed.",
            ),
        ),
        events=tuple(events),
        settlement=HandSettlement(
            evidence_level="unknown",
            notes=("No settlement values are inferred by the Hint Alpha bridge.",),
        ),
        notes=(
            "This is a review draft, not confirmed gameplay evidence.",
            "No event is promoted above evidence_level=unknown automatically.",
        ),
    )


def write_timeline_draft(
    session_dir: str | Path,
    *,
    hand_index: int,
    output_dir: str | Path | None = None,
    start_seq: int | None = None,
    end_seq: int | None = None,
    source_sha256: str | None = None,
    source_label: str | None = None,
) -> tuple[Path, Path]:
    timeline = build_timeline_draft(
        session_dir,
        hand_index=hand_index,
        start_seq=start_seq,
        end_seq=end_seq,
        source_sha256=source_sha256,
        source_label=source_label,
    )
    root = Path(output_dir) if output_dir is not None else Path(session_dir) / "timeline_drafts"
    root.mkdir(parents=True, exist_ok=True)
    stem = f"hand_{hand_index:02d}_timeline.draft"
    json_path = root / f"{stem}.json"
    md_path = root / f"{stem}.md"
    json_path.write_text(
        json.dumps(timeline.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(timeline), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export a closed Hint Alpha session range as an UNKNOWN-only timeline draft"
    )
    parser.add_argument("--session", required=True)
    parser.add_argument("--hand", required=True, type=int)
    parser.add_argument("--start-seq", type=int)
    parser.add_argument("--end-seq", type=int)
    parser.add_argument("--source-sha256")
    parser.add_argument("--source-label")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    json_path, md_path = write_timeline_draft(
        args.session,
        hand_index=args.hand,
        start_seq=args.start_seq,
        end_seq=args.end_seq,
        source_sha256=args.source_sha256,
        source_label=args.source_label,
        output_dir=args.output_dir,
    )
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
