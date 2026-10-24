"""Private, development-only review of partial human events against a replay trace.

This is a triage list, not an accuracy metric. The human record has approximate
timestamps and does not certify that every action in the video was reviewed.
The replay must be generated independently before this module reads human truth.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from workspace.vision.real_video_public_probe import source_sha256


def compare_partial_hand(truth: dict, replay: dict, *, video_name: str,
                         video_sha256: str, tolerance_seconds: float = 1.5) -> dict:
    """Align supported known events for manual inspection; never compute rates."""
    if (type(tolerance_seconds) not in (int, float)
            or not math.isfinite(tolerance_seconds) or tolerance_seconds <= 0):
        raise ValueError("tolerance_seconds must be positive and finite")
    if not isinstance(truth, dict) or truth.get("source") != video_name:
        raise ValueError("human truth source filename differs from selected video")
    if not isinstance(truth.get("events"), list):
        raise ValueError("human truth events must be an array")
    trace = replay.get("machine_predictions") if isinstance(replay, dict) else None
    if (not isinstance(trace, dict) or replay.get("source_sha256") != video_sha256
            or trace.get("source_sha256") != video_sha256
            or not isinstance(trace.get("actions"), list)):
        raise ValueError("replay trace does not match selected video SHA256")
    time_window = replay.get("time_seconds")
    if (not isinstance(time_window, list) or len(time_window) != 2
            or any(type(t) not in (int, float) or not math.isfinite(t) or t < 0
                   for t in time_window)
            or time_window[1] <= time_window[0]):
        raise ValueError("replay requires a bounded decoded time window")

    predictions = trace["actions"]
    for prediction in predictions:
        if (not isinstance(prediction, dict)
                or type(prediction.get("timestamp_seconds")) not in (int, float)
                or not math.isfinite(prediction["timestamp_seconds"])
                or prediction["timestamp_seconds"] < 0):
            raise ValueError("invalid machine prediction timestamp")
    used: set[int] = set()
    rows = []
    comparable: dict[int, tuple[float, str]] = {}
    for index, event in enumerate(truth["events"]):
        if not isinstance(event, dict):
            raise ValueError("invalid human event")
        kind = event.get("type")
        when = event.get("approx_second")
        if str(event.get("verification_status", "")).startswith("REJECTED_"):
            rows.append({"truth_index": index, "status": "rejected_human_event_excluded",
                         "human_kind": kind})
            continue
        if kind == "DISCARD" and when is None:
            rows.append({"truth_index": index, "status": "no_time_anchor_review_needed",
                         "human_kind": kind})
            continue
        if type(when) in (int, float) and math.isfinite(when) and (
            when < time_window[0] or when > time_window[1]
        ):
            rows.append({"truth_index": index, "status": "outside_replay_window",
                         "human_kind": kind})
            continue
        if kind != "DISCARD":
            rows.append({"truth_index": index, "status": "outside_river_replay_scope",
                         "human_kind": kind})
            continue
        if (type(when) not in (int, float) or not math.isfinite(when)
                or when < 0 or event.get("actor") not in ("tz", "opponent")):
            raise ValueError("invalid human discard anchor or actor")
        actor = "player" if event["actor"] == "tz" else "opponent"
        comparable[index] = (when, actor)
        rows.append({"truth_index": index, "approx_second": when, "actor": actor,
                     "human_kind": kind, "human_tile": event.get("tile_or_meld"),
                     "status": "no_nearby_prediction_review_needed"})

    # Assign predictions globally, preferring the same action and actor before
    # temporal proximity. Otherwise a nearby opposite player's action can steal
    # the only prediction from a slightly later matching human event.
    edges = sorted(
        (int(p.get("kind") != "DISCARD" or p.get("actor") != actor),
         abs(p["timestamp_seconds"] - when), ti, pi)
        for ti, (when, actor) in comparable.items()
        for pi, p in enumerate(predictions)
        if abs(p["timestamp_seconds"] - when) <= tolerance_seconds
    )
    matched_truth: set[int] = set()
    for _, delta, ti, pi in edges:
        if ti in matched_truth or pi in used:
            continue
        matched_truth.add(ti)
        used.add(pi)
        row = rows[ti]
        candidate = predictions[pi]
        row.update(prediction_index=pi, time_delta_seconds=round(delta, 3),
                   machine_kind=candidate.get("kind"),
                   machine_actor=candidate.get("actor"),
                   machine_tile=candidate.get("tile"),
                   machine_grade=candidate.get("evidence_grade"))
        abstains = (candidate.get("evidence_grade") == "UNKNOWN"
                    or candidate.get("kind") in ("UNKNOWN_ACTION", "EVIDENCE_CONFLICT")
                    or candidate.get("actor") not in ("player", "opponent")
                    or candidate.get("confidence") in (None, 0)
                    or not candidate.get("evidence_refs"))
        row["status"] = (
            "abstained_prediction_nearby" if abstains else
            "candidate_same_kind_actor_review_needed"
            if candidate.get("kind") == "DISCARD" and candidate.get("actor") == row["actor"]
            else "candidate_conflict_review_needed"
        )
    return {
        "schema_version": "partial_hand_replay_diff_v0_1",
        "evaluation_type": "private_development_triage_only",
        "source_video": video_name,
        "decoded_time_window_seconds": time_window,
        "tolerance_seconds": tolerance_seconds,
        "human_record_status": truth.get("status"),
        "human_event_rows": len(rows),
        "rows": rows,
        "unpaired_machine_prediction_indexes": [
            i for i in range(len(predictions)) if i not in used
        ],
        "accuracy_metrics": None,
        "reason": "partial human truth and approximate seconds cannot certify misses, false positives or full-hand accuracy",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="private local report; do not commit source-linked event rows")
    parser.add_argument("--tolerance-seconds", type=float, default=1.5)
    args = parser.parse_args()
    # Replay was already produced without truth. Verify the actual video bytes
    # before loading the human record, so a filename alone cannot link sources.
    digest = source_sha256(args.video)
    replay = json.loads(args.replay.read_text(encoding="utf-8"))
    if replay.get("source_sha256") != digest:
        raise ValueError("replay and video SHA256 differ")
    truth = json.loads(args.truth.read_text(encoding="utf-8"))
    report = compare_partial_hand(truth, replay, video_name=args.video.name,
                                  video_sha256=digest,
                                  tolerance_seconds=args.tolerance_seconds)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(f"Review rows: {len(report['rows'])}; accuracy metrics: unavailable")


if __name__ == "__main__":
    main()
