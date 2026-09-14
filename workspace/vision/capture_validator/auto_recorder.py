"""Conservative visual phase detection and per-hand recording orchestration."""
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
import time
import uuid

import cv2
import numpy as np
from PIL import Image

from .media import Recorder


class HandPhase(str, Enum):
    WAITING = "WAITING"
    OPENING = "OPENING"
    PLAYING = "PLAYING"
    SETTLEMENT = "SETTLEMENT"


@dataclass(frozen=True)
class PhaseDetection:
    phase: str | None
    confidence: float
    method: str = "uncertain"


@dataclass(frozen=True)
class BufferedFrame:
    jpeg: bytes
    source: dict
    monotonic: float
    wall_time: float

    def image(self):
        array = cv2.imdecode(np.frombuffer(self.jpeg, np.uint8), cv2.IMREAD_COLOR)
        if array is None:
            raise RuntimeError("环形缓存帧解码失败")
        return Image.fromarray(cv2.cvtColor(array, cv2.COLOR_BGR2RGB))


class FrameRingBuffer:
    """JPEG-compressed rolling frames to bound long-running preview memory."""

    def __init__(self, seconds=10, jpeg_quality=85):
        if seconds <= 0:
            raise ValueError("环形缓存时长必须为正数")
        self.seconds = seconds
        self.jpeg_quality = jpeg_quality
        self.frames = deque()

    def append(self, image, source, monotonic_time, wall_time):
        bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
        ok, encoded = cv2.imencode(
            ".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
        )
        if not ok:
            raise RuntimeError("环形缓存帧压缩失败")
        self.frames.append(BufferedFrame(
            encoded.tobytes(), dict(source), monotonic_time, wall_time
        ))
        cutoff = monotonic_time - self.seconds
        while self.frames and self.frames[0].monotonic < cutoff:
            self.frames.popleft()

    def snapshot(self):
        return tuple(self.frames)


class TemplatePhaseDetector:
    """Fixed-ROI template comparison; no tile or Mahjong-rule recognition."""

    DEFAULT_ROIS = {
        HandPhase.OPENING.value: (0.08, 0.05, 0.92, 0.82),
        HandPhase.SETTLEMENT.value: (0.08, 0.05, 0.92, 0.95),
    }

    def __init__(self, templates=None, threshold=0.94, rois=None):
        if not 0 < threshold <= 1:
            raise ValueError("模板阈值必须在 0 到 1 之间")
        self.threshold = threshold
        self.rois = dict(self.DEFAULT_ROIS if rois is None else rois)
        self.templates = {phase: [] for phase in self.rois}
        for phase, paths in (templates or {}).items():
            if phase not in self.rois:
                raise ValueError(f"未知视觉阶段：{phase}")
            for path in paths:
                with Image.open(path) as image:
                    self.templates[phase].append(
                        self._feature(image.convert("RGB"), self.rois[phase])
                    )

    @classmethod
    def from_project_evidence(cls, project_root, threshold=0.94):
        folder = Path(project_root) / "references" / "capture_review" / "2026-09-13"
        return cls({
            HandPhase.OPENING.value: [
                folder / "opening_gold_dice_and_room_settings.jpg",
                folder / "opening_gold_reveal_wall_108.jpg",
            ],
            HandPhase.SETTLEMENT.value: [
                folder / "liuju_zero_settlement.jpg",
                folder / "pinghu_11_settlement.jpg",
                folder / "pinghu_16_settlement.jpg",
                folder / "zimo_38_kong_settlement.jpg",
            ],
        }, threshold=threshold)

    @staticmethod
    def _feature(image, roi):
        width, height = image.size
        left, top, right, bottom = roi
        crop = image.crop((int(left * width), int(top * height),
                           int(right * width), int(bottom * height)))
        gray = cv2.cvtColor(
            np.asarray(crop.resize((192, 108))), cv2.COLOR_RGB2GRAY
        )
        return cv2.equalizeHist(gray)

    def detect(self, image):
        best_phase, best_score = None, -1.0
        for phase, templates in self.templates.items():
            if not templates:
                continue
            feature = self._feature(image, self.rois[phase])
            score = max(float(cv2.matchTemplate(
                feature, template, cv2.TM_CCOEFF_NORMED
            )[0, 0]) for template in templates)
            if score > best_score:
                best_phase, best_score = phase, score
        if best_phase is None or best_score < self.threshold:
            return PhaseDetection(
                None, max(0.0, best_score), "fixed_roi_template"
            )
        return PhaseDetection(
            best_phase, best_score, "fixed_roi_template"
        )


