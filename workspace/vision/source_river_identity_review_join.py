"""Private metadata join of source-qualified river actions and unlabeled crops.

This is a review aid, not identity inference or a label-promotion path. The
three-frame observation window is explicit; ambiguous simultaneous tracks stay
ambiguous, and repeated physical tiles remain only geometry-based hints.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "source_river_identity_review_join_v0_1"


def join_review_candidates(replay: dict[str, Any], queue: dict[str, Any]) -> dict[str, Any]:
    if (replay.get("schema_version") != "source_river_action_replay_v0_1"
            or queue.get("schema_version") != "source_river_review_queue_v0_1"
            or not replay.get("source_session")
            or not replay.get("source_sha256")
            or (replay["source_session"], replay["source_sha256"])
            != (queue.get("source_session"), queue.get("source_sha256"))
            or replay.get("frame_range") != queue.get("frame_range")
            or replay.get("safe_for_executor") is not False
            or queue.get("safe_for_executor") is not False
            or queue.get("formal_promotion_evidence") is not False
            or queue.get("label_reuse_forbidden") is not True):
        raise ValueError("replay and private queue must share exact source, range, and safety contract")
    actions = replay.get("machine_predictions", {}).get("actions")
    candidates = queue.get("candidates")
    if not isinstance(actions, list) or not isinstance(candidates, list):
        raise ValueError("missing action/crop records")
    seen: set[str] = set()
    for crop in candidates:
        rid = crop.get("review_id")
        if (not isinstance(rid, str) or not rid or rid in seen
                or type(crop.get("frame")) is not int
                or type(crop.get("stream_epoch")) is not int
                or crop.get("screen_side_actor") not in ("player", "opponent")
                or crop.get("tile_id") is not None
                or crop.get("turn_actor") is not None
                or crop.get("action_kind") is not None
                or crop.get("review_status") != "pending"):
            raise ValueError("invalid or labeled private crop")
        seen.add(rid)
    rows = []
    for action in actions:
        frame = action.get("frame_index")
        if (action.get("source_session") != replay["source_session"]
                or type(frame) is not int
                or type(action.get("stream_epoch")) is not int
                or action.get("actor") not in ("player", "opponent")
                or action.get("kind") != "DISCARD"
                or action.get("evidence_grade") != "UNKNOWN"
                or action.get("tile") is not None
                or action.get("turn_actor") is not None):
            raise ValueError("join only accepts frame-anchored UNKNOWN river discards")
        # Three stable frames: appearance at frame-2, observation at frame.
        matches = sorted((crop for crop in candidates
                          if frame - 2 <= crop["frame"] <= frame
                          and crop["screen_side_actor"] == action["actor"]
                          and crop["stream_epoch"] == action["stream_epoch"]),
                         key=lambda crop: (crop["frame"], crop["review_id"]))
        rows.append({
            "frame_index": frame, "actor": action["actor"],
            "stream_epoch": action["stream_epoch"],
            "review_candidate_ids": [crop["review_id"] for crop in matches],
            "association_status": ("no_candidate" if not matches else
                                   "single_unverified" if len(matches) == 1 else
                                   "ambiguous_multiple"),
            "repeat_hint_candidate_ids": [crop["review_id"] for crop in matches
                                          if crop.get("possible_repeat_of")],
            "tile_id": None, "turn_actor": None,
        })
    associated = {rid for row in rows for rid in row["review_candidate_ids"]}
    return {
        "schema_version": SCHEMA_VERSION,
        "source_session": replay["source_session"],
        "source_sha256": replay["source_sha256"],
        "frame_range": replay["frame_range"],
        "association_window_frames": 2,
        "review_kind": "private_unlabeled_development_metadata",
        "safe_for_executor": False, "formal_promotion_evidence": False,
        "identity_inference_performed": False,
        "counts": dict(Counter(row["association_status"] for row in rows)),
        "unassociated_candidate_ids": sorted(seen - associated),
        "actions": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", required=True, help="Private source replay JSON")
    parser.add_argument("--queue", required=True, help="Private crop review_queue.json")
    parser.add_argument("--output", required=True, help="Private output OUTSIDE repository")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    repository = Path(__file__).resolve().parents[2]
    if output == repository or repository in output.parents or output.exists():
        parser.error("output must be a new private path outside repository")
    result = join_review_candidates(
        json.loads(Path(args.replay).read_text(encoding="utf-8")),
        json.loads(Path(args.queue).read_text(encoding="utf-8")),
    )
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"actions": len(result["actions"]), "counts": result["counts"],
                      "unassociated_candidates": len(result["unassociated_candidate_ids"]),
                      "safe_for_executor": False}))


if __name__ == "__main__":
    main()
