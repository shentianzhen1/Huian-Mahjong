import argparse
from collections import deque
import json
from pathlib import Path
import time
import tkinter as tk
from tkinter import ttk, messagebox

from PIL import Image, ImageTk

from .backend import CaptureSession, dpi_awareness, geometry, windows
from .auto_recorder import AutoHandRecorder, TemplatePhaseDetector
from .media import FrameHealth, Recorder, snapshot

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT = PROJECT_ROOT / "data" / "capture_validation"
DURATIONS = {
    "30 秒": 30,
    "120 秒": 120,
    "10 分钟": 10 * 60,
    "30 分钟": 30 * 60,
    "手动停止": None,
}


class App(tk.Tk):
    def __init__(self, demo=False):
        super().__init__()
        self.title("惠安窗口采集验证器 Recorder V0.2")
        self.geometry("1100x760")
        self.minsize(800, 560)
        self.session = self.recorder = self.frame = self.photo = None
        self.auto_recorder = None
        self.target = None
        self.source = {}
        self.backend_name = ""
        self.health = FrameHealth()
        self.times = deque(maxlen=30)
        self.last_received = 0
        self.started = 0
        self.last_rect = None
        self.black = False
        self.demo = demo
        self.frames = 0
        self.entries = []
        self.status = tk.StringVar(value="选择小程序窗口，然后开始预览。")
        self.saved = tk.StringVar(value=f"保存位置：{OUTPUT}")
        self.backend = tk.StringVar(value="WGC")
        self.duration = tk.StringVar(value="30 秒")
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="目标窗口").grid(row=0, column=0)
        self.selector = ttk.Combobox(top, state="readonly", width=56)
        self.selector.grid(row=0, column=1, padx=6)
        ttk.Button(top, text="刷新窗口", command=self.refresh).grid(row=0, column=2)
        ttk.Combobox(top, state="readonly", textvariable=self.backend,
                     values=["WGC", "PrintWindow", "屏幕区域"], width=14).grid(row=0, column=3, padx=6)
        controls = ttk.Frame(self, padding=(10, 0, 10, 8))
        controls.pack(fill="x")
        for text, command in (("开始预览", self.start), ("停止采集", self.stop),
                              ("保存截图", self.save_snapshot),
                              ("开始手动录屏", self.record),
                              ("停止手动录屏", self.stop_recording),
                              ("开始自动按局录制", self.start_auto_recording),
                              ("停止自动录制", self.stop_auto_recording)):
            ttk.Button(controls, text=text, command=command).pack(side="left", padx=(0, 6))
        ttk.Label(controls, text="手动时长").pack(side="left")
        ttk.Combobox(controls, state="readonly", textvariable=self.duration,
                     values=list(DURATIONS), width=10).pack(side="left")
        ttk.Label(self, text="只采集画面，不操作游戏。屏幕区域后端会包含遮挡物；后端不会自动切换。",
                  padding=(10, 0, 10, 6)).pack(anchor="w")
        self.canvas = tk.Canvas(self, background="#111827", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10)
        self.canvas.bind("<Configure>", lambda _: self.render())
        ttk.Label(self, textvariable=self.status, padding=10, wraplength=1000).pack(anchor="w")
        ttk.Label(self, textvariable=self.saved, padding=(10, 0, 10, 10), wraplength=1000).pack(anchor="w")
        self.protocol("WM_DELETE_WINDOW", self.close)
        if demo:
            self.status.set("合成测试画面；没有连接任何真实窗口。")
            self.backend_name = "SYNTHETIC"
            self.started = time.monotonic()
        else:
            self.refresh()
        self.after(100, self.tick)

    def refresh(self):
        try:
            self.entries = windows()
            self.selector["values"] = [f"{title}  [PID {pid} / HWND {hwnd}]" for hwnd, pid, title in self.entries]
            if self.entries:
                index = next((i for i, entry in enumerate(self.entries) if "开心" in entry[2]), 0)
                self.selector.current(index)
        except Exception as exc:
            self.status.set(f"无法枚举窗口：{exc}")

    def start(self):
        if self.demo:
            return
        index = self.selector.current()
        if index < 0:
            messagebox.showinfo("选择窗口", "请先刷新并选择小程序窗口。")
            return
        self.stop()
        try:
            self.target = self.entries[index]
            hwnd, pid, _ = self.target
            geometry(hwnd, pid)
            self.backend_name = self.backend.get()
            self.health, self.times = FrameHealth(), deque(maxlen=30)
            self.frame = None
            self.canvas.delete("all")
            self.started = self.last_received = time.monotonic()
            self.last_rect = None
            self.session = CaptureSession(hwnd, pid, self.backend_name)
            self.status.set("正在连接窗口……")
        except Exception as exc:
            self.status.set(f"启动失败：{exc}")

    def stop(self):
        self.stop_all_recordings("采集停止")
        if self.session:
            self.session.close()
            self.session = None
        self.frame = None
        self.canvas.delete("all")
        self.status.set("已停止采集。")

    def metadata(self):
        return dict(backend=self.backend_name, target=self.target, source=self.source,
                    captured_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    capture_only=True, synthetic=self.demo)

    def usable(self):
        if self.frame is None or (not self.session and not self.demo):
            raise RuntimeError("请先开始预览并等待画面")
        if self.black:
            raise RuntimeError("疑似黑屏，请切换后端核实")
        if time.monotonic() - self.last_received > 3:
            raise RuntimeError("超过 3 秒没有新帧，可能静止或停帧；请恢复画面变化后重试")

    def save_snapshot(self):
        try:
            self.usable()
            path = snapshot(self.frame, OUTPUT, self.metadata())
            self.saved.set(f"截图已保存：{path}")
        except Exception as exc:
            messagebox.showerror("截图未保存", str(exc))

    def record(self):
        if self.recorder:
            return
        try:
            self.usable()
            if self.auto_recorder:
                raise RuntimeError("自动按局录制运行中，请先停止自动录制")
            seconds = DURATIONS[self.duration.get()]
            self.recorder = Recorder(
                OUTPUT, self.frame.size, self.metadata(), seconds
            )
            self.recorder.append(self.frame, self.source)
            self.saved.set(f"正在录屏：{self.recorder.path}")
        except Exception as exc:
            self.stop_recording("录屏启动失败")
            messagebox.showerror("录屏未开始", str(exc))

    def stop_recording(self, reason="手动停止"):
        if self.recorder:
            recording, self.recorder = self.recorder, None
            try:
                path = recording.close(reason)
                self.saved.set(f"录屏结束（{reason}）：{path}")
            except Exception as exc:
                self.saved.set(f"录屏结束，但写入记录失败：{exc}")

    def start_auto_recording(self):
        if self.auto_recorder:
            return
        try:
            self.usable()
            if self.recorder:
                raise RuntimeError("手动录屏运行中，请先停止手动录屏")
            detector = TemplatePhaseDetector.from_project_evidence(PROJECT_ROOT)
            self.auto_recorder = AutoHandRecorder(
                OUTPUT, self.metadata, detector,
                pre_roll_seconds=10, post_roll_seconds=5
            )
            self.saved.set(
                "自动按局录制已启动：等待高置信开局画面；不确定时继续等待或录制"
            )
        except Exception as exc:
            self.auto_recorder = None
            messagebox.showerror("自动录制未开始", str(exc))

    def stop_auto_recording(self, reason="手动停止自动录制"):
        if self.auto_recorder:
            automatic, self.auto_recorder = self.auto_recorder, None
            try:
                path = automatic.close(reason)
                self.saved.set(
                    f"自动录制已停止：{path}" if path
                    else "自动录制已停止；等待阶段没有生成空录像"
                )
            except Exception as exc:
                self.saved.set(f"自动录制结束，但写入记录失败：{exc}")

    def stop_all_recordings(self, reason):
        self.stop_recording(reason)
        self.stop_auto_recording(reason)

    def accept(self, item):
        _, sequence, captured, wall_time, size, pixels, rect = item
        self.frame = Image.frombytes("RGB", size, pixels)
        self.last_received = captured
        self.source = dict(sequence=sequence, monotonic=captured, unix_time=wall_time,
                           rect=rect, size=size)
        health = self.health.inspect(self.frame, captured)
        self.black = health["black"]
        self.times.append(captured)
        notes = []
        if self.black:
            notes.append("疑似黑屏")
            self.stop_all_recordings("疑似黑屏")
        if health["resized"]:
            notes.append("尺寸变化，已重新适配预览")
            self.stop_all_recordings("尺寸变化")
        if self.last_rect is not None and tuple(rect[:2]) != tuple(self.last_rect[:2]):
            notes.append("窗口位置变化")
        self.last_rect = rect
        if health["unchanged_seconds"] > 5:
            notes.append("画面长时间无变化：可能正常静止，也可能停帧")
        fps = (len(self.times)-1)/(self.times[-1]-self.times[0]) if len(self.times)>1 and self.times[-1]>self.times[0] else 0
        if self.auto_recorder:
            notes.append(f"自动录制 {self.auto_recorder.state.value}")
            path = self.auto_recorder.process(
                self.frame, self.source, captured, wall_time
            )
            if path:
                self.saved.set(f"本局自动录像已保存：{path}；继续等待下一局")
        self.status.set(f"{self.backend_name} | {size[0]}×{size[1]} | 接收 {fps:.1f} FPS | " + ("；".join(notes) or "正在接收画面（不代表识别正确）"))
        self.render()

    def render(self):
        if self.frame is None:
            return
        image = self.frame.copy()
        image.thumbnail((max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())))
        self.photo = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        self.canvas.create_image(self.canvas.winfo_width()/2, self.canvas.winfo_height()/2,
                                 image=self.photo, anchor="center")

    def tick(self):
        try:
            if self.demo:
                from PIL import ImageDraw
                image = Image.new("RGB", (960, 540), "#176658")
                draw = ImageDraw.Draw(image)
                draw.text((30, 30), f"SYNTHETIC CAPTURE TEST / frame {self.frames}", fill="white")
                draw.rectangle((30 + self.frames % 500, 180, 100 + self.frames % 500, 300), fill="#f8edcb")
                self.frames += 1
                self.accept(("frame", self.frames, time.monotonic(), time.time(), image.size, image.tobytes(), (0, 0, 960, 540)))
            elif self.session:
                geometry(self.target[0], self.target[1])
                item = self.session.read()
                if item and item[0] == "error":
                    raise RuntimeError(item[1])
                if item:
                    self.accept(item)
                if not self.session.process.is_alive():
                    raise RuntimeError("采集进程退出，请重新开始或选择其他后端")
                age = time.monotonic() - self.last_received
                if age > 3:
                    self.status.set(f"{self.backend_name}：{age:.1f} 秒无新帧；可能静止／停帧，请检查目标窗口。")
                    self.stop_all_recordings("超过 3 秒无新帧")
            if self.recorder and self.frame:
                if self.recorder.append(self.frame, self.source):
                    self.stop_recording("达到设定时长")
        except Exception as exc:
            self.stop()
            self.status.set(f"采集已停止：{exc}")
        finally:
            self.after(100, self.tick)

    def close(self):
        self.demo = False
        self.stop()
        self.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="合成画面，只用于本程序自测")
    args = parser.parse_args()
    dpi_awareness()
    App(args.demo).mainloop()


if __name__ == "__main__":
    main()