class AutoHandRecorder:
    """WAITING → OPENING → PLAYING → SETTLEMENT → WAITING."""

    def __init__(self, folder, metadata_factory, detector, *, fps=10,
                 pre_roll_seconds=10, post_roll_seconds=5, confirm_frames=3):
        if post_roll_seconds < 0 or confirm_frames < 1:
            raise ValueError("自动录像参数无效")
        self.folder = Path(folder)
        self.metadata_factory = metadata_factory
        self.detector = detector
        self.fps = fps
        self.post_roll_seconds = post_roll_seconds
        self.confirm_frames = confirm_frames
        self.buffer = FrameRingBuffer(pre_roll_seconds)
        self.state = HandPhase.WAITING
        self.recorder = None
        self._candidate = object()
        self._candidate_count = 0
        self._settlement_deadline = None
        self.completed = []

    def _stable(self, phase):
        if self._candidate == phase:
            self._candidate_count += 1
        else:
            self._candidate, self._candidate_count = phase, 1
        return self._candidate_count >= self.confirm_frames

    def _transition(self, phase, detection, monotonic_time, wall_time):
        self.state = phase
        if self.recorder:
            self.recorder.mark_phase(
                phase.value, monotonic_time, wall_time,
                detection.confidence, detection.method
            )

    def _start_hand(self, detection, monotonic_time, wall_time):
        buffered = self.buffer.snapshot()
        first = buffered[0]
        hand_id = (
            f"{datetime.fromtimestamp(wall_time):%Y%m%d_%H%M%S}_"
            f"{uuid.uuid4().hex[:8]}"
        )
        metadata = dict(self.metadata_factory())
        metadata["mode"] = "AUTO_HAND"
        size = buffered[-1].image().size
        self.recorder = Recorder(
            self.folder, size, metadata, seconds=None, fps=self.fps,
            prefix=f"hand_{hand_id}", hand_id=hand_id,
            started=first.monotonic, started_at=first.wall_time
        )
        for frame in buffered:
            self.recorder.append(
                frame.image(), frame.source, frame.monotonic,
                HandPhase.WAITING.value
            )
        self._transition(
            HandPhase.OPENING, detection, monotonic_time, wall_time
        )

    def process(self, image, source, monotonic_time=None, wall_time=None):
        monotonic_time = (
            time.monotonic() if monotonic_time is None else monotonic_time
        )
        wall_time = time.time() if wall_time is None else wall_time
        self.buffer.append(image, source, monotonic_time, wall_time)
        detection = self.detector.detect(image)
        stable = self._stable(detection.phase)

        if self.state == HandPhase.WAITING:
            if stable and detection.phase == HandPhase.OPENING.value:
                self._start_hand(
                    detection, monotonic_time, wall_time
                )
            return None

        self.recorder.append(
            image, source, monotonic_time, self.state.value
        )
        if self.state == HandPhase.OPENING:
            if stable and detection.phase != HandPhase.OPENING.value:
                self._transition(
                    HandPhase.PLAYING, detection, monotonic_time, wall_time
                )
        elif self.state == HandPhase.PLAYING:
            if (stable
                    and detection.phase == HandPhase.SETTLEMENT.value):
                self._transition(
                    HandPhase.SETTLEMENT, detection,
                    monotonic_time, wall_time
                )
                self._settlement_deadline = (
                    monotonic_time + self.post_roll_seconds
                )
        elif (self.state == HandPhase.SETTLEMENT
              and monotonic_time >= self._settlement_deadline):
            return self.close("检测到结算页并完成 5 秒后录制")
        return None

    def close(self, reason="手动停止自动录制"):
        if not self.recorder:
            self.state = HandPhase.WAITING
            return None
        recording, self.recorder = self.recorder, None
        path = recording.close(reason)
        self.completed.append(path)
        self.state = HandPhase.WAITING
        self._candidate = object()
        self._candidate_count = 0
        self._settlement_deadline = None
        return path
