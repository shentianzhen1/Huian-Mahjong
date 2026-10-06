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
REPLAY_OCR_INTERVAL_SECONDS = 2.0


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
    # Offline replay values throughput over live-display latency.  A 0.30s
    # cadence still keeps a 3-sample burst within the existing <=0.8s temporal
    # gate (first-to-last ~=0.6s) while cutting short-video Runtime work by
    # roughly one third versus the earlier 0.20s cadence.
    target = 0.30
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
            ok = cap.grab()
            if not ok:
                break
            if (index - start_frame) % stride == 0:
                ok, frame = cap.retrieve()
                if not ok:
                    break
                pts = float(cap.get(cv2.CAP_PROP_POS_MSEC)) / 1000.0
                yield (
                    index,
                    pts,
                    Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)),
                )
            index += 1
    finally:
        cap.release()


class VideoTimelineAccumulator:
    """Incrementally build the same fail-closed timeline shown in the UI."""

    def __init__(self, source):
        self.source = dict(source)
        self.events = []
        self.current_hand = None
        self.current_gold = None
        self.current_scores = None
        self.current_hand_tiles = None

    def _emit(self, timestamp, kind, *, actor="system", hand_number=None, **details):
        event = {
            "timestamp_seconds": round(float(timestamp), 6),
            "actor": actor,
            "kind": kind,
            "hand_number": hand_number,
            "evidence_grade": "UNKNOWN",
            "details": details,
        }
        self.events.append(event)
        return event

    def observe(self, runtime, public):
        times = runtime.get("source_seconds") or ()
        if not times:
            return ()
        timestamp = times[-1]
        created = []
        observation = public.get("observation") if isinstance(public, dict) else None

        if observation:
            hand_number = observation.get("hand_number")
            previous_hand = self.current_hand
            hand_changed = hand_number is not None and hand_number != self.current_hand
            if hand_changed:
                self.current_hand = hand_number
                self.current_gold = None
                self.current_hand_tiles = None
                created.append(self._emit(
                    timestamp,
                    "HAND_START",
                    hand_number=hand_number,
                    total_hands=8,
                    source="public_state_ocr",
                ))

            score_pair = observation.get("score_pair")
            if score_pair is not None:
                score_pair = tuple(score_pair)
                if score_pair != self.current_scores:
                    if self.current_scores is None:
                        created.append(self._emit(
                            timestamp,
                            "SCORE_BASELINE",
                            hand_number=self.current_hand,
                            top_right=score_pair[0],
                            bottom_left=score_pair[1],
                            source="public_state_ocr",
                        ))
                    else:
                        created.append(self._emit(
                            timestamp,
                            "SETTLEMENT_SCORE_CHANGE",
                            hand_number=(
                                previous_hand if hand_changed else self.current_hand
                            ),
                            top_right_before=self.current_scores[0],
                            bottom_left_before=self.current_scores[1],
                            top_right_after=score_pair[0],
                            bottom_left_after=score_pair[1],
                            settlement_kind="UNKNOWN",
                            source="public_state_ocr",
                        ))
                    self.current_scores = score_pair

        snapshot = runtime.get("snapshot") or {}
        if snapshot.get("gold_trusted") and snapshot.get("gold_tile"):
            gold = snapshot["gold_tile"]
            if gold != self.current_gold:
                self.current_gold = gold
                created.append(self._emit(
                    timestamp,
                    "OPEN_GOLD",
                    hand_number=self.current_hand,
                    tile=gold,
                    source="runtime_vision",
                ))

        if snapshot.get("hand_trusted") and snapshot.get("own_hand"):
            tiles = tuple(sorted(snapshot["own_hand"]))
            if tiles != self.current_hand_tiles:
                self.current_hand_tiles = tiles
                created.append(self._emit(
                    timestamp,
                    "PLAYER_HAND_SNAPSHOT",
                    actor="player",
                    hand_number=self.current_hand,
                    tile_count=len(tiles),
                    tiles=list(tiles),
                    phase=(runtime.get("hint") or {}).get("phase"),
                    source="runtime_vision",
                ))
        return tuple(created)

    def to_dict(self):
        return {
            "schema_version": "hint_alpha_video_timeline_draft_v0_1",
            "source_sha256": self.source.get("sha256"),
            "source_session": self.source.get("session"),
            "status": "PARTIAL",
            "public_actions_complete": False,
            "missing_channels": [
                "river_action_identity",
                "meld_action_identity",
                "opponent_concealed_hand",
                "hu_subtype_and_settlement_semantics",
            ],
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_hint": False,
            "safe_for_executor": False,
            "events": list(self.events),
        }


def build_video_timeline(runtime_rows, public_rows, source):
    accumulator = VideoTimelineAccumulator(source)
    for index, runtime in enumerate(runtime_rows):
        public = public_rows[index] if index < len(public_rows) else {}
        accumulator.observe(runtime, public)
    return accumulator.to_dict()


def render_video_timeline_event(event):
    from workspace.vision.issue69_text_timeline import tile_text

    timestamp = event["timestamp_seconds"]
    kind = event["kind"]
    details = event.get("details") or {}
    hand_number = event.get("hand_number")
    prefix = f"{timestamp:.2f}s "
    if kind == "HAND_START":
        text = f"第{hand_number}/8局开始"
    elif kind == "OPEN_GOLD":
        text = f"开金：{tile_text(details.get('tile'))}"
    elif kind == "SCORE_BASELINE":
        text = (
            f"比分：我方 {details.get('bottom_left')} / "
            f"对方 {details.get('top_right')}"
        )
    elif kind == "SETTLEMENT_SCORE_CHANGE":
        text = (
            "比分变化："
            f"我方 {details.get('bottom_left_before')}→{details.get('bottom_left_after')}，"
            f"对方 {details.get('top_right_before')}→{details.get('top_right_after')} "
            "（结算方式 UNKNOWN）"
        )
    elif kind == "PLAYER_HAND_SNAPSHOT":
        tiles = " ".join(tile_text(tile) for tile in details.get("tiles", ()))
        text = f"我方手牌快照（{details.get('tile_count')}张）：{tiles}"
    else:
        text = f"{kind}（UNKNOWN）"
    return prefix + text


