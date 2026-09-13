from datetime import datetime
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
    def __init__(self, folder, size, metadata, seconds=30, fps=10):
        import cv2
        if not 1 <= seconds <= 120:
            raise ValueError("录屏长度应为 1–120 秒")
        self.path = unique_path(folder, "recording", ".avi")
        self.encoded_size = (size[0] + size[0] % 2, size[1] + size[1] % 2)
        self.writer = cv2.VideoWriter(str(self.path), cv2.VideoWriter_fourcc(*"MJPG"), fps, self.encoded_size)
        if not self.writer.isOpened():
            self.writer.release()
            raise RuntimeError("无法创建 MJPG AVI 录像")
        self.size, self.metadata = size, dict(metadata)
        self.frames, self.fps = 0, fps
        self.started, self.seconds = time.monotonic(), seconds
        try:
            self.timeline = self.path.with_suffix(".jsonl").open("w", encoding="utf-8")
        except Exception:
            self.writer.release()
            raise

    def append(self, image, source, now=None):
        import cv2
        now = time.monotonic() if now is None else now
        if image.size != self.size:
            raise ValueError("窗口画面尺寸变化，录像已停止，请重新录制")
        elapsed = min(max(0, now - self.started), self.seconds)
        target = max(1, int(elapsed * self.fps))
        if target - self.frames > self.fps * 2:
            raise RuntimeError("录制处理落后超过 2 秒，已停止以免掩盖掉帧")
        if target > self.frames:
            bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
            bgr = cv2.copyMakeBorder(bgr, 0, self.encoded_size[1] - self.size[1],
                                     0, self.encoded_size[0] - self.size[0], cv2.BORDER_CONSTANT)
            while self.frames < target:
                self.writer.write(bgr)
                self.timeline.write(json.dumps(dict(frame=self.frames, video_seconds=self.frames/self.fps,
                                                     source=source), ensure_ascii=False) + "\n")
                self.frames += 1
        return now - self.started >= self.seconds

    def close(self, reason="手动停止"):
        if self.writer is None:
            return self.path
        self.writer.release()
        self.writer = None
        self.timeline.close()
        self.metadata.update(frames=self.frames, fps=self.fps, video_seconds=self.frames/self.fps,
                             source_size=self.size, encoded_size=self.encoded_size,
                             stop_reason=reason, format="MJPG AVI, no audio",
                             timing="constant frame rate; duplicated source frames identified in JSONL")
        self.path.with_suffix(".json").write_text(json.dumps(self.metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.path
