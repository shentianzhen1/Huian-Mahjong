"""Compare local video reports at shared, pixel-identical endpoint frames."""
import argparse
from collections import Counter
import json
from pathlib import Path


def _endpoints(report):
    endpoints = {}
    for row in report["rows"]:
        frame = row["frames"][-1]
        digest = row["pixel_sha256"][-1]
        if frame in endpoints or not digest:
            raise ValueError(f"Duplicate endpoint or missing pixel hash at frame {frame}")
        endpoints[frame] = (digest, row)
    return endpoints


def _discard_tiles(row):
    if not row["display_allowed"] or row["hint"]["phase"] != "POST_DRAW":
        return frozenset()
    return frozenset(item["discard"] for item in row["hint"]["best_discards"])


def compare_video_reports(baseline, candidate):
    """Measure sampled output changes without inferring correctness or recall."""
    left_source, right_source = baseline["source"], candidate["source"]
    if not left_source.get("sha256") or left_source["sha256"] != right_source.get("sha256"):
        raise ValueError("Replay source SHA256 mismatch")
    for key in ("start_seconds", "requested_duration_seconds", "session", "reference_packet",
                "advice_policy", "gold_hand_boundary_policy"):
        if left_source.get(key) != right_source.get(key):
            raise ValueError(f"Replay configuration differs: {key}")
    if baseline.get("identity_threshold") != candidate.get("identity_threshold"):
        raise ValueError("Replay identity thresholds differ")
    if any(report.get("decode_error") or report.get("stopped_early")
           for report in (baseline, candidate)):
        raise ValueError("Comparison requires completed replay reports")
    left, right = _endpoints(baseline), _endpoints(candidate)
    shared = left.keys() & right.keys()
    if not shared:
        raise ValueError("No shared replay endpoints")
    changes = Counter()
    changed_frames = {}
    for frame in sorted(shared):
        left_digest, before = left[frame]
        right_digest, after = right[frame]
        if left_digest != right_digest:
            raise ValueError(f"Replay endpoint pixel SHA256 mismatch at frame {frame}")
        before_discard, after_discard = _discard_tiles(before), _discard_tiles(after)
        labels = []
        if before["display_allowed"] != after["display_allowed"]:
            labels.append("advice_gained" if after["display_allowed"] else "advice_lost")
        elif before["display_allowed"]:
            if before["hint"]["shanten"] != after["hint"]["shanten"]:
                labels.append("shanten_changed")
            if before["hint"]["phase"] != after["hint"]["phase"]:
                labels.append("phase_changed")
        if bool(before_discard) != bool(after_discard):
            labels.append("discard_gained" if after_discard else "discard_lost")
        elif before_discard != after_discard:
            labels.append("discard_set_changed")
        if labels:
            changes.update(labels)
            changed_frames[frame] = labels
    return {
        "development_only": True,
        "shared_endpoints": len(shared),
        "baseline_only_endpoints": len(left.keys() - shared),
        "candidate_only_endpoints": len(right.keys() - shared),
        "candidate_only_advice": sum(right[frame][1]["display_allowed"] for frame in right.keys() - shared),
        "candidate_only_discards": sum(bool(_discard_tiles(right[frame][1])) for frame in right.keys() - shared),
        "shared_endpoint_changes": dict(changes),
        "changed_frames": changed_frames,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    try:
        comparison = compare_video_reports(
            json.loads(args.baseline.read_text(encoding="utf-8")),
            json.loads(args.candidate.read_text(encoding="utf-8")),
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()
