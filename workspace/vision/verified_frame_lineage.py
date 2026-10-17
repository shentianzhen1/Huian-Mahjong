"""Verify 1:1 presentation-frame lineage for a private development clip.

FFprobe packet PTS values are sorted into presentation order. This verifies
timing continuity for an FFmpeg passthrough-frame derivative; it does not
certify pixel identity, Mahjong actions, or a generalization holdout.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess


def video_presentation_times(path: str | Path) -> tuple[float, ...]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "packet=pts_time", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    try:
        times = tuple(sorted(float(line.rstrip(",")) for line in
                             result.stdout.splitlines() if line.strip()))
    except ValueError as exc:
        raise ValueError("video contains invalid presentation timestamps") from exc
    if not times or any(not math.isfinite(t) or t < 0 for t in times):
        raise ValueError("video needs finite nonnegative presentation timestamps")
    if any(later <= earlier for earlier, later in zip(times, times[1:])):
        raise ValueError("video has duplicate/nonmonotonic presentation timestamps")
    return times


def verify_frame_lineage(source_pts, clip_pts, *, source_first_frame: int,
                         expected_timestamp_offset: float,
                         tolerance_seconds: float = .003,
                         sample_frames=()) -> dict:
    """Reject dropped/reordered frames and a clip with the wrong source offset.

    The expected offset is independently specified from the FFmpeg source seek
    command (for example `-ss 143.5`), not inferred from the two arrays.
    """
    if type(source_first_frame) is not int or source_first_frame < 0:
        raise ValueError("source_first_frame must be nonnegative integer")
    if (type(expected_timestamp_offset) not in (int, float)
            or not math.isfinite(expected_timestamp_offset)
            or expected_timestamp_offset < 0):
        raise ValueError("expected timestamp offset must be finite and nonnegative")
    if (type(tolerance_seconds) not in (int, float)
            or not math.isfinite(tolerance_seconds)
            or tolerance_seconds <= 0):
        raise ValueError("tolerance_seconds must be positive and finite")
    if not source_pts or not clip_pts or source_first_frame + len(clip_pts) > len(source_pts):
        raise ValueError("clip frame span exceeds source")
    for label, values in (("source", source_pts), ("clip", clip_pts)):
        if any(type(t) not in (int, float) or not math.isfinite(t) or t < 0
               for t in values) or any(b <= a for a, b in zip(values, values[1:])):
            raise ValueError(f"{label} PTS must be finite, nonnegative, and increasing")
    errors = [abs(source_pts[source_first_frame + i] - t - expected_timestamp_offset)
              for i, t in enumerate(clip_pts)]
    maximum_error = max(errors)
    if maximum_error > tolerance_seconds:
        raise ValueError(f"frame lineage mismatch at clip frame {errors.index(maximum_error)}")
    samples = {}
    for index in sample_frames:
        if type(index) is not int or not 0 <= index < len(clip_pts):
            raise ValueError("sample frame outside verified clip")
        samples[str(index)] = {
            "source_frame": source_first_frame + index,
            "source_pts_seconds": source_pts[source_first_frame + index],
            "clip_pts_seconds": clip_pts[index],
        }
    return {
        "source_frame_range": [source_first_frame, source_first_frame + len(clip_pts) - 1],
        "source_pts_seconds": [source_pts[source_first_frame],
                               source_pts[source_first_frame + len(clip_pts) - 1]],
        "clip_frames_verified": len(clip_pts),
        "maximum_timestamp_error_seconds": round(maximum_error, 6),
        "sample_frame_mapping": samples,
        "pixel_identity_verified": False,
        "action_accuracy_verified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--source-first-frame", type=int, required=True)
    parser.add_argument("--expected-offset", type=float, required=True)
    parser.add_argument("--sample-frame", type=int, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True,
                        help="private report; source-linked frame indexes must stay local")
    args = parser.parse_args()
    result = verify_frame_lineage(
        video_presentation_times(args.source), video_presentation_times(args.clip),
        source_first_frame=args.source_first_frame,
        expected_timestamp_offset=args.expected_offset,
        sample_frames=args.sample_frame,
    )
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {result['clip_frames_verified']} frames; "
          f"maximum PTS error {result['maximum_timestamp_error_seconds']}s")


if __name__ == "__main__":
    main()