def render_video_timeline(timeline):
    lines = [
        render_video_timeline_event(event)
        for event in timeline.get("events", ())
    ]
    if not lines:
        lines.append("未形成可信流水事件；保持 UNKNOWN。")
    lines.append(
        "流水状态：PARTIAL；弃牌/吃/碰/杠等公共动作需通过 #69 公共区域证据后再升级。"
    )
    return lines


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
    sampled_public = 0
    reused_public = 0
    for row in public_rows:
        if row.get("sampled"):
            sampled_public += 1
        if row.get("reused"):
            reused_public += 1
        if row.get("error"):
            public_errors += 1
            continue
        observation = row.get("observation") or {}
        if observation and not observation.get("issues"):
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
            "sampled_windows": sampled_public,
            "reused_windows": reused_public,
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
            "ocr_interval_seconds": REPLAY_OCR_INTERVAL_SECONDS,
        }
    )

    if public_reader is None:
        from workspace.vision.tiles_v0_1.public_state_reader import PublicStateReader

        public_reader = PublicStateReader()

    runtime_resources = None
    geometry_cache = {}

    def replay_runtime_reader(
        images,
        root,
        *,
        frame_ids=None,
        session=None,
        confidence_threshold=0.82,
    ):
        # Load optional Vision dependencies only when the reader is invoked.
        # Mocked replay orchestration must remain usable in core-only installs.
        from workspace.vision.tiles_runtime_v0_2.runtime_reader import (
            prepare_runtime_resources,
            read_stable_frames,
        )

        nonlocal runtime_resources
        if runtime_resources is None:
            runtime_resources = prepare_runtime_resources(dataset_root, session)
        return read_stable_frames(
            images,
            root,
            frame_ids=frame_ids,
            session=session,
            confidence_threshold=confidence_threshold,
            resources=runtime_resources,
            geometry_cache=geometry_cache,
        )

    window = deque(maxlen=3)
    runtime_rows = []
    public_rows = []
    previous_public = None
    last_public_row = None
    last_ocr_seconds = float("-inf")
    timeline_accumulator = VideoTimelineAccumulator(source)

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
            reader=replay_runtime_reader,
        )
        runtime_rows.append(runtime)

        current_seconds = burst[-1][1]
        ocr_due = (
            last_public_row is None
            or current_seconds - last_ocr_seconds >= REPLAY_OCR_INTERVAL_SECONDS
        )
        if ocr_due:
            try:
                # Two fresh nearby frames retain the 2-vote PublicState gate
                # while avoiding OCR of the same overlapping frame three times.
                public = public_reader.read_window(
                    tuple(item[2] for item in burst[-2:]),
                    previous=previous_public,
                    minimum_votes=2,
                )
                previous_public = public.observation
                public_row = {
                    "frames": [item[0] for item in burst[-2:]],
                    "source_seconds": [item[1] for item in burst[-2:]],
                    "sampled": True,
                    "reused": False,
                    "observation": {
                        **asdict(public.observation),
                        "score_pair": (
                            list(public.observation.score_pair)
                            if public.observation.score_pair is not None
                            else None
                        ),
                    },
                }
                last_public_row = public_row
            except Exception as exc:
                public_row = {
                    "frames": [item[0] for item in burst[-2:]],
                    "source_seconds": [item[1] for item in burst[-2:]],
                    "sampled": True,
                    "reused": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            last_ocr_seconds = current_seconds
        elif last_public_row is not None:
            public_row = {
                "frames": [item[0] for item in burst],
                "source_seconds": [item[1] for item in burst],
                "sampled": False,
                "reused": True,
                "observation": dict(last_public_row.get("observation") or {}),
            }
        else:
            public_row = {
                "frames": [item[0] for item in burst],
                "source_seconds": [item[1] for item in burst],
                "sampled": False,
                "reused": False,
                "skipped": True,
            }
        public_rows.append(public_row)
        new_timeline_events = timeline_accumulator.observe(runtime, public_row)

        if on_window is not None:
            on_window(
                {
                    "window_index": len(runtime_rows),
                    "last_frame": burst[-1][0],
                    "source_seconds": burst[-1][1],
                    "runtime": runtime,
                    "public_state": public_row,
                    "timeline_events": list(new_timeline_events),
                    "timeline_lines": [
                        render_video_timeline_event(event)
                        for event in new_timeline_events
                    ],
                    "timeline_event_count": len(timeline_accumulator.events),
                    "preview": burst[-1][2],
                }
            )

        if stop_event is not None and stop_event.is_set():
            break

    if not runtime_rows:
        raise ValueError("Selected range contains fewer than three sampled frames")

    result = summarize_video_test(runtime_rows, public_rows, source)
    timeline = timeline_accumulator.to_dict()
    result["timeline"] = timeline
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
        timeline_json = output_path.with_suffix(".timeline.json")
        timeline_text = output_path.with_suffix(".timeline.txt")
        timeline_json.write_text(
            json.dumps(timeline, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        timeline_text.write_text(
            "\n".join(render_video_timeline(timeline)) + "\n",
            encoding="utf-8",
        )
        result["report_path"] = str(output_path)
        result["timeline_json_path"] = str(timeline_json)
        result["timeline_text_path"] = str(timeline_text)

    return result
