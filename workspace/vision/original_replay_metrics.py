"""Issue #69 original-video replay scoring; offline, read-only and stdlib only.

Inputs are manually adjudicated ground truth and machine predictions from the
SAME source video. Both carry integer frame anchors. This scorer does not run
vision and cannot create ground truth from predictions. Unknown/abstained
predictions are not false positives, but unmatched ground-truth actions remain
false negatives. Use source-disjoint videos only for formal promotion.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path

KINDS = frozenset(("CHI", "PENG", "KONG"))
_REQUIRED = ("video_id", "fps", "duration_frames", "ground_truth", "predictions")


def _validate(data: dict) -> None:
    if not isinstance(data, dict) or any(k not in data for k in _REQUIRED):
        raise ValueError("missing_required_replay_fields")
    if not isinstance(data["video_id"], str) or not data["video_id"]:
        raise ValueError("invalid_video_id")
    if (type(data["fps"]) not in (int, float) or not math.isfinite(data["fps"]) or data["fps"] <= 0
            or type(data["duration_frames"]) is not int
            or data["duration_frames"] <= 0):
        raise ValueError("invalid_duration")
    for key in ("ground_truth", "predictions"):
        if not isinstance(data[key], list):
            raise ValueError("invalid_event_list")
        seen_adjudicated: set[tuple[int, str, str]] = set()
        for event in data[key]:
            if not isinstance(event, dict):
                raise ValueError("invalid_event")
            if (type(event.get("frame")) is not int
                    or not 0 <= event["frame"] < data["duration_frames"]
                    or event.get("kind") not in KINDS | {"UNKNOWN"}
                    or event.get("actor") not in ("SELF", "OPPONENT", "UNKNOWN")):
                raise ValueError("invalid_event_fields")
            # Optional per-event provenance must agree with the manifest.
            # Reject mixed-source predictions before temporal matching.
            if "video_id" in event and event["video_id"] != data["video_id"]:
                raise ValueError("mixed_source_replay_event")
            if key == "ground_truth" and (event["kind"] == "UNKNOWN"
                    or event["actor"] == "UNKNOWN"):
                raise ValueError("ground_truth_requires_manual_adjudication")
            if key == "ground_truth":
                identity = (event["frame"], event["kind"], event["actor"])
                if identity in seen_adjudicated:
                    raise ValueError("duplicate_adjudicated_ground_truth_event")
                seen_adjudicated.add(identity)


def _maximum_frame_matches(truth: list[dict], predictions: list[dict],
                           tolerance: int, *, require_kind: bool,
                           require_actor: bool) -> int:
    """Maximum one-to-one matches, not greedy nearest (which can lose recall).

    Process the most constrained truth events first; use augmenting paths to
    reassign an earlier prediction if that permits another valid match.
    Distance and original index provide deterministic tie ordering.
    """
    options: list[list[int]] = []
    for event in truth:
        valid = [
            (abs(event["frame"] - pred["frame"]), pi)
            for pi, pred in enumerate(predictions)
            if abs(event["frame"] - pred["frame"]) <= tolerance
            and (not require_kind or event["kind"] == pred["kind"])
            and (not require_actor or event["actor"] == pred["actor"])
        ]
        options.append([pi for _, pi in sorted(valid)])
    owners: dict[int, int] = {}

    def augment(ti: int, seen: set[int]) -> bool:
        for pi in options[ti]:
            if pi in seen:
                continue
            seen.add(pi)
            if pi not in owners or augment(owners[pi], seen):
                owners[pi] = ti
                return True
        return False

    for ti in sorted(range(len(truth)), key=lambda i: (len(options[i]), i)):
        augment(ti, set())
    return len(owners)


def score_replay(data: dict, *, frame_tolerance: int = 15) -> dict:
    """Maximum-cardinality one-to-one matching with explicit kind and actor.

    Detection: time-matched any known meld prediction regardless of kind/actor.
    Kind+actor: time-matched same kind AND same actor. For this partial metric,
    a wrong-kind/actor prediction is counted as both FP and FN. Full action
    reconstruction also needs claimed tile and independent source provenance;
    it is deliberately unscored here.
    """
    _validate(data)
    if type(frame_tolerance) is not int or frame_tolerance < 0:
        raise ValueError("invalid_frame_tolerance")
    truth = data["ground_truth"]
    predictions = [p for p in data["predictions"] if p["kind"] in KINDS]
    det_tp = _maximum_frame_matches(
        truth, predictions, frame_tolerance,
        require_kind=False, require_actor=False)
    action_tp = _maximum_frame_matches(
        truth, predictions, frame_tolerance,
        require_kind=True, require_actor=True)
    duration_minutes = data["duration_frames"] / data["fps"] / 60
    def metric(tp):
        fp = len(predictions) - tp
        fn = len(truth) - tp
        return {
            "tp": tp, "fp": fp, "fn": fn,
            "recall": tp / len(truth) if truth else None,
            "precision": tp / len(predictions) if predictions else None,
            "false_positives_per_minute": fp / duration_minutes,
        }
    # A per-kind view matches only identical types and ignores actor.
    by_kind = {}
    for kind in sorted(KINDS):
        ts = [t for t in truth if t["kind"] == kind]
        ps = [p for p in predictions if p["kind"] == kind]
        matched = _maximum_frame_matches(
            ts, ps, frame_tolerance, require_kind=True, require_actor=False)
        by_kind[kind] = {
            "truth": len(ts), "predictions": len(ps),
            "tp": matched, "fp": len(ps) - matched,
            "fn": len(ts) - matched,
        }
    return {
        "schema_version": "original_replay_metrics_v0_1",
        "video_id": data["video_id"], "evaluation_type": "development_replay",
        "frame_tolerance": frame_tolerance,
        "duration_seconds": data["duration_frames"] / data["fps"],
        "adjudicated_ground_truth_events": len(truth),
        "known_machine_predictions": len(predictions),
        "abstained_predictions": len(data["predictions"]) - len(predictions),
        "meld_detection": metric(det_tp),
        "action_kind_actor_reconstruction": metric(action_tp),
        "complete_action_reconstruction": None,
        "complete_action_reason": "claimed_tile_and_independent_discard_hand_meld_provenance_not_scored",
        "by_kind": by_kind,
        "formal_source_disjoint_claim": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--frame-tolerance", type=int, default=15)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = score_replay(
        json.loads(args.manifest.read_text(encoding="utf-8")),
        frame_tolerance=args.frame_tolerance)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
