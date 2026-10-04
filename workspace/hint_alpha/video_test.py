"""Direct local-video test path for Hint Alpha.

This module deliberately bypasses media players and Windows capture.  It decodes
original video pixels, sends the same three-frame bursts through the existing
Runtime Vision replay boundary, and runs PublicState OCR on the same samples.
Reports are local development diagnostics only; they are not promotion evidence.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import asdict
import json
import math
from pathlib import Path
import time

from .replay_smoke import evaluate_burst, sha256, summarize_windows


REFERENCE_FRAME_SIZE = (2796, 1290)
DEFAULT_SAMPLE_INTERVAL_SECONDS = 0.20


def automatic_sample_interval(metadata):
    """Choose a conservative no-input replay cadence from decoded metadata.

    Three sampled frames must stay within the existing <=0.8s temporal window,
    so the automatic cadence never exceeds 0.30s.  Longer recordings use a
    slightly wider interval to keep whole-match replay practical without
    changing any Vision confidence threshold.
    """
    fps = float(metadata["fps"])
    duration = float(metadata["duration_seconds"])
    if fps <= 0 or duration <= 0:
        raise ValueError("Video metadata is invalid")
    target = 0.20 if duration <= 10 * 60 else 0.25 if duration <= 30 * 60 else 0.30
    stride = max(1, int(round(target * fps)))
    return stride / fps


def probe_video(path):
    """Return decode metadata without resizing or otherwise changing pixels."""
    import cv2

    path = Path(path)
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise ValueError("Video cannot be opened")
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if fps <= 0 or frame_count <= 0 or width <= 0 or height <= 0:
            raise ValueError("Video metadata is invalid")
    finally:
        cap.release()

    duration = frame_count / fps
    aspect = width / height
    reference_aspect = REFERENCE_FRAME_SIZE[0] / REFERENCE_FRAME_SIZE[1]
    return {
        "path": str(path),
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": duration,
        "aspect_ratio": aspect,
        "reference_frame_size": list(REFERENCE_FRAME_SIZE),
        "reference_aspect_ratio": reference_aspect,
        "aspect_ratio_delta_percent": abs(aspect / reference_aspect - 1.0) * 100.0,
    }


def iter_video_samples(
    path,
    *,
    start_seconds=0.0,
    duration_seconds=0.0,
    sample_interval_seconds=None,
    stop_event=None,
):
    """Yield source-frame samples from the original video without resizing."""
    import cv2
    from PIL import Image

    meta = probe_video(path)
    start_seconds = float(start_seconds)
    duration_seconds = float(duration_seconds)
    sample_interval_seconds = (
        automatic_sample_interval(meta)
        if sample_interval_seconds is None
        else float(sample_interval_seconds)
    )
    if (
        not math.isfinite(start_seconds)
        or start_seconds < 0
        or not math.isfinite(duration_seconds)
        or duration_seconds < 0
        or not math.isfinite(sample_interval_seconds)
        or sample_interval_seconds <= 0
    ):
        raise ValueError("Require start>=0, duration>=0 and sample interval>0")

    fps = meta["fps"]
    start_frame = min(
        meta["frame_count"] - 1,
        max(0, int(round(start_seconds * fps))),
    )
    if duration_seconds == 0:
        end_frame = meta["frame_count"]
    else:
        end_frame = min(
            meta["frame_count"],
            int(round((start_seconds + duration_seconds) * fps)),
        )
    if end_frame <= start_frame:
        raise ValueError("Selected video range is empty")

    stride = max(1, int(round(sample_interval_seconds * fps)))
    cap = cv2.VideoCapture(str(path))
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        index = start_frame
        while index < end_frame:
            if stop_event is not None and stop_event.is_set():
                return
            ok, frame = cap.read()
            if not ok:
                break
            if (index - start_frame) % stride == 0:
                pts = float(cap.get(cv2.CAP_PROP_POS_MSEC)) / 1000.0
                yield (
                    index,
                    pts,
                    Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)),
                )
            index += 1
    finally:
        cap.release()


def summarize_video_test(runtime_rows, public_rows, source):
    runtime_rows = list(runtime_rows)
    public_rows = list(public_rows)
    runtime_summary = summarize_windows(runtime_rows)

    gold_counts = Counter()
    trusted_hand_windows = 0
    trusted_gold_windows = 0
    discard_windows = 0
    for row in runtime_rows:
        snapshot = row.get("snapshot") or {}
        if snapshot.get("hand_trusted") and snapshot.get("own_hand"):
            trusted_hand_windows += 1
        if snapshot.get("gold_trusted") and snapshot.get("gold_tile"):
            trusted_gold_windows += 1
            gold_counts[snapshot["gold_tile"]] += 1
        hint = row.get("hint") or {}
        if (
            row.get("display_allowed") is True
            and hint.get("phase") == "POST_DRAW"
            and hint.get("best_discards")
        ):
            discard_windows += 1

    hand_counts = Counter()
    score_counts = Counter()
    valid_public = 0
    public_errors = 0
    for row in public_rows:
        if row.get("error"):
            public_errors += 1
            continue
        observation = row.get("observation") or {}
        if not observation.get("issues"):
            valid_public += 1
        hand = observation.get("hand_number")
        if hand is not None:
            hand_counts[str(hand)] += 1
        pair = observation.get("score_pair")
        if pair is not None:
            score_counts["/".join(str(value) for value in pair)] += 1

    accepted = sum(row.get("display_allowed") is True for row in runtime_rows)
    return {
        "schema_version": "hint_alpha_local_video_test_v0_1",
        "source": source,
        "development_only": True,
        "formal_promotion_evidence": False,
        "windows_capture_validated": False,
        "safe_for_executor": False,
        "identity_threshold": 0.82,
        "runtime": {
            "windows": len(runtime_rows),
            "accepted_windows": accepted,
            "blocked_windows": len(runtime_rows) - accepted,
            "trusted_hand_windows": trusted_hand_windows,
            "trusted_gold_windows": trusted_gold_windows,
            "discard_windows": discard_windows,
            "gold_tile_votes": dict(gold_counts.most_common()),
            **runtime_summary,
        },
        "public_state": {
            "windows": len(public_rows),
            "valid_windows": valid_public,
            "error_windows": public_errors,
            "hand_number_votes": dict(hand_counts.most_common()),
            "score_pair_votes_top_bottom": dict(score_counts.most_common()),
        },
    }


def run_video_test(
    path,
    *,
    dataset_root,
    start_seconds=0.0,
    duration_seconds=0.0,
    sample_interval_seconds=None,
    output_path=None,
    source_session=None,
    public_reader=None,
    stop_event=None,
    on_window=None,
):
    """Run original video pixels through Runtime Vision and PublicState OCR."""
    path = Path(path)
    source = probe_video(path)
    if sample_interval_seconds is None:
        sample_interval_seconds = automatic_sample_interval(source)
    digest = sha256(path)
    session = source_session or "local-video-" + digest[:16]
    source.update(
        {
            "sha256": digest,
            "session": session,
            "session_binding": (
                "explicit_original_session"
                if source_session
                else "sha_derived_no_match_exclusion_claim"
            ),
            "start_seconds": float(start_seconds),
            "requested_duration_seconds": float(duration_seconds),
            "sample_interval_seconds": float(sample_interval_seconds),
        }
    )

    if public_reader is None:
        from workspace.vision.tiles_v0_1.public_state_reader import PublicStateReader

        public_reader = PublicStateReader()

    window = deque(maxlen=3)
    runtime_rows = []
    public_rows = []
    previous_public = None

    for sample in iter_video_samples(
        path,
        start_seconds=start_seconds,
        duration_seconds=duration_seconds,
        sample_interval_seconds=sample_interval_seconds,
        stop_event=stop_event,
    ):
        window.append(sample)
        if len(window) < 3:
            continue
        burst = tuple(window)
        runtime = evaluate_burst(
            burst,
            session=session,
            dataset_root=dataset_root,
        )
        runtime_rows.append(runtime)

        try:
            public = public_reader.read_window(
                tuple(item[2] for item in burst),
                previous=previous_public,
                minimum_votes=2,
            )
            previous_public = public.observation
            public_row = {
                "frames": [item[0] for item in burst],
                "source_seconds": [item[1] for item in burst],
                "observation": {
                    **asdict(public.observation),
                    "score_pair": (
                        list(public.observation.score_pair)
                        if public.observation.score_pair is not None
                        else None
                    ),
                },
            }
        except Exception as exc:
            public_row = {
                "frames": [item[0] for item in burst],
                "source_seconds": [item[1] for item in burst],
                "error": f"{type(exc).__name__}: {exc}",
            }
        public_rows.append(public_row)

        if on_window is not None:
            on_window(
                {
                    "window_index": len(runtime_rows),
                    "last_frame": burst[-1][0],
                    "source_seconds": burst[-1][1],
                    "runtime": runtime,
                    "public_state": public_row,
                    "preview": burst[-1][2],
                }
            )

        if stop_event is not None and stop_event.is_set():
            break

    if not runtime_rows:
        raise ValueError("Selected range contains fewer than three sampled frames")

    result = summarize_video_test(runtime_rows, public_rows, source)
    result["stopped_early"] = bool(stop_event is not None and stop_event.is_set())
    result["generated_unix_time"] = time.time()
    result["rows"] = runtime_rows
    result["public_rows"] = public_rows

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result["report_path"] = str(output_path)

    return result
