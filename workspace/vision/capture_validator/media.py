from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid

import numpy as np


def unique_path(folder, prefix, suffix):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{prefix}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}{suffix}"


class FrameHealth:
    def __init__(self):
        self.previous = None
        self.changed_at = None
        self.size = None

    def inspect(self, image, now):
        small = np.asarray(image.convert("L").resize((96, 54)), dtype=np.float32)
        changed_size = self.size is not None and self.size != image.size
        if self.previous is None or changed_size or np.mean(np.abs(small - self.previous)) > 1.5:
            self.changed_at = now
        self.previous, self.size = small, image.size
        return dict(black=bool(small.mean() < 4), resized=changed_size,
                    unchanged_seconds=now - self.changed_at)


def snapshot(image, folder, metadata):
    path = unique_path(folder, "snapshot", ".png")
    image.save(path)
    path.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class Recorder:
    def __init__(self, folder, size, metadata, seconds=30, fps=10, *,
                 prefix="recording", hand_id=None, started=None, started_at=None):
        import cv2
        if seconds is not None and (
                isinstance(seconds, bool) or not isinstance(seconds, (int, float))
                or seconds <= 0):
            raise ValueError("录屏长度必须是正数或 None（手动停止）")
        if isinstance(fps, bool) or not isinstance(fps, int) or fps <= 0:
            raise ValueError("fps 必须是正整数")
        self.path = unique_path(folder, prefix, ".avi")
        self.encoded_size = (size[0] + size[0] % 2, size[1] + size[1] % 2)
        self.writer = cv2.VideoWriter(str(self.path), cv2.VideoWriter_fourcc(*"MJPG"), fps, self.encoded_size)
        if not self.writer.isOpened():
            self.writer.release()
            raise RuntimeError("无法创建 MJPG AVI 录像")
        self.size, self.metadata = size, dict(metadata)
        self.frames, self.fps = 0, fps
        self.started = time.monotonic() if started is None else started
        self.started_wall_time = time.time() if started_at is None else started_at
        self.seconds = seconds
        self.hand_id = hand_id
        self.detected_phases = []
        try:
            self.timeline = self.path.with_suffix(".jsonl").open("w", encoding="utf-8")
        except Exception:
            self.writer.release()
            raise

    def append(self, image, source, now=None, phase=None):
        import cv2
        now = time.monotonic() if now is None else now
        if image.size != self.size:
            raise ValueError("窗口画面尺寸变化，录像已停止，请重新录制")
        elapsed = max(0, now - self.started)
        if self.seconds is not None:
            elapsed = min(elapsed, self.seconds)
        target = max(1, int(elapsed * self.fps))
        if target - self.frames > self.fps * 2:
            raise RuntimeError("录制处理落后超过 2 秒，已停止以免掩盖掉帧")
        if target > self.frames:
            bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
            bgr = cv2.copyMakeBorder(bgr, 0, self.encoded_size[1] - self.size[1],
                                     0, self.encoded_size[0] - self.size[0], cv2.BORDER_CONSTANT)
            while self.frames < target:
                self.writer.write(bgr)
                self.timeline.write(json.dumps(dict(
                    type="frame", frame=self.frames,
                    video_seconds=self.frames/self.fps, phase=phase, source=source
                ), ensure_ascii=False) + "\n")
                self.frames += 1
            self.timeline.flush()
        return self.seconds is not None and now - self.started >= self.seconds

    def mark_phase(self, phase, monotonic_time, wall_time, confidence, method):
        event = dict(
            phase=phase,
            monotonic=monotonic_time,
            timestamp=datetime.fromtimestamp(
                wall_time, timezone.utc
            ).astimezone().isoformat(),
            confidence=float(confidence),
            method=method,
        )
        self.detected_phases.append(event)
        self.timeline.write(json.dumps(
            dict(type="phase", **event), ensure_ascii=False
        ) + "\n")
        self.timeline.flush()

    def close(self, reason="手动停止"):
        if self.writer is None:
            return self.path
        self.writer.release()
        self.writer = None
        self.timeline.close()
        self.metadata.update(frames=self.frames, fps=self.fps, video_seconds=self.frames/self.fps,
                             source_size=self.size, encoded_size=self.encoded_size,
                             hand_id=self.hand_id,
                             duration_limit_seconds=self.seconds,
                             start_time=datetime.fromtimestamp(
                                 self.started_wall_time, timezone.utc
                             ).astimezone().isoformat(),
                             end_time=datetime.now().astimezone().isoformat(),
                             detected_phases=self.detected_phases,
                             stop_reason=reason, format="MJPG AVI, no audio",
                             timing="constant frame rate; duplicated source frames identified in JSONL")
        self.path.with_suffix(".json").write_text(json.dumps(self.metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.path
