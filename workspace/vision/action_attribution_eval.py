"""Read-only, source-scoped evaluation of public action and turn attribution.

Manual truth comes from reviewed *continuous* source intervals, never from
detector output. UNKNOWN predictions abstain; they are not successful actions.
This report is development evidence only and cannot promote Vision/Executor.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from workspace.vision.public_match_reconstruction import ReconstructedAction

SCHEMA_VERSION = "public_action_attribution_eval_v0_1"
ACTION_KINDS = frozenset({"DISCARD", "CHI", "PENG", "MING_GANG", "ADD_KONG", "HU"})
PREDICTION_KINDS = ACTION_KINDS | {"UNKNOWN_ACTION", "EVIDENCE_CONFLICT"}
ACTORS = frozenset({"player", "opponent"})
GRADES = frozenset({"DIRECT", "CORROBORATED", "INFERRED", "UNKNOWN"})
REVIEW_KINDS = frozenset({
    "synthetic_contract",
    "development_continuous_video",
    "source_disjoint_continuous_video",
})
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return number


def _nonnegative_int(value: Any, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def _refs(value: Any, name: str, *, required: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{name} must be an array")
    if any(not isinstance(ref, str) or not ref.strip() for ref in value):
        raise ValueError(f"{name} must contain nonempty strings")
    result = tuple(dict.fromkeys(value))
    if required and not result:
        raise ValueError(f"{name} must contain at least one source/frame reference")
    return result


@dataclass(frozen=True)
class ReviewedSpan:
    stream_epoch: int
    start_seconds: float
    end_seconds: float
    first_frame: int
    last_frame: int
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _nonnegative_int(self.stream_epoch, "stream_epoch")
        _number(self.start_seconds, "start_seconds")
        _number(self.end_seconds, "end_seconds")
        _nonnegative_int(self.first_frame, "first_frame")
        _nonnegative_int(self.last_frame, "last_frame")
        if self.end_seconds <= self.start_seconds or self.last_frame <= self.first_frame:
            raise ValueError("reviewed span must have positive time/frame extent")
        _refs(self.evidence_refs, "span evidence_refs", required=True)

    def includes(self, epoch: int, timestamp: float) -> bool:
        return self.stream_epoch == epoch and self.start_seconds <= timestamp <= self.end_seconds


@dataclass(frozen=True)
class TruthEvent:
    timestamp_seconds: float
    stream_epoch: int
    frame: int
    kind: str
    actor: str
    evidence_refs: tuple[str, ...]
    tile: str | None = None
    turn_actor: str | None = None

    def __post_init__(self) -> None:
        _number(self.timestamp_seconds, "truth timestamp_seconds")
        _nonnegative_int(self.stream_epoch, "truth stream_epoch")
        _nonnegative_int(self.frame, "truth frame")
        if self.kind not in ACTION_KINDS:
            raise ValueError("truth kind must be a supported public action")
        if self.actor not in ACTORS:
            raise ValueError("approved truth actor must be player or opponent")
        if self.turn_actor is not None and self.turn_actor not in ACTORS:
            raise ValueError("truth turn_actor must be player/opponent or null")
        if self.tile is not None and (not isinstance(self.tile, str) or not self.tile):
            raise ValueError("truth tile must be nonempty or null")
        _refs(self.evidence_refs, "truth evidence_refs", required=True)


@dataclass(frozen=True)
class TruthBatch:
    source_session: str
    source_sha256: str
    review_kind: str
    truth_frozen: bool
    spans: tuple[ReviewedSpan, ...]
    events: tuple[TruthEvent, ...]
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported truth schema_version")
        if not isinstance(self.source_session, str) or not self.source_session.strip():
            raise ValueError("source_session is required")
        if not isinstance(self.source_sha256, str) or not _SHA256.fullmatch(self.source_sha256):
            raise ValueError("source_sha256 must be lowercase SHA256")
        if self.review_kind not in REVIEW_KINDS:
            raise ValueError("unsupported review_kind")
        if self.truth_frozen is not True:
            raise ValueError("manual truth must be frozen before predictions are scored")
        if not self.spans:
            raise ValueError("at least one reviewed continuous interval is required")
        # A reviewer may split one recording into disjoint epochs/intervals.
        ordered = sorted(self.spans, key=lambda span: (span.stream_epoch, span.start_seconds))
        for previous, current in zip(ordered, ordered[1:]):
            if (previous.stream_epoch == current.stream_epoch
                    and previous.end_seconds >= current.start_seconds):
                raise ValueError("reviewed intervals of one epoch must not overlap")
        if not self.events:
            raise ValueError("truth events are required; zero-event reviews need an explicit future contract")
        for event in self.events:
            matching = tuple(span for span in self.spans if span.includes(
                event.stream_epoch, event.timestamp_seconds
            ))
            if len(matching) != 1:
                raise ValueError("each truth event needs exactly one reviewed interval")
            span = matching[0]
            if not span.first_frame <= event.frame <= span.last_frame:
                raise ValueError("truth frame outside its reviewed interval")


@dataclass(frozen=True)
class ActionPrediction:
    timestamp_seconds: float
    source_session: str | None
    stream_epoch: int | None
    kind: str
    actor: str
    evidence_grade: str
    evidence_refs: tuple[str, ...]
    confidence: float | None = None
    tile: str | None = None
    turn_actor: str | None = None

    def __post_init__(self) -> None:
        _number(self.timestamp_seconds, "predicted timestamp_seconds")
        if self.source_session is not None and (
            not isinstance(self.source_session, str) or not self.source_session.strip()
        ):
            raise ValueError("prediction source_session must be nonempty or null")
        if self.stream_epoch is not None:
            _nonnegative_int(self.stream_epoch, "prediction stream_epoch")
        if self.kind not in PREDICTION_KINDS:
            raise ValueError("unsupported predicted action kind")
        if self.actor not in ACTORS | {"unknown", "system"}:
            raise ValueError("unsupported predicted actor")
        if self.evidence_grade not in GRADES:
            raise ValueError("unsupported prediction evidence grade")
        if self.confidence is not None:
            confidence = _number(self.confidence, "prediction confidence")
            if confidence > 1:
                raise ValueError("prediction confidence must be between 0 and 1")
        if self.turn_actor is not None and self.turn_actor not in ACTORS | {"unknown"}:
            raise ValueError("prediction turn_actor must be player/opponent/unknown/null")
        if self.tile is not None and (not isinstance(self.tile, str) or not self.tile):
            raise ValueError("prediction tile must be nonempty or null")
        _refs(self.evidence_refs, "prediction evidence_refs")

    @property
    def abstains(self) -> bool:
        return (
            self.kind in {"UNKNOWN_ACTION", "EVIDENCE_CONFLICT"}
            or self.actor not in ACTORS
            or self.evidence_grade == "UNKNOWN"
            or self.confidence is None
            or self.confidence == 0
            or not self.evidence_refs
        )


@dataclass(frozen=True)
class PredictionBatch:
    """Capture hash must match independently reviewed truth, not just its alias."""

    source_sha256: str
    actions: tuple[ActionPrediction, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_sha256, str) or not _SHA256.fullmatch(self.source_sha256):
            raise ValueError("prediction source_sha256 must be lowercase SHA256")
        object.__setattr__(self, "actions", tuple(self.actions))


def prediction_from_action(action: ReconstructedAction) -> ActionPrediction:
    """Convert a real assembler action without inventing its turn or source."""
    details = action.details
    return ActionPrediction(
        timestamp_seconds=action.timestamp_seconds,
        source_session=details.get("source_session"),
        stream_epoch=details.get("stream_epoch"),
        kind=action.kind.value,
        actor=action.actor,
        evidence_grade=action.evidence_grade.value,
        evidence_refs=action.evidence_refs,
        confidence=action.confidence,
        tile=action.tile or action.claimed_tile,
        turn_actor=details.get("turn_actor"),
    )


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def evaluate_attribution(
    truth: TruthBatch,
    predictions: PredictionBatch,
    *,
    tolerance_seconds: float = 0.35,
) -> dict[str, Any]:
    """Match events one-to-one within a reviewed interval and capture epoch.

    Actor is deliberately *not* part of matching; a same-time wrong actor must
    be counted as an attribution error rather than a separate miss/false alert.
    Time/kind pairing is deterministic but is not a formal sequence aligner.
    """
    tolerance = _number(tolerance_seconds, "tolerance_seconds")
    if tolerance == 0:
        raise ValueError("tolerance_seconds must be positive")
    if predictions.source_sha256 != truth.source_sha256:
        raise ValueError("prediction source_sha256 does not match reviewed truth")
    predicted = predictions.actions
    in_scope: list[tuple[int, ActionPrediction]] = []
    out_of_scope: list[int] = []
    for index, item in enumerate(predicted):
        if (
            item.source_session != truth.source_session
            or item.stream_epoch is None
            or not any(span.includes(item.stream_epoch, item.timestamp_seconds)
                       for span in truth.spans)
        ):
            out_of_scope.append(index)
        else:
            in_scope.append((index, item))

    abstained = [(i, item) for i, item in in_scope if item.abstains]
    concrete = [(i, item) for i, item in in_scope if not item.abstains]
    # Prefer temporal proximity; kind equality breaks same-time ties.
    candidates: list[tuple[float, int, int, int]] = []
    for ti, event in enumerate(truth.events):
        for pi, prediction in concrete:
            if prediction.stream_epoch != event.stream_epoch:
                continue
            delta = abs(event.timestamp_seconds - prediction.timestamp_seconds)
            if delta <= tolerance:
                candidates.append((delta, int(event.kind != prediction.kind), ti, pi))
    candidates.sort()
    used_truth: set[int] = set()
    used_predictions: set[int] = set()
    aligned: list[dict[str, Any]] = []
    wrong_actor = wrong_kind = wrong_tile = 0
    exact = 0
    labeled_turns = turns_known = turns_correct = wrong_turn = 0
    for delta, _, ti, pi in candidates:
        if ti in used_truth or pi in used_predictions:
            continue
        used_truth.add(ti)
        used_predictions.add(pi)
        event = truth.events[ti]
        prediction = predicted[pi]
        kind_ok = event.kind == prediction.kind
        actor_ok = event.actor == prediction.actor
        tile_ok = event.tile is None or event.tile == prediction.tile
        if not kind_ok:
            wrong_kind += 1
        if not actor_ok:
            wrong_actor += 1
        if not tile_ok:
            wrong_tile += 1
        if kind_ok and actor_ok and tile_ok:
            exact += 1
        turn_result = "not_labeled"
        if event.turn_actor is not None:
            labeled_turns += 1
            if prediction.turn_actor in ACTORS:
                turns_known += 1
                if prediction.turn_actor == event.turn_actor:
                    turns_correct += 1
                    turn_result = "correct"
                else:
                    wrong_turn += 1
                    turn_result = "wrong"
            else:
                turn_result = "unknown"
        aligned.append({
            "truth_index": ti,
            "prediction_index": pi,
            "delta_seconds": round(delta, 6),
            "kind_correct": kind_ok,
            "actor_correct": actor_ok,
            "tile_correct": tile_ok,
            "turn_result": turn_result,
            "truth_evidence_refs": list(event.evidence_refs),
            "prediction_evidence_refs": list(prediction.evidence_refs),
        })
    missed = [i for i in range(len(truth.events)) if i not in used_truth]
    extra = [i for i, _ in concrete if i not in used_predictions]
    # An UNKNOWN near truth is evidence of abstention, not a correct action.
    truth_with_abstention = sum(
        any(a.stream_epoch == event.stream_epoch and
            abs(a.timestamp_seconds - event.timestamp_seconds) <= tolerance
            for _, a in abstained)
        for index, event in enumerate(truth.events) if index in missed
    )
    false_positive = len(extra) + len(aligned) - exact
    false_negative = len(missed) + len(aligned) - exact
    return {
        "schema_version": SCHEMA_VERSION,
        "source_session": truth.source_session,
        "source_sha256": truth.source_sha256,
        "review_kind": truth.review_kind,
        "formal_promotion_evidence": False,
        "safe_for_executor": False,
        "reviewed_intervals": len(truth.spans),
        "truth_events": len(truth.events),
        "predictions_total": len(predicted),
        "out_of_scope_prediction_indexes": out_of_scope,
        "in_scope_predictions": len(in_scope),
        "abstentions": len(abstained),
        "abstention_prediction_indexes": [i for i, _ in abstained],
        "truth_events_with_nearby_abstention_and_no_match": truth_with_abstention,
        "aligned_events": len(aligned),
        "true_positives": exact,
        "false_positives": false_positive,
        "false_negatives": false_negative,
        "wrong_kind": wrong_kind,
        "wrong_actor": wrong_actor,
        "wrong_tile": wrong_tile,
        "actor_accuracy_on_aligned": _ratio(len(aligned) - wrong_actor, len(aligned)),
        "event_precision": _ratio(exact, exact + false_positive),
        "event_recall": _ratio(exact, exact + false_negative),
        "turn_truth_labeled_on_aligned": labeled_turns,
        "turn_predictions_known": turns_known,
        "turn_correct": turns_correct,
        "turn_wrong": wrong_turn,
        "turn_unknown": labeled_turns - turns_known,
        "turn_coverage_on_labeled_aligned": _ratio(turns_known, labeled_turns),
        "turn_accuracy_when_known": _ratio(turns_correct, turns_known),
        "missed_truth_indexes": missed,
        "extra_prediction_indexes": extra,
        "matches": aligned,
        "interpretation": (
            "Development-only event/actor/turn audit against manually reviewed "
            "continuous intervals; not candidate-track APPEARED precision, "
            "independent Vision promotion or Executor clearance."
        ),
    }


def load_truth(path: str | Path) -> TruthBatch:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("truth must be a JSON object")
    spans = tuple(ReviewedSpan(
        stream_epoch=row["stream_epoch"],
        start_seconds=row["start_seconds"],
        end_seconds=row["end_seconds"],
        first_frame=row["first_frame"],
        last_frame=row["last_frame"],
        evidence_refs=_refs(row.get("evidence_refs", []), "span evidence_refs", required=True),
    ) for row in payload.get("reviewed_intervals", ()))
    events = tuple(TruthEvent(
        timestamp_seconds=row["timestamp_seconds"],
        stream_epoch=row["stream_epoch"],
        frame=row["frame"],
        kind=row["kind"],
        actor=row["actor"],
        evidence_refs=_refs(row.get("evidence_refs", []), "truth evidence_refs", required=True),
        tile=row.get("tile"),
        turn_actor=row.get("turn_actor"),
    ) for row in payload.get("events", ()))
    return TruthBatch(
        source_session=payload.get("source_session"),
        source_sha256=payload.get("source_sha256"),
        review_kind=payload.get("review_kind"),
        truth_frozen=payload.get("truth_frozen"),
        spans=spans,
        events=events,
        schema_version=payload.get("schema_version"),
    )


def load_predictions(path: str | Path) -> PredictionBatch:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported prediction file schema")
    if not isinstance(payload.get("actions"), list):
        raise ValueError("prediction file must contain an actions array")
    result: list[ActionPrediction] = []
    for row in payload["actions"]:
        result.append(ActionPrediction(
            timestamp_seconds=row["timestamp_seconds"],
            source_session=row.get("source_session"),
            stream_epoch=row.get("stream_epoch"),
            kind=row["kind"],
            actor=row["actor"],
            evidence_grade=row.get("evidence_grade", "UNKNOWN"),
            evidence_refs=_refs(row.get("evidence_refs", []), "prediction evidence_refs"),
            confidence=row.get("confidence"),
            tile=row.get("tile"),
            turn_actor=row.get("turn_actor"),
        ))
    return PredictionBatch(source_sha256=payload.get("source_sha256"), actions=tuple(result))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth", required=True, help="Frozen, human-reviewed truth JSON")
    parser.add_argument("--predictions", required=True, help="Separate machine action JSON")
    parser.add_argument("--output", required=True, help="Development-only evaluation JSON")
    parser.add_argument("--tolerance-seconds", type=float, default=0.35)
    args = parser.parse_args()
    report = evaluate_attribution(
        load_truth(args.truth),
        load_predictions(args.predictions),
        tolerance_seconds=args.tolerance_seconds,
    )
    Path(args.output).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"development-only: {report['true_positives']}/{report['truth_events']} "
        f"exact; wrong actor={report['wrong_actor']}; "
        f"turn unknown={report['turn_unknown']}; abstentions={report['abstentions']}"
    )


if __name__ == "__main__":
    main()
