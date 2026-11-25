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
    gained_from = Counter()
    lost_to = Counter()
    for frame in sorted(shared):
        left_digest, before = left[frame]
        right_digest, after = right[frame]
        if left_digest != right_digest:
            raise ValueError(f"Replay endpoint pixel SHA256 mismatch at frame {frame}")
        before_discard, after_discard = _discard_tiles(before), _discard_tiles(after)
        labels = []
        if before["display_allowed"] != after["display_allowed"]:
            if after["display_allowed"]:
                labels.append("advice_gained")
                gained_from[(before.get("diagnostics") or {}).get("primary_advice_blocker") or "unreported"] += 1
            else:
                labels.append("advice_lost")
                lost_to[(after.get("diagnostics") or {}).get("primary_advice_blocker") or "unreported"] += 1
        elif before["display_allowed"]:
            left_snapshot = before.get("snapshot") or {}
            right_snapshot = after.get("snapshot") or {}
            if "own_hand" in left_snapshot and "own_hand" in right_snapshot:
                if Counter(left_snapshot["own_hand"]) != Counter(right_snapshot["own_hand"]):
                    labels.append("concealed_hand_changed")
            if "gold_tile" in left_snapshot and "gold_tile" in right_snapshot:
                if left_snapshot["gold_tile"] != right_snapshot["gold_tile"]:
                    labels.append("gold_changed")
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
        "advice_gained_from_blockers": dict(gained_from),
        "advice_lost_to_blockers": dict(lost_to),
        "changed_frames": changed_frames,
    }


def check_reviewed_endpoints(report, evidence):
    """Check a completed replay against reviewed current-frame inputs and hints."""
    if report.get("decode_error") or report.get("stopped_early"):
        raise ValueError("Reviewed endpoint check requires a completed replay")
    source_sha = report["source"].get("sha256")
    matches = [
        source for source in evidence["sources"]
        if source_sha and source["source_sha256"] == source_sha
    ]
    if len(matches) != 1 or not matches[0]["frames"]:
        raise ValueError("Expected one nonempty reviewed source for this replay SHA256")

    endpoints = _endpoints(report)
    issues_by_frame = {}
    seen = set()
    for expected in matches[0]["frames"]:
        frame = expected["frame"]
        if frame in seen:
            raise ValueError(f"Duplicate reviewed frame {frame}")
        seen.add(frame)
        if frame not in endpoints:
            issues_by_frame[frame] = ["endpoint_missing"]
            continue
        digest, row = endpoints[frame]
        if digest != expected["pixel_sha256"]:
            issues_by_frame[frame] = ["endpoint_pixel_mismatch"]
            continue
        if row["display_allowed"] is not True:
            issues_by_frame[frame] = ["advice_blocked"]
            continue
        snapshot, hint = row["snapshot"], row["hint"]
        observed = {
            "hand": Counter(snapshot["own_hand"]),
            "gold": snapshot["gold_tile"],
            "own_meld_count": len(snapshot["melds"][0]),
            "phase": hint["phase"],
            "shanten": hint["shanten"],
            "discards": _discard_tiles(row),
        }
        reference = {**expected, "hand": Counter(expected["hand"]),
                     "discards": frozenset(expected["discards"])}
        mismatches = [key for key, value in observed.items() if value != reference[key]]
        if mismatches:
            issues_by_frame[frame] = mismatches
    return {
        "development_only": True,
        "reviewed_endpoints": len(seen),
        "matching_endpoints": len(seen) - len(issues_by_frame),
        "issues_by_frame": issues_by_frame,
    }


def reviewed_draw_coverage(report, inventory):
    """Count observed discard displays within reviewed source-frame intervals."""
    source_sha = report["source"].get("sha256")
    if not source_sha or source_sha != inventory.get("source_sha256"):
        raise ValueError("Draw inventory source SHA256 mismatch")
    if report.get("decode_error") or report.get("stopped_early"):
        raise ValueError("Draw coverage requires a completed replay")
    endpoints = _endpoints(report)
    if not endpoints:
        raise ValueError("Draw coverage requires replay endpoints")
    first, last = min(endpoints), max(endpoints)
    flowers = set(inventory["flower_episode_indices"])
    covered = {}
    missed = []
    outside = []
    discard_frames = sorted(frame for frame, (_, row) in endpoints.items() if _discard_tiles(row))
    for index, episode in enumerate(inventory["episodes"]):
        if index in flowers:
            continue
        start, end = episode["start"], episode["end"]
        if start > end:
            raise ValueError(f"Invalid draw interval at episode {index}")
        if start < first or end > last:
            outside.append(index)
            continue
        first_discard = next((frame for frame in discard_frames if start <= frame <= end), None)
        if first_discard is None:
            missed.append(index)
        else:
            covered[index] = {
                "first_discard_frame": first_discard,
                "frames_after_interval_start": first_discard - start,
            }
    return {
        "development_only": True,
        "eligible_episodes": len(covered) + len(missed),
        "covered_episodes": covered,
        "missed_episodes": missed,
        "outside_report_episodes": outside,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--reviewed", type=Path, help="Check candidate against reviewed frames")
    parser.add_argument("--draw-inventory", type=Path, help="Count coverage within reviewed draw intervals")
    args = parser.parse_args()
    try:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
        comparison = compare_video_reports(baseline, candidate)
        if args.reviewed is not None:
            evidence = json.loads(args.reviewed.read_text(encoding="utf-8"))
            comparison["reviewed_check"] = check_reviewed_endpoints(candidate, evidence)
        if args.draw_inventory is not None:
            inventory = json.loads(args.draw_inventory.read_text(encoding="utf-8"))
            comparison["draw_coverage"] = {
                "baseline": reviewed_draw_coverage(baseline, inventory),
                "candidate": reviewed_draw_coverage(candidate, inventory),
            }
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(comparison, indent=2))
    return int(bool(comparison.get("reviewed_check", {}).get("issues_by_frame")))


if __name__ == "__main__":
    raise SystemExit(main())
