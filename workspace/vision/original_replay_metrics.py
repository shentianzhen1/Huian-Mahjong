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
        for event in data[key]:
            if not isinstance(event, dict):
                raise ValueError("invalid_event")
            if (type(event.get("frame")) is not int
                    or not 0 <= event["frame"] < data["duration_frames"]
                    or event.get("kind") not in KINDS | {"UNKNOWN"}
                    or event.get("actor") not in ("SELF", "OPPONENT", "UNKNOWN")):
                raise ValueError("invalid_event_fields")
            if key == "ground_truth" and (event["kind"] == "UNKNOWN"
                    or event["actor"] == "UNKNOWN"):
                raise ValueError("ground_truth_requires_manual_adjudication")


def score_replay(data: dict, *, frame_tolerance: int = 15) -> dict:
    """One-to-one greedy nearest matching with explicit kind and actor.

    Detection: time-matched any known meld prediction regardless of kind/actor.
    Kind+actor: time-matched same kind AND same actor. For this partial metric,
    a wrong-kind/actor prediction is counted as both FP and FN. Full action\n    reconstruction also needs claimed tile and independent source provenance;\n    it is deliberately unscored here.
    """
    _validate(data)
    if type(frame_tolerance) is not int or frame_tolerance < 0:
        raise ValueError("invalid_frame_tolerance")
    truth = data["ground_truth"]
    predictions = [p for p in data["predictions"] if p["kind"] in KINDS]
    # Deterministic global nearest pairing avoids reusing one prediction.
    def match(require_identity: bool):
        pairs = []
        for ti, t in enumerate(truth):
            for pi, p in enumerate(predictions):
                distance = abs(t["frame"] - p["frame"])
                if distance <= frame_tolerance and (
                    not require_identity or
                    (t["kind"], t["actor"]) == (p["kind"], p["actor"])
                ):
                    pairs.append((distance, ti, pi))
        used_truth, used_pred = set(), set()
        for _, ti, pi in sorted(pairs):
            if ti not in used_truth and pi not in used_pred:
                used_truth.add(ti)
                used_pred.add(pi)
        return len(used_truth), len(used_pred)
    det_tp, _ = match(False)
    action_tp, _ = match(True)
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
        candidates = sorted(
            (abs(t["frame"] - p["frame"]), ti, pi)
            for ti, t in enumerate(ts) for pi, p in enumerate(ps)
            if abs(t["frame"] - p["frame"]) <= frame_tolerance
        )
        used_t, used_p = set(), set()
        for _, ti, pi in candidates:
            if ti not in used_t and pi not in used_p:
                used_t.add(ti)
                used_p.add(pi)
        by_kind[kind] = {
            "truth": len(ts), "predictions": len(ps),
            "tp": len(used_t), "fp": len(ps) - len(used_p),
            "fn": len(ts) - len(used_t),
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
