"""Windows internal Hint Alpha V0.1 shell.

This first slice wires capture, automatic per-hand recording, PublicState
diagnostics, evidence markers and safety provenance. Tile->GameState->CurrentAgent
live advice is connected in a later slice and is deliberately shown as pending
rather than guessed.
"""
import argparse
from collections import deque
from dataclasses import asdict
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from huian.rules import DEFAULT_RULE_SNAPSHOT
from huian.version import PROJECT_VERSION
from workspace.ai import CURRENT_AGENT_NAME, CURRENT_AGENT_VERSION
from workspace.vision.capture_validator.auto_recorder import (
    AutoHandRecorder,
    TemplatePhaseDetector,
)
from workspace.vision.capture_validator.backend import (
    CaptureSession,
    dpi_awareness,
    geometry,
    windows,
)
from workspace.vision.capture_validator.media import FrameHealth
from workspace.vision.tiles_v0_1.public_state_reader import PublicStateReader

from .evidence import EvidenceSession


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT = PROJECT_ROOT / "data" / "hint_alpha"


class HintAlphaApp(tk.Tk):
    def __init__(self, demo=False):
        super().__init__()
        self.title("惠安麻将 Hint Alpha V0.1 内测")
        self.geometry("1220x760")
        self.minsize(980, 620)
        self.demo = demo

        self.session = None
        self.target = None
        self.entries = []
        self.frame = None
        self.photo = None
        self.source = {}
        self.backend_name = ""
        self.health = FrameHealth()
        self.last_received = 0.0
        self.last_rect = None
        self.black = False
        self.frames = 0

        self.evidence = None
        self.auto_recorder = None
        self.public_reader = PublicStateReader()
        self.public_previous = None
        self.public_frames = deque(maxlen=3)
        self.public_busy = False
        self.public_disabled = False
        self.public_result_queue = queue.Queue(maxsize=1)
        self.last_public_started = 0.0

        self.backend = tk.StringVar(value="WGC")
        self.auto_record = tk.BooleanVar(value=True)
        self.capture_status = tk.StringVar(value="等待选择开心麻将窗口")
        self.vision_status = tk.StringVar(value="PublicState：等待画面")
        self.hint_status = tk.StringVar(
            value="AI提示：等待实时手牌→GameState桥接；当前不会猜测"
        )
        self.evidence_status = tk.StringVar(value=f"证据目录：{OUTPUT}")
        self.version_status = tk.StringVar(
            value=(
                f"Project {PROJECT_VERSION} | "
                f"Agent {CURRENT_AGENT_NAME} {CURRENT_AGENT_VERSION} | "
                f"Rules {DEFAULT_RULE_SNAPSHOT.label} | "
                f"{DEFAULT_RULE_SNAPSHOT.fingerprint[:12]}"
            )
        )
        self._build()
        if demo:
            self.backend_name = "SYNTHETIC"
            self.capture_status.set("合成内测画面；不会连接真实游戏")
        else:
            self.refresh()
        self.after(100, self.tick)

    def _build(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="目标窗口").grid(row=0, column=0)
        self.selector = ttk.Combobox(top, state="readonly", width=54)
        self.selector.grid(row=0, column=1, padx=6)
        ttk.Button(top, text="刷新", command=self.refresh).grid(row=0, column=2)
        ttk.Combobox(
            top,
            state="readonly",
            textvariable=self.backend,
            values=["WGC", "PrintWindow", "屏幕区域"],
            width=12,
        ).grid(row=0, column=3, padx=6)
        ttk.Checkbutton(
            top, text="自动按局录制", variable=self.auto_record
        ).grid(row=0, column=4, padx=6)
        ttk.Button(top, text="开始内测", command=self.start).grid(row=0, column=5, padx=4)
        ttk.Button(top, text="停止", command=self.stop).grid(row=0, column=6)

        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        preview = ttk.Frame(body)
        sidebar = ttk.Frame(body, width=330)
        body.add(preview, weight=3)
        body.add(sidebar, weight=1)

        self.canvas = tk.Canvas(preview, background="#111827", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _: self.render())

        ttk.Label(sidebar, text="内测状态", font=("", 12, "bold")).pack(
            anchor="w", pady=(4, 8)
        )
        for variable in (
            self.capture_status,
            self.vision_status,
            self.hint_status,
            self.evidence_status,
            self.version_status,
        ):
            ttk.Label(sidebar, textvariable=variable, wraplength=310).pack(
                anchor="w", fill="x", pady=4
            )

        ttk.Separator(sidebar).pack(fill="x", pady=10)
        ttk.Label(sidebar, text="一键证据打点", font=("", 11, "bold")).pack(anchor="w")
        for text, category in (
            ("识别错了", "RECOGNITION_ERROR"),
            ("AI建议错了", "AI_ADVICE_ERROR"),
            ("发现新规则证据", "RULE_EVIDENCE"),
            ("保存结算页证据", "SETTLEMENT_PAGE"),
        ):
            ttk.Button(
                sidebar,
                text=text,
                command=lambda value=category: self.mark_feedback(value),
            ).pack(fill="x", pady=3)

        ttk.Label(
            sidebar,
            text=(
                "Alpha原则：识别不稳/规则UNKNOWN时不提供策略；"
                "Executor始终关闭。每次打点自动保存当前帧和RuleSnapshot。"
            ),
            wraplength=310,
        ).pack(anchor="w", pady=(12, 4))

    def refresh(self):
        try:
            self.entries = windows()
            self.selector["values"] = [
                f"{title} [PID {pid} / HWND {hwnd}]"
                for hwnd, pid, title in self.entries
            ]
            if self.entries:
                index = next(
                    (i for i, entry in enumerate(self.entries) if "开心" in entry[2]),
                    0,
                )
                self.selector.current(index)
        except Exception as exc:
            self.capture_status.set(f"窗口枚举失败：{exc}")

    def _start_evidence(self):
        if self.evidence:
            return
        self.evidence = EvidenceSession(
            OUTPUT,
            metadata={
                "backend": self.backend_name,
                "target": self.target,
                "synthetic": self.demo,
                "capture_only": False,
                "advisory_only": True,
            },
        )
        self.evidence_status.set(f"证据会话：{self.evidence.path}")
        self.evidence.mark("CAPTURE_STARTED", {"backend": self.backend_name})

    def start(self):
        self.stop()
        try:
            if self.demo:
                self.backend_name = "SYNTHETIC"
                self.target = ("synthetic", 0, "synthetic")
                self._start_evidence()
                self.capture_status.set("合成内测运行中")
                return

            index = self.selector.current()
            if index < 0:
                raise RuntimeError("请先选择开心麻将窗口")
            self.target = self.entries[index]
            hwnd, pid, _ = self.target
            geometry(hwnd, pid)
            self.backend_name = self.backend.get()
            self.session = CaptureSession(hwnd, pid, self.backend_name)
            self.health = FrameHealth()
            self.last_received = time.monotonic()
            self.last_rect = None
            self.public_previous = None
            self.public_frames.clear()
            self.public_disabled = False
            self._start_evidence()
            self.capture_status.set("正在连接窗口……")
        except Exception as exc:
            self.stop()
            messagebox.showerror("内测未开始", str(exc))

    def _ensure_auto_recorder(self):
        if (
            not self.auto_record.get()
            or self.auto_recorder is not None
            or self.evidence is None
            or self.frame is None
        ):
            return
        try:
            detector = TemplatePhaseDetector.from_project_evidence(PROJECT_ROOT)
            self.auto_recorder = AutoHandRecorder(
                self.evidence.recordings_path,
                self._recording_metadata,
                detector,
                pre_roll_seconds=10,
                post_roll_seconds=5,
            )
            self.evidence.mark("AUTO_RECORDING_ARMED")
        except Exception as exc:
            self.evidence.mark(
                "AUTO_RECORDING_UNAVAILABLE",
                {"error": f"{type(exc).__name__}: {exc}"},
            )
            self.evidence_status.set(f"自动按局录制不可用：{exc}")

    def _recording_metadata(self):
        return {
            "hint_alpha": True,
            "project_version": PROJECT_VERSION,
            "executor_enabled": False,
            "session_id": self.evidence.session_id if self.evidence else None,
            "backend": self.backend_name,
            "target": self.target,
            "rule_snapshot_id": DEFAULT_RULE_SNAPSHOT.fingerprint,
            "agent_version": CURRENT_AGENT_VERSION,
        }

    def stop(self):
        if self.auto_recorder:
            automatic, self.auto_recorder = self.auto_recorder, None
            try:
                path = automatic.close("Hint Alpha停止")
                if path and self.evidence:
                    self.evidence.mark("AUTO_RECORDING_CLOSED", {"path": str(path)})
            except Exception:
                pass
        if self.session:
            self.session.close()
            self.session = None
        if self.evidence:
            evidence, self.evidence = self.evidence, None
            evidence.close("capture_stopped")
        self.frame = None
        self.canvas.delete("all")
        self.capture_status.set("已停止")

    def _public_worker(self, images, previous):
        try:
            result = self.public_reader.read_window(
                images, previous=previous, minimum_votes=2
            )
            payload = ("ok", result)
        except Exception as exc:
            payload = ("error", f"{type(exc).__name__}: {exc}")
        try:
            self.public_result_queue.put_nowait(payload)
        except queue.Full:
            pass

    def _schedule_public_read(self, now):
        if (
            self.public_disabled
            or self.public_busy
            or len(self.public_frames) < 3
            or now - self.last_public_started < 1.5
        ):
            return
        self.public_busy = True
        self.last_public_started = now
        images = tuple(image.copy() for image in self.public_frames)
        threading.Thread(
            target=self._public_worker,
            args=(images, self.public_previous),
            daemon=True,
        ).start()

    def _consume_public_result(self):
        try:
            kind, value = self.public_result_queue.get_nowait()
        except queue.Empty:
            return
        self.public_busy = False
        if kind == "error":
            self.vision_status.set(f"PublicState暂不可用：{value}")
            if "OCRUnavailable" in value or "not installed" in value:
                self.public_disabled = True
            if self.evidence:
                self.evidence.mark("PUBLIC_STATE_ERROR", {"error": value})
            return
        observation = value.observation
        self.public_previous = observation
        self.vision_status.set(
            "PublicState："
            f"比分={observation.score_pair} "
            f"第{observation.hand_number or '?'}局 "
            f"余牌={observation.remaining_tiles} "
            f"issues={','.join(observation.issues) or 'none'}"
        )
        if self.evidence:
            self.evidence.mark(
                "PUBLIC_STATE",
                {"observation": asdict(observation)},
                source=self.source,
            )

    def accept(self, item):
        _, sequence, captured, wall_time, size, pixels, rect = item
        self.frame = Image.frombytes("RGB", size, pixels)
        self.last_received = captured
        self.source = {
            "sequence": sequence,
            "monotonic": captured,
            "unix_time": wall_time,
            "rect": rect,
            "size": size,
        }
        health = self.health.inspect(self.frame, captured)
        self.black = health["black"]
        if self.black:
            self.capture_status.set("疑似黑屏：停止给提示并保留证据")
            if self.evidence:
                self.evidence.mark("BLACK_FRAME", source=self.source)
            return
        self.public_frames.append(self.frame.copy())
        self._ensure_auto_recorder()
        if self.auto_recorder:
            path = self.auto_recorder.process(
                self.frame, self.source, captured, wall_time
            )
            if path and self.evidence:
                self.evidence.mark(
                    "HAND_RECORDING_SAVED", {"path": str(path)}, source=self.source
                )
        self._schedule_public_read(captured)
        self.capture_status.set(
            f"{self.backend_name} | {size[0]}×{size[1]} | "
            "正在采集；Executor OFF"
        )
        self.last_rect = rect
        self.render()

    def mark_feedback(self, category):
        if not self.evidence or self.frame is None:
            messagebox.showinfo("尚无画面", "请先开始内测并等待实时画面。")
            return
        try:
            path = self.evidence.save_frame(
                self.frame,
                category.lower(),
                source=self.source,
                payload={
                    "public_state": (
                        asdict(self.public_previous)
                        if self.public_previous is not None
                        else None
                    )
                },
            )
            if category == "SETTLEMENT_PAGE":
                self.evidence.mark(
                    "SETTLEMENT_PAGE",
                    {"frame": str(path.relative_to(self.evidence.path))},
                    source=self.source,
                )
            else:
                self.evidence.mark_feedback(
                    category,
                    payload={"frame": str(path.relative_to(self.evidence.path))},
                    source=self.source,
                )
            self.evidence_status.set(f"已打点并保存：{path.name}")
        except Exception as exc:
            messagebox.showerror("证据未保存", str(exc))

    def render(self):
        if self.frame is None:
            return
        image = self.frame.copy()
        image.thumbnail(
            (
                max(1, self.canvas.winfo_width()),
                max(1, self.canvas.winfo_height()),
            )
        )
        self.photo = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        self.canvas.create_image(
            self.canvas.winfo_width() / 2,
            self.canvas.winfo_height() / 2,
            image=self.photo,
            anchor="center",
        )

    def tick(self):
        try:
            self._consume_public_result()
            if self.demo:
                from PIL import ImageDraw

                image = Image.new("RGB", (960, 540), "#176658")
                draw = ImageDraw.Draw(image)
                draw.text(
                    (30, 30),
                    f"HINT ALPHA SYNTHETIC / frame {self.frames}",
                    fill="white",
                )
                draw.rectangle(
                    (40 + self.frames % 400, 190, 120 + self.frames % 400, 310),
                    fill="#f8edcb",
                )
                self.frames += 1
                now = time.monotonic()
                self.accept(
                    (
                        "frame",
                        self.frames,
                        now,
                        time.time(),
                        image.size,
                        image.tobytes(),
                        (0, 0, 960, 540),
                    )
                )
            elif self.session:
                geometry(self.target[0], self.target[1])
                item = self.session.read()
                if item and item[0] == "error":
                    raise RuntimeError(item[1])
                if item:
                    self.accept(item)
                if not self.session.process.is_alive():
                    raise RuntimeError("采集进程退出")
        except Exception as exc:
            if self.evidence:
                self.evidence.mark(
                    "CAPTURE_ERROR", {"error": f"{type(exc).__name__}: {exc}"}
                )
            self.capture_status.set(f"采集错误：{exc}")
        finally:
            self.after(100, self.tick)

    def close(self):
        self.demo = False
        self.stop()
        self.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--demo", action="store_true", help="只运行合成画面，验证内测壳与证据记录"
    )
    args = parser.parse_args()
    dpi_awareness()
    HintAlphaApp(demo=args.demo).mainloop()


if __name__ == "__main__":
    main()
