"""Structured hand timeline records with deterministic Markdown rendering.

The JSON representation is the machine-readable source. Markdown is a derived
human review artifact. Unknown values stay explicit; this module never guesses
Mahjong scoring or UI state from missing evidence.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
from typing import Any


SCHEMA_VERSION = "hand_timeline_v0_1"
TIMELINE_ACTORS = frozenset({"player", "opponent", "system", "unknown"})
EVIDENCE_LEVELS = frozenset({
    "direct_observation",
    "player_confirmed",
    "derived_from_confirmed",
    "unknown",
})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _plain_int(value: Any, name: str, *, minimum: int | None = None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer or None")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _score_pair(value: Any, name: str) -> tuple[int, int] | None:
    if value is None:
        return None
    try:
        pair = tuple(value)
    except TypeError as exc:
        raise ValueError(f"{name} must be a two-integer pair or None") from exc
    if (
        len(pair) != 2
        or any(
            isinstance(item, bool)
            or not isinstance(item, int)
            or not 0 <= item <= 2000
            for item in pair
        )
        or sum(pair) != 2000
    ):
        raise ValueError(
            f"{name} must be a physical two-integer pair conserving 2000"
        )
    return pair


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        raise ValueError("expected a sequence of strings, not one string")
    result = tuple(str(item) for item in value)
    if any(not item for item in result):
        raise ValueError("string sequence contains an empty value")
    return result


@dataclass(frozen=True)
class HandContext:
    player_seat: int | None = None
    dealer: int | None = None
    initial_scores: tuple[int, int] | None = None
    current_dealer_base: int | None = None
    gold_tile: str | None = None
    player_flowers: tuple[str, ...] = ()
    opponent_flowers: tuple[str, ...] = ()
    room_options: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, seat in (("player_seat", self.player_seat), ("dealer", self.dealer)):
            if seat is not None and (type(seat) is not int or seat not in (0, 1)):
                raise ValueError(f"{name} must be seat 0, seat 1 or None")
        object.__setattr__(self, "initial_scores", _score_pair(self.initial_scores, "initial_scores"))
        _plain_int(self.current_dealer_base, "current_dealer_base", minimum=0)
        for name in ("player_flowers", "opponent_flowers", "room_options", "notes"):
            object.__setattr__(self, name, _string_tuple(getattr(self, name)))


@dataclass(frozen=True)
class TimelineEvent:
    timestamp_seconds: float
    actor: str
    kind: str
    evidence_level: str
    tile: str | None = None
    screen_evidence: str | None = None
    state_interpretation: str | None = None
    prompt: str | None = None
    choice: str | None = None
    result: str | None = None
    evidence_refs: tuple[str, ...] = ()
    unknown_rules: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.timestamp_seconds, bool) or not isinstance(
            self.timestamp_seconds, (int, float)
        ):
            raise ValueError("timestamp_seconds must be numeric")
        if self.timestamp_seconds < 0:
            raise ValueError("timestamp_seconds must be nonnegative")
        if self.actor not in TIMELINE_ACTORS:
            raise ValueError(f"unsupported actor: {self.actor}")
        if not isinstance(self.kind, str) or not self.kind:
            raise ValueError("kind must be a nonempty string")
        if self.evidence_level not in EVIDENCE_LEVELS:
            raise ValueError(f"unsupported evidence_level: {self.evidence_level}")
        object.__setattr__(self, "timestamp_seconds", float(self.timestamp_seconds))
        object.__setattr__(self, "evidence_refs", _string_tuple(self.evidence_refs))
        object.__setattr__(self, "unknown_rules", _string_tuple(self.unknown_rules))
        if not isinstance(self.details, dict):
            raise ValueError("details must be a dictionary")
        object.__setattr__(self, "details", dict(self.details))


@dataclass(frozen=True)
class HandSettlement:
    winner: int | None = None
    win_type: str | None = None
    fan: int | None = None
    multiplier: int | None = None
    dealer_base: int | None = None
    net_score: int | None = None
    scores_before: tuple[int, int] | None = None
    scores_after: tuple[int, int] | None = None
    next_dealer: int | None = None
    evidence_level: str = "unknown"
    unknown_rules: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, seat in (("winner", self.winner), ("next_dealer", self.next_dealer)):
            if seat is not None and (type(seat) is not int or seat not in (0, 1)):
                raise ValueError(f"{name} must be seat 0, seat 1 or None")
        for name in ("fan", "multiplier", "dealer_base"):
            _plain_int(getattr(self, name), name, minimum=0)
        if self.multiplier == 0:
            raise ValueError("multiplier must be positive when known")
        _plain_int(self.net_score, "net_score")
        object.__setattr__(self, "scores_before", _score_pair(self.scores_before, "scores_before"))
        object.__setattr__(self, "scores_after", _score_pair(self.scores_after, "scores_after"))
        if self.evidence_level not in EVIDENCE_LEVELS:
            raise ValueError(f"unsupported evidence_level: {self.evidence_level}")
        object.__setattr__(self, "unknown_rules", _string_tuple(self.unknown_rules))
        object.__setattr__(self, "notes", _string_tuple(self.notes))

        if (
            self.winner is not None
            and self.scores_before is not None
            and self.scores_after is not None
            and self.net_score is not None
        ):
            observed = self.scores_after[self.winner] - self.scores_before[self.winner]
            if observed != self.net_score:
                raise ValueError("net_score does not match the observed winner score delta")


@dataclass(frozen=True)
class HandTimeline:
    evidence_id: str
    hand_index: int
    source_sha256: str | None
    duration_seconds: float | None
    geometry: str | None
    context: HandContext
    events: tuple[TimelineEvent, ...]
    settlement: HandSettlement = HandSettlement()
    source_label: str | None = None
    notes: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_id, str) or not self.evidence_id:
            raise ValueError("evidence_id must be a nonempty string")
        if type(self.hand_index) is not int or not 1 <= self.hand_index <= 8:
            raise ValueError("hand_index must be 1..8")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.source_sha256 is not None:
            value = self.source_sha256.lower()
            if not _SHA256.fullmatch(value):
                raise ValueError("source_sha256 must be a 64-character hex digest")
            object.__setattr__(self, "source_sha256", value)
        if self.duration_seconds is not None:
            if isinstance(self.duration_seconds, bool) or not isinstance(
                self.duration_seconds, (int, float)
            ) or self.duration_seconds <= 0:
                raise ValueError("duration_seconds must be positive or None")
            object.__setattr__(self, "duration_seconds", float(self.duration_seconds))
        if not isinstance(self.context, HandContext):
            raise TypeError("context must be HandContext")
        if not isinstance(self.settlement, HandSettlement):
            raise TypeError("settlement must be HandSettlement")
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(self, "notes", _string_tuple(self.notes))

        previous = -1.0
        for event in self.events:
            if not isinstance(event, TimelineEvent):
                raise TypeError("events must contain TimelineEvent values")
            if event.timestamp_seconds < previous:
                raise ValueError("timeline events must be sorted by timestamp")
            if (
                self.duration_seconds is not None
                and event.timestamp_seconds > self.duration_seconds + 1e-9
            ):
                raise ValueError("timeline event exceeds source duration")
            previous = event.timestamp_seconds

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["events"] = [asdict(event) for event in self.events]
        return data


def _event_from_dict(row: dict[str, Any]) -> TimelineEvent:
    return TimelineEvent(
        timestamp_seconds=row["timestamp_seconds"],
        actor=row["actor"],
        kind=row["kind"],
        evidence_level=row["evidence_level"],
        tile=row.get("tile"),
        screen_evidence=row.get("screen_evidence"),
        state_interpretation=row.get("state_interpretation"),
        prompt=row.get("prompt"),
        choice=row.get("choice"),
        result=row.get("result"),
        evidence_refs=tuple(row.get("evidence_refs", ())),
        unknown_rules=tuple(row.get("unknown_rules", ())),
        details=dict(row.get("details", {})),
    )


def timeline_from_dict(data: dict[str, Any]) -> HandTimeline:
    context_data = dict(data.get("context", {}))
    settlement_data = dict(data.get("settlement", {}))
    return HandTimeline(
        evidence_id=data["evidence_id"],
        hand_index=data["hand_index"],
        source_sha256=data.get("source_sha256"),
        duration_seconds=data.get("duration_seconds"),
        geometry=data.get("geometry"),
        source_label=data.get("source_label"),
        context=HandContext(
            player_seat=context_data.get("player_seat"),
            dealer=context_data.get("dealer"),
            initial_scores=context_data.get("initial_scores"),
            current_dealer_base=context_data.get("current_dealer_base"),
            gold_tile=context_data.get("gold_tile"),
            player_flowers=tuple(context_data.get("player_flowers", ())),
            opponent_flowers=tuple(context_data.get("opponent_flowers", ())),
            room_options=tuple(context_data.get("room_options", ())),
            notes=tuple(context_data.get("notes", ())),
        ),
        events=tuple(_event_from_dict(row) for row in data.get("events", ())),
        settlement=HandSettlement(
            winner=settlement_data.get("winner"),
            win_type=settlement_data.get("win_type"),
            fan=settlement_data.get("fan"),
            multiplier=settlement_data.get("multiplier"),
            dealer_base=settlement_data.get("dealer_base"),
            net_score=settlement_data.get("net_score"),
            scores_before=settlement_data.get("scores_before"),
            scores_after=settlement_data.get("scores_after"),
            next_dealer=settlement_data.get("next_dealer"),
            evidence_level=settlement_data.get("evidence_level", "unknown"),
            unknown_rules=tuple(settlement_data.get("unknown_rules", ())),
            notes=tuple(settlement_data.get("notes", ())),
        ),
        notes=tuple(data.get("notes", ())),
        schema_version=data.get("schema_version", SCHEMA_VERSION),
    )


def load_timeline(path: str | Path) -> HandTimeline:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("timeline JSON root must be an object")
    return timeline_from_dict(data)


def _display(value: Any) -> str:
    if value is None or value == "":
        return "UNKNOWN"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value) if value else "—"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _clock(seconds: float) -> str:
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"{minutes:02d}:{remainder:04.1f}"


def render_markdown(timeline: HandTimeline) -> str:
    context = timeline.context
    settlement = timeline.settlement
    lines = [
        "# Hand Timeline Log",
        "",
        "## Basic info",
        "",
        f"- Evidence ID: `{timeline.evidence_id}`",
        f"- Hand index: {timeline.hand_index}/8",
        f"- Source: {_display(timeline.source_label)}",
        f"- Source SHA256: {_display(timeline.source_sha256)}",
        f"- Duration: {_display(timeline.duration_seconds)} s",
        f"- Geometry: {_display(timeline.geometry)}",
        f"- Player seat: {_display(context.player_seat)}",
        f"- Dealer: {_display(context.dealer)}",
        f"- Initial score: {_display(context.initial_scores)}",
        f"- Current dealer base: {_display(context.current_dealer_base)}",
        f"- Gold / Jin: {_display(context.gold_tile)}",
        f"- Player flowers: {_display(context.player_flowers)}",
        f"- Opponent flowers: {_display(context.opponent_flowers)}",
        f"- Room options: {_display(context.room_options)}",
        "",
        "## Timeline",
        "",
        "| Time | Actor | Event | Tile | Screen evidence | Interpretation | Prompt / choice | Result | Evidence | UNKNOWN |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for event in timeline.events:
        prompt_choice = " / ".join(
            item for item in (event.prompt, event.choice) if item
        ) or None
        lines.append(
            "| "
            + " | ".join([
                _clock(event.timestamp_seconds),
                _display(event.actor),
                _display(event.kind),
                _display(event.tile),
                _display(event.screen_evidence),
                _display(event.state_interpretation),
                _display(prompt_choice),
                _display(event.result),
                _display(event.evidence_level),
                _display(event.unknown_rules),
            ])
            + " |"
        )

    lines.extend([
        "",
        "## Settlement",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Winner | {_display(settlement.winner)} |",
        f"| Win type | {_display(settlement.win_type)} |",
        f"| Fan | {_display(settlement.fan)} |",
        f"| Multiplier | {_display(settlement.multiplier)} |",
        f"| Dealer base | {_display(settlement.dealer_base)} |",
        f"| Net score | {_display(settlement.net_score)} |",
        f"| Scores before | {_display(settlement.scores_before)} |",
        f"| Scores after | {_display(settlement.scores_after)} |",
        f"| Next dealer | {_display(settlement.next_dealer)} |",
        f"| Evidence | {_display(settlement.evidence_level)} |",
        f"| Unknown rules | {_display(settlement.unknown_rules)} |",
    ])
    if settlement.notes:
        lines.extend(["", "Settlement notes:"])
        lines.extend(f"- {item}" for item in settlement.notes)
    if timeline.notes:
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {item}" for item in timeline.notes)
    lines.extend([
        "",
        "> JSON is the canonical machine-readable record. This Markdown file is a deterministic review view; UNKNOWN fields must remain UNKNOWN.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a hand timeline JSON file as Markdown")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    timeline = load_timeline(args.input)
    rendered = render_markdown(timeline)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
