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

from huian._legacy import env
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

from .runtime_pipeline import evaluate_runtime_report
from .evidence import EvidenceSession
from .live_guard import LiveAdviceGuard
from .manual_input import evaluate_manual_input, observed_score_entry


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT = PROJECT_ROOT / "data" / "hint_alpha"


class HintAlphaApp(tk.Tk):
    def __init__(self, demo=False, experimental_runtime_advisory=False):
        super().__init__()
        self.title("惠安麻将 Hint Alpha V0.1 内测")
        self.geometry("1220x760")
        self.minsize(980, 620)
        self.demo = demo
        self.experimental_runtime_advisory = bool(experimental_runtime_advisory)
        if self.experimental_runtime_advisory:
            self.title("惠安麻将 Hint Alpha V0.1 内测 [UNPROMOTED Runtime]")
        
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

        self.live_guard = LiveAdviceGuard()
        self.runtime_frames = deque(maxlen=3)
        self.runtime_busy = False
        self.runtime_result_queue = queue.Queue(maxsize=1)
        self.last_runtime_started = 0.0
        self.last_runtime_event_key = None
        self.manual_active = False
        self.manual_tiles = []
        self.manual_revision = 0

        # Presentation-only live view state.  These fields summarize facts that
        # existing PublicState / Runtime Vision have already accepted; they do
        # not infer new game actions or weaken any UNKNOWN gate.
        self.timeline_events = []
        self.timeline_seen = set()
        self.timeline_hand = None
        self.timeline_gold = None
        self.timeline_scores = None
        self.ui_hand_number = None
        self.ui_remaining_tiles = None
        self.ui_score_pair = None
        self.ui_gold_tile = None
        self.ui_hand_ok = False
        self.ui_gold_ok = False
        self.ui_hand_number_ok = False
        self.match_header_status = tk.StringVar(
            value="第 ? / 8 局  ｜  我方：UNKNOWN  ｜  金：UNKNOWN  ｜  剩余 ? 张"
        )
        self.score_header_status = tk.StringVar(value="我方 ?  ｜  对方 ?")
        self.table_hand_status = tk.StringVar(value="我的手牌：UNKNOWN")
        self.table_meld_status = tk.StringVar(value="我的副露：UNKNOWN")
        self.opponent_meld_status = tk.StringVar(value="对方副露：实时牌面尚未接入")
        self.turn_status = tk.StringVar(value="当前状态：等待可信状态")
        self.health_status = tk.StringVar(
            value="采集 —  ｜  手牌 —  ｜  金牌 —  ｜  局号 —  ｜  流水 PARTIAL"
        )

        self.backend = tk.StringVar(value="WGC")
        self.auto_record = tk.BooleanVar(value=True)
        self.capture_status = tk.StringVar(value="等待选择开心麻将窗口")
        self.vision_status = tk.StringVar(value="PublicState：等待画面")
        self.runtime_status = tk.StringVar(value="Runtime Vision：等待稳定3帧")
        self.hint_status = tk.StringVar(
            value="向听提示：等待可信手牌/金牌；Executor OFF"
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
        self.geometry("1320x820")
        self.minsize(1080, 680)

        top = ttk.Frame(self, padding=(10, 8))
        top.pack(fill="x")
        ttk.Label(top, text="目标窗口").grid(row=0, column=0)
        self.selector = ttk.Combobox(top, state="readonly", width=48)
        self.selector.grid(row=0, column=1, padx=6)
        ttk.Button(top, text="刷新", command=self.refresh).grid(row=0, column=2)
        ttk.Combobox(
            top,
            state="readonly",
            textvariable=self.backend,
            values=["WGC", "PrintWindow", "屏幕区域"],
            width=11,
        ).grid(row=0, column=3, padx=6)
        ttk.Checkbutton(
            top, text="自动按局录制", variable=self.auto_record
        ).grid(row=0, column=4, padx=6)
        ttk.Button(top, text="开始内测", command=self.start).grid(row=0, column=5, padx=4)
        ttk.Button(top, text="停止", command=self.stop).grid(row=0, column=6, padx=2)
        ttk.Button(top, text="人工录牌", command=self.open_manual_hand).grid(
            row=0, column=7, padx=4
        )

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        realtime = ttk.Frame(self.notebook, padding=10)
        advice = ttk.Frame(self.notebook, padding=10)
        diagnostic = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(realtime, text="实时流水")
        self.notebook.add(advice, text="AI 提示")
        self.notebook.add(diagnostic, text="识别诊断")

        # --- 实时流水：打牌时默认看的页面 ---
        header = ttk.Frame(realtime)
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(
            header, textvariable=self.match_header_status, font=("", 16, "bold")
        ).pack(side="left", anchor="w")
        ttk.Label(
            header, textvariable=self.score_header_status, font=("", 14, "bold")
        ).pack(side="right", anchor="e")

        live_body = ttk.Panedwindow(realtime, orient="horizontal")
        live_body.pack(fill="both", expand=True)

        timeline_panel = ttk.Frame(live_body, padding=(0, 0, 8, 0))
        snapshot_panel = ttk.Frame(live_body, width=360)
        live_body.add(timeline_panel, weight=3)
        live_body.add(snapshot_panel, weight=2)

        ttk.Label(
            timeline_panel, text="牌局流水", font=("", 12, "bold")
        ).pack(anchor="w", pady=(0, 6))
        timeline_wrap = ttk.Frame(timeline_panel)
        timeline_wrap.pack(fill="both", expand=True)
        self.timeline_text = tk.Text(
            timeline_wrap,
            wrap="word",
            state="disabled",
            borderwidth=0,
            padx=10,
            pady=8,
            background="#0f172a",
            foreground="#e5e7eb",
            insertbackground="#e5e7eb",
            font=("", 11),
        )
        timeline_scroll = ttk.Scrollbar(
            timeline_wrap, orient="vertical", command=self.timeline_text.yview
        )
        self.timeline_text.configure(yscrollcommand=timeline_scroll.set)
        self.timeline_text.pack(side="left", fill="both", expand=True)
        timeline_scroll.pack(side="right", fill="y")
        self.timeline_text.tag_configure("system", foreground="#facc15")
        self.timeline_text.tag_configure("self", foreground="#60a5fa")
        self.timeline_text.tag_configure("opponent", foreground="#f87171")
        self.timeline_text.tag_configure("unknown", foreground="#9ca3af")

        ttk.Label(
            snapshot_panel, text="当前桌面摘要", font=("", 12, "bold")
        ).pack(anchor="w", pady=(0, 8))
        for variable in (
            self.table_hand_status,
            self.table_meld_status,
            self.opponent_meld_status,
            self.turn_status,
        ):
            ttk.Label(
                snapshot_panel, textvariable=variable, wraplength=340, justify="left"
            ).pack(anchor="w", fill="x", pady=7)
        ttk.Separator(snapshot_panel).pack(fill="x", pady=10)
        ttk.Label(
            snapshot_panel,
            text=(
                "实时壳尚未接入双方河牌和对手副露的低层牌面识别。"
                "缺失动作保持 UNKNOWN，流水不会因单项识别失败而中断。"
            ),
            wraplength=340,
            justify="left",
        ).pack(anchor="w", fill="x")

        health = ttk.Frame(realtime)
        health.pack(fill="x", pady=(8, 0))
        ttk.Separator(health).pack(fill="x", pady=(0, 6))
        ttk.Label(
            health, textvariable=self.health_status, font=("", 10, "bold")
        ).pack(anchor="w")

        # --- AI 提示：只放牌效/建议，不混工程日志 ---
        ttk.Label(advice, text="AI 提示", font=("", 16, "bold")).pack(
            anchor="w", pady=(2, 12)
        )
        ttk.Label(
            advice,
            textvariable=self.hint_status,
            wraplength=1180,
            justify="left",
            font=("", 13),
        ).pack(anchor="w", fill="x", pady=6)
        ttk.Separator(advice).pack(fill="x", pady=10)
        ttk.Label(
            advice,
            textvariable=self.table_hand_status,
            wraplength=1180,
            justify="left",
        ).pack(anchor="w", fill="x", pady=5)
        ttk.Label(
            advice,
            textvariable=self.runtime_status,
            wraplength=1180,
            justify="left",
        ).pack(anchor="w", fill="x", pady=5)
        ttk.Label(
            advice,
            text=(
                "这里只展示通过现有 fail-closed gate 的只读结果。"
                "CurrentAgent V0.10 未因本次页面调整而升级，Executor 始终关闭。"
            ),
            wraplength=1180,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(14, 0))

        # --- 识别诊断：原来的预览和研发状态全部收进这里 ---
        body = ttk.Panedwindow(diagnostic, orient="horizontal")
        body.pack(fill="both", expand=True)
        preview = ttk.Frame(body)
        sidebar = ttk.Frame(body, width=350)
        body.add(preview, weight=3)
        body.add(sidebar, weight=1)

        self.canvas = tk.Canvas(preview, background="#111827", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _: self.render())

        ttk.Label(sidebar, text="识别诊断", font=("", 12, "bold")).pack(
            anchor="w", pady=(4, 8)
        )
        for variable in (
            self.capture_status,
            self.vision_status,
            self.runtime_status,
            self.hint_status,
            self.evidence_status,
            self.version_status,
        ):
            ttk.Label(sidebar, textvariable=variable, wraplength=330).pack(
                anchor="w", fill="x", pady=4
            )

        ttk.Separator(sidebar).pack(fill="x", pady=10)
        ttk.Button(
            sidebar,
            text="人工录分（未知规则，仅记录）",
            command=self.open_manual_score,
        ).pack(fill="x", pady=3)
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
                "诊断页保留原始采集、OCR、Runtime Vision、证据路径和版本信息。"
                "主页面不展示置信度等工程细节。"
            ),
            wraplength=330,
            justify="left",
        ).pack(anchor="w", pady=(12, 4))

        self._append_timeline(
            "unknown",
            "等待实时采集；未确认的局号、金牌或动作都会保持 UNKNOWN。",
            key=("boot",),
        )

    @staticmethod
    def _display_tile(tile):
        if not tile or tile == "UNKNOWN":
            return "UNKNOWN"
        return env.CN.get(tile, tile)

    @classmethod
    def _display_tiles(cls, tiles):
        values = [cls._display_tile(tile) for tile in tiles if tile]
        return " ".join(values) if values else "UNKNOWN"

    def _clear_timeline(self):
        self.timeline_events = []
        self.timeline_seen = set()
        self.timeline_hand = None
        self.timeline_gold = None
        self.timeline_scores = None
        if hasattr(self, "timeline_text"):
            self.timeline_text.configure(state="normal")
            self.timeline_text.delete("1.0", "end")
            self.timeline_text.configure(state="disabled")

    def _append_timeline(self, kind, text, *, key=None):
        if key is not None and key in self.timeline_seen:
            return
        if key is not None:
            self.timeline_seen.add(key)
        stamp = time.strftime("%H:%M:%S")
        row = (stamp, kind, text)
        self.timeline_events.append(row)
        if len(self.timeline_events) > 300:
            self.timeline_events = self.timeline_events[-300:]
        if not hasattr(self, "timeline_text"):
            return
        self.timeline_text.configure(state="normal")
        self.timeline_text.insert("end", f"{stamp}  {text}\n", kind)
        self.timeline_text.see("end")
        self.timeline_text.configure(state="disabled")

    def _refresh_header(self):
        hand = self.ui_hand_number if self.ui_hand_number is not None else "?"
        remaining = (
            self.ui_remaining_tiles if self.ui_remaining_tiles is not None else "?"
        )
        gold = self._display_tile(self.ui_gold_tile)
        self.match_header_status.set(
            f"第 {hand} / 8 局  ｜  我方：UNKNOWN  ｜  金：{gold}  ｜  剩余 {remaining} 张"
        )
        if self.ui_score_pair is None:
            self.score_header_status.set("我方 ?  ｜  对方 ?")
        else:
            top_right, bottom_left = self.ui_score_pair
            self.score_header_status.set(
                f"我方 {bottom_left}  ｜  对方 {top_right}"
            )

    def _refresh_health(self):
        capture_ok = self.frame is not None and not self.black
        self.health_status.set(
            "采集 "
            + ("✅" if capture_ok else "—")
            + "  ｜  手牌 "
            + ("✅" if self.ui_hand_ok else "❌")
            + "  ｜  金牌 "
            + ("✅" if self.ui_gold_ok else "❌")
            + "  ｜  局号 "
            + ("✅" if self.ui_hand_number_ok else "❌")
            + "  ｜  流水 PARTIAL"
        )

    def _begin_live_view(self, label):
        self._clear_timeline()
        self.ui_hand_number = None
        self.ui_remaining_tiles = None
        self.ui_score_pair = None
        self.ui_gold_tile = None
        self.ui_hand_ok = False
        self.ui_gold_ok = False
        self.ui_hand_number_ok = False
        self.table_hand_status.set("我的手牌：UNKNOWN")
        self.table_meld_status.set("我的副露：UNKNOWN")
        self.opponent_meld_status.set("对方副露：实时牌面尚未接入")
        self.turn_status.set("当前状态：等待可信状态")
        self._refresh_header()
        self._refresh_health()
        self._append_timeline("system", label, key=("session_start", label))

    def _update_public_view(self, observation):
        self.ui_hand_number = observation.hand_number
        self.ui_remaining_tiles = observation.remaining_tiles
        self.ui_score_pair = observation.score_pair
        self.ui_hand_number_ok = observation.hand_number is not None

        if observation.hand_number is not None and observation.hand_number != self.timeline_hand:
            self.timeline_hand = observation.hand_number
            self.timeline_gold = None
            self._append_timeline(
                "system",
                f"第 {observation.hand_number} / 8 局",
                key=("hand", observation.hand_number),
            )

        if observation.score_pair is not None and observation.score_pair != self.timeline_scores:
            self.timeline_scores = observation.score_pair
            top_right, bottom_left = observation.score_pair
            self._append_timeline(
                "system",
                f"比分：我方 {bottom_left} / 对方 {top_right}",
                key=("scores", observation.score_pair),
            )

        self._refresh_header()
        self._refresh_health()

    def _update_snapshot_view(self, snapshot, result, *, source_label):
        own_hand = tuple(snapshot.own_hand)
        trusted_hand = bool(snapshot.hand_trusted) and bool(own_hand)
        self.ui_hand_ok = trusted_hand
        self.ui_gold_ok = bool(snapshot.gold_trusted and snapshot.gold_tile)
        if trusted_hand:
            self.table_hand_status.set(
                "我的手牌：" + self._display_tiles(own_hand)
            )
        else:
            self.table_hand_status.set("我的手牌：UNKNOWN")

        own_meld_count = len(snapshot.melds[0]) if snapshot.melds else 0
        if snapshot.meld_trusted[0]:
            self.table_meld_status.set(
                f"我的副露：{own_meld_count} 组"
                + ("（牌面可能为 UNKNOWN）" if own_meld_count else "")
            )
        else:
            self.table_meld_status.set("我的副露：UNKNOWN")

        if self.ui_gold_ok:
            gold = snapshot.gold_tile
            self.ui_gold_tile = gold
            if gold != self.timeline_gold:
                old = self.timeline_gold
                self.timeline_gold = gold
                message = (
                    f"开金：{self._display_tile(gold)}"
                    if old is None
                    else f"金牌识别更新：{self._display_tile(gold)}"
                )
                self._append_timeline(
                    "system",
                    message,
                    key=("gold", self.timeline_hand, gold),
                )

        if not result.allowed:
            issue = ",".join(result.issues[:2]) or "snapshot_untrusted"
            self.turn_status.set(f"当前状态：UNKNOWN（{issue}）")
        elif result.phase == "PRE_DRAW":
            self.turn_status.set("当前状态：等待摸牌 / 结构向听可用")
        elif result.phase == "POST_DRAW":
            self.turn_status.set("当前状态：已摸牌 / 等待弃牌")
        elif result.phase == "POST_DRAW_COMPLETE":
            self.turn_status.set("当前状态：普通结构完成 / 等待规则确认")
        else:
            self.turn_status.set(f"当前状态：{result.phase or result.status}")

        if source_label == "manual":
            self._append_timeline(
                "self",
                f"人工更新当前手牌：{len(own_hand)} 张；金={self._display_tile(snapshot.gold_tile)}",
                key=("manual_snapshot", snapshot.stream_epoch),
            )
        self._refresh_header()
        self._refresh_health()

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
                "experimental_runtime_advisory": self.experimental_runtime_advisory,
            },
        )
        self.evidence_status.set(f"证据会话：{self.evidence.path}")
        self.evidence.mark(
            "MANUAL_ENTRY_STARTED" if self.backend_name == "MANUAL" else "CAPTURE_STARTED",
            {"backend": self.backend_name},
        )

    def start(self):
        self.stop()
        if self.evidence is not None:
            messagebox.showerror("内测未开始", "上次证据会话关闭失败，请先处理保存错误再重试。")
            return
        try:
            if self.demo:
                self.backend_name = "SYNTHETIC"
                self.target = ("synthetic", 0, "synthetic")
                self._start_evidence()
                self._begin_live_view("合成内测开始")
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
            self.public_result_queue = queue.Queue(maxsize=1)
            self.runtime_frames.clear()
            self.runtime_busy = False
            self.runtime_result_queue = queue.Queue(maxsize=1)
            self.last_runtime_event_key = None
            self.runtime_status.set("Runtime Vision：等待稳定3帧")
            self.hint_status.set("向听提示：等待可信手牌/金牌；Executor OFF")
            self._start_evidence()
            self._begin_live_view(f"实时采集开始 · {self.backend_name}")
            self.capture_status.set("正在连接窗口……")
        except Exception as exc:
            self.stop()
            messagebox.showerror("内测未开始", str(exc))

    @staticmethod
    def _tile_label(tile):
        return env.CN[tile]

    def _start_manual_session(self):
        if self.manual_active and self.evidence is not None:
            return True
        self.stop()
        if self.evidence is not None:
            messagebox.showerror("人工模式未开始", "证据会话关闭失败，请先处理保存错误。")
            return False
        try:
            self.demo = False
            self.backend_name = "MANUAL"
            self.target = None
            self.source = {}
            self.manual_tiles = []
            self.manual_revision = 0
            self._start_evidence()
            self._begin_live_view("人工录牌会话开始 · 非视觉识别")
            self.manual_active = True
            self.capture_status.set("人工模式：无画面采集、无自动识别；Executor OFF")
            self.runtime_status.set("Runtime Vision：人工输入未经过视觉识别")
            self.vision_status.set("PublicState：未提供完整公开牌")
            return True
        except Exception as exc:
            messagebox.showerror("人工模式未开始", str(exc))
            return False

    def open_manual_hand(self):
        if not self._start_manual_session():
            return
        dialog = tk.Toplevel(self)
        dialog.title("人工点选手牌 · 仅内部只读")
        dialog.geometry("680x540")
        dialog.transient(self)
        dialog.grab_set()
        ttk.Label(dialog, text="逐张点选自己的暗手牌（含本次摸牌）；\n"
                  "金牌和自家副露组数需单独选择。未知牌不要猜，先不要提交。"
                  ).pack(anchor="w", padx=12, pady=8)
        controls = ttk.Frame(dialog)
        controls.pack(fill="x", padx=12)
        gold = tk.StringVar(value="")
        melds = tk.StringVar(value="0")
        ttk.Label(controls, text="开出的金牌").grid(row=0, column=0)
        ttk.Combobox(controls, state="readonly", textvariable=gold,
                     values=env.BASE_TILES, width=8).grid(row=0, column=1, padx=8)
        ttk.Label(controls, text="自家副露组数").grid(row=0, column=2)
        ttk.Spinbox(controls, from_=0, to=5, textvariable=melds,
                    width=5).grid(row=0, column=3, padx=8)

        hand_view = tk.Listbox(dialog, height=4, exportselection=False)
        hand_view.pack(fill="x", padx=12, pady=6)

        def refresh():
            hand_view.delete(0, tk.END)
            for tile in self.manual_tiles:
                hand_view.insert(tk.END, f"{tile} · {self._tile_label(tile)}")
            self.hint_status.set("向听提示：BLOCKED（人工录牌已改动，请重新提交）")

        gold.trace_add("write", lambda *_: refresh())
        melds.trace_add("write", lambda *_: refresh())

        def add(tile):
            self.manual_tiles.append(tile)
            refresh()

        tile_grid = ttk.Frame(dialog)
        tile_grid.pack(fill="both", expand=True, padx=12)
        for index, tile in enumerate(env.BASE_TILES):
            ttk.Button(tile_grid, text=f"{tile} {self._tile_label(tile)}",
                       command=lambda value=tile: add(value), width=9).grid(
                           row=index // 8, column=index % 8, padx=2, pady=3
                       )

        def remove_selected():
            selected = hand_view.curselection()
            if selected:
                self.manual_tiles.pop(selected[0])
                refresh()

        def submit():
            try:
                snapshot, hint = evaluate_manual_input(
                    session_id=self.evidence.session_id,
                    revision=self.manual_revision + 1,
                    captured=time.monotonic(),
                    hand=tuple(self.manual_tiles), gold_tile=gold.get() or None,
                    own_meld_count=int(melds.get()),
                )
                self.evidence.mark("MANUAL_TABLE_SNAPSHOT", {
                    "input_source": "USER_ENTERED_UNVERIFIED",
                    "snapshot": asdict(snapshot), "hint": asdict(hint),
                    "official_ai_reward_eligible": False,
                    "safe_for_executor": False,
                }, source={"manual_revision": snapshot.stream_epoch})
            except (ValueError, RuntimeError, OSError) as exc:
                messagebox.showerror("人工录牌未提交", str(exc))
                return
            self.manual_revision = snapshot.stream_epoch
            self.runtime_status.set(
                f"人工输入：{len(snapshot.own_hand)}张，金={snapshot.gold_tile or '?'}，"
                f"自家副露{len(snapshot.melds[0])}组；{hint.status}；非视觉识别"
            )
            self.hint_status.set("人工未核验 · " + self._format_shanten_hint(hint))
            self._update_snapshot_view(snapshot, hint, source_label="manual")
            dialog.destroy()

        buttons = ttk.Frame(dialog)
        buttons.pack(fill="x", padx=12, pady=8)
        ttk.Button(buttons, text="移除选中牌（弃牌后更新）",
                   command=remove_selected).pack(side="left", padx=4)
        ttk.Button(buttons, text="提交当前快照", command=submit).pack(side="right")
        refresh()

    def open_manual_score(self):
        if self.evidence is None:
            messagebox.showinfo("尚无证据会话", "请先开始内测或点击人工录牌。")
            return
        dialog = tk.Toplevel(self)
        dialog.title("人工录分 · 规则仍为 UNKNOWN")
        dialog.transient(self)
        dialog.grab_set()
        ttk.Label(dialog, text="仅录入画面上的前后分数；不按未确认规则自动结算。"
                  ).grid(row=0, column=0, columnspan=2, padx=12, pady=8)
        fields = {}
        for index, (key, label) in enumerate((
            ("before_self", "之前我方"), ("before_opponent", "之前对方"),
            ("after_self", "之后我方"), ("after_opponent", "之后对方"),
        ), start=1):
            ttk.Label(dialog, text=label).grid(row=index, column=0, padx=8, pady=4)
            entry = ttk.Entry(dialog, width=18)
            entry.grid(row=index, column=1, padx=8, pady=4)
            fields[key] = entry
        rule = tk.StringVar(value="")
        ttk.Label(dialog, text="未确认规则 ID").grid(row=5, column=0, padx=8)
        ttk.Combobox(dialog, textvariable=rule, width=32, values=(
            "settlement.qiangjin_full", "settlement.sanjindao_full",
            "settlement.eight_flower_real",
        )).grid(row=5, column=1, padx=8, pady=4)

        def submit():
            try:
                row = observed_score_entry(
                    scores_before=(int(fields["before_self"].get()),
                                   int(fields["before_opponent"].get())),
                    scores_after=(int(fields["after_self"].get()),
                                  int(fields["after_opponent"].get())),
                    unresolved_rule_id=rule.get(),
                )
                self.evidence.mark("MANUAL_SCORE_OBSERVATION", row,
                                   source={"input_origin": "user_entered",
                                           **self.source})
            except (ValueError, RuntimeError, OSError) as exc:
                messagebox.showerror("人工分数未保存", str(exc))
                return
            self.evidence_status.set(
                f"人工录分已保存：我方{row['score_delta'][0]:+d}；"
                "仅观察，不作规则结算"
            )
            dialog.destroy()

        ttk.Button(dialog, text="保存观察分数（不落规则账）",
                   command=submit).grid(row=6, column=0, columnspan=2, pady=12)

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

    def _invalidate_advice(self, reason):
        self.live_guard.invalidate()
        self.runtime_frames.clear()
        self.public_frames.clear()
        self.runtime_busy = False
        self.runtime_result_queue = queue.Queue(maxsize=1)
        self.public_busy = False
        self.public_result_queue = queue.Queue(maxsize=1)
        self.public_previous = None
        self.hint_status.set(f"向听提示：BLOCKED（{reason}）；Executor OFF")

    def stop(self):
        self._invalidate_advice("采集已停止")
        self.manual_active = False
        errors = []
        if self.auto_recorder:
            automatic, self.auto_recorder = self.auto_recorder, None
            try:
                path = automatic.close("Hint Alpha停止")
                if path and self.evidence:
                    self.evidence.mark("AUTO_RECORDING_CLOSED", {"path": str(path)})
            except Exception as exc:
                errors.append(f"录像关闭失败：{type(exc).__name__}: {exc}")
        if self.session:
            session, self.session = self.session, None
            try:
                session.close()
            except Exception as exc:
                errors.append(f"采集关闭失败：{type(exc).__name__}: {exc}")
        if self.evidence:
            evidence = self.evidence
            try:
                if errors:
                    evidence.mark("SHUTDOWN_FAILED", {"errors": list(errors)})
                evidence.close("capture_stopped_with_errors" if errors else "capture_stopped")
            except Exception as exc:
                errors.append(f"证据关闭失败：{type(exc).__name__}: {exc}")
            else:
                self.evidence = None
        self.frame = None
        self.canvas.delete("all")
        self.capture_status.set("已停止；保存失败" if errors else "已停止")
        self._refresh_health()
        if errors:
            self.evidence_status.set("；".join(errors))

    def _public_worker(self, images, previous, output_queue):
        try:
            result = self.public_reader.read_window(
                images, previous=previous, minimum_votes=2
            )
            payload = ("ok", result)
        except Exception as exc:
            payload = ("error", f"{type(exc).__name__}: {exc}")
        try:
            output_queue.put_nowait(payload)
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
            args=(images, self.public_previous, self.public_result_queue),
            daemon=True,
        ).start()

    def _runtime_worker(self, samples, session_id, generation, captured, output_queue):
        try:
            # Lazy import keeps non-Vision Hint Alpha utilities importable
            # without forcing OpenCV into every core-only process.
            from workspace.vision.tiles_runtime_v0_2.runtime_reader import (
                read_stable_frames,
            )

            frame_ids = tuple(sequence for sequence, _ in samples)
            images = tuple(image for _, image in samples)
            report = read_stable_frames(
                images,
                PROJECT_ROOT / "dataset" / "tiles_runtime_v0_2",
                frame_ids=frame_ids,
                session=session_id,
                confidence_threshold=0.82,
            )
            report["stream_epoch"] = generation
            payload = ("ok", session_id, generation, captured, report)
        except Exception as exc:
            payload = ("error", session_id, generation, captured, f"{type(exc).__name__}: {exc}")
        try:
            output_queue.put_nowait(payload)
        except queue.Full:
            pass

    def _schedule_runtime_read(self, now):
        if (
            self.demo
            or self.runtime_busy
            or len(self.runtime_frames) < 3
            or now - self.last_runtime_started < 0.8
            or self.evidence is None
        ):
            return
        self.runtime_busy = True
        self.last_runtime_started = now
        samples = tuple(
            (sequence, image.copy())
            for sequence, image in self.runtime_frames
        )
        threading.Thread(
            target=self._runtime_worker,
            args=(samples, self.evidence.session_id, self.live_guard.generation,
                  self.live_guard.last_frame, self.runtime_result_queue),
            daemon=True,
        ).start()

    @staticmethod
    def _format_shanten_hint(result):
        if not result.allowed:
            issues = ",".join(result.issues[:3]) or "snapshot_untrusted"
            return f"向听提示：BLOCKED（{issues}）"

        if result.phase == "PRE_DRAW":
            if result.effective_tiles:
                effective = " ".join(
                    f"{item.tile}×{item.remaining}"
                    for item in result.effective_tiles[:8]
                )
                if len(result.effective_tiles) > 8:
                    effective += " …"
                return (
                    f"向听提示：{result.shanten}向听 | "
                    f"有效牌 {effective} | 公开剩余张数已启用"
                )
            return (
                f"向听提示：{result.shanten}向听 | "
                "仅结构计算；公开牌未完全可信"
            )

        if result.phase == "POST_DRAW_COMPLETE":
            return "向听提示：普通结构已完成；仍需规则层确认是否可胡"

        if result.phase == "POST_DRAW":
            choices = []
            for item in result.best_discards[:8]:
                text = f"{item.discard}(向听{item.shanten}"
                if item.total_live_copies is not None:
                    text += f",活{item.total_live_copies}"
                choices.append(text + ")")
            suffix = " …" if len(result.best_discards) > 8 else ""
            mode = (
                "公开剩余张数已启用"
                if result.visible_remainders_used
                else "仅结构最小向听"
            )
            return f"向听提示：可考虑 {' '.join(choices)}{suffix} | {mode}"

        return "向听提示：状态暂不可解释；不输出建议"

    @staticmethod
    def _format_runtime_advice(advisory, *, experimental, promoted):
        # Missing trusted inputs are an actual Vision abstention, even when
        # Runtime has not passed its formal promotion gate. Surface the cause.
        if not advisory.hint.allowed:
            return HintAlphaApp._format_shanten_hint(advisory.hint)
        if not advisory.display_allowed:
            return (
                "向听提示：BLOCKED（Runtime Vision尚未正式promotion；"
                "仅可用开发开关做内部验证）"
            )
        prefix = "实验 " if experimental and not promoted else ""
        return prefix + HintAlphaApp._format_shanten_hint(advisory.hint)

    def _consume_runtime_result(self):
        try:
            kind, source_session, generation, captured, value = self.runtime_result_queue.get_nowait()
        except queue.Empty:
            return
        self.runtime_busy = False
        current_session = self.evidence.session_id if self.evidence else None
        if source_session != current_session or not self.live_guard.accepts(
            generation, captured, time.monotonic()
        ):
            return
        self.live_guard.last_result = captured
        if kind == "error":
            self.runtime_status.set(f"Runtime Vision暂不可用：{value}")
            self.hint_status.set("向听提示：BLOCKED（Runtime Vision错误）")
            event_key = ("error", value)
            if self.evidence and event_key != self.last_runtime_event_key:
                self.evidence.mark("RUNTIME_VISION_ERROR", {"error": value})
                self.last_runtime_event_key = event_key
            return

        report = value
        advisory = evaluate_runtime_report(
            report, captured=captured,
            experimental=self.experimental_runtime_advisory,
        )
        snapshot, result = advisory.snapshot, advisory.hint
        issues = ",".join(result.issues[:4]) or "none"
        global_coverage = report.get("standard_class_coverage") or {}
        domains = report.get("classification_domain_coverage") or {}
        concealed_coverage = domains.get("concealed_identity") or global_coverage
        concealed_missing = ",".join(
            concealed_coverage.get("missing") or ()
        ) or "none"
        self.runtime_status.set(
            "Runtime Vision："
            f"{result.status} 手牌={len(snapshot.own_hand)} "
            f"金={snapshot.gold_tile or '?'} "
            f"concealed_missing={concealed_missing} "
            f"issues={issues}"
        )
        self._update_snapshot_view(snapshot, result, source_label="runtime")
        runtime_promoted_for_hint = report.get("safe_for_hint") is True
        display_allowed = advisory.display_allowed
        self.hint_status.set(self._format_runtime_advice(
            advisory, experimental=self.experimental_runtime_advisory,
            promoted=runtime_promoted_for_hint,
        ))

        event_key = (
            result.status,
            result.phase,
            result.shanten,
            display_allowed,
            tuple((item.discard, item.shanten) for item in result.best_discards),
            snapshot.gold_tile,
            snapshot.own_hand,
            result.issues,
        )
        if self.evidence and event_key != self.last_runtime_event_key:
            self.evidence.mark(
                "CURRENT_SNAPSHOT_HINT",
                {
                    "status": result.status,
                    "phase": result.phase,
                    "shanten": result.shanten,
                    "hand": list(snapshot.own_hand),
                    "gold_tile": snapshot.gold_tile,
                    "best_discards": [
                        {
                            "tile": item.discard,
                            "shanten": item.shanten,
                            "live": item.total_live_copies,
                        }
                        for item in result.best_discards
                    ],
                    "issues": list(result.issues),
                    "runtime_safe_for_hint": runtime_promoted_for_hint,
                    "experimental_runtime_advisory": self.experimental_runtime_advisory,
                    "display_allowed": display_allowed,
                    "safe_for_executor": False,
                },
                source=self.source,
            )
            self.last_runtime_event_key = event_key

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
        self._update_public_view(observation)
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
            self._invalidate_advice("黑屏")
            self.capture_status.set("疑似黑屏：停止给提示并保留证据")
            if self.evidence:
                self.evidence.mark("BLACK_FRAME", source=self.source)
            return
        if self.last_rect is not None and rect != self.last_rect:
            self._invalidate_advice("窗口几何变化，等待稳定帧")
        generation = self.live_guard.generation
        if not self.live_guard.observe(sequence, captured):
            self._invalidate_advice("无效采集时间")
            return
        if generation != self.live_guard.generation:
            self._invalidate_advice("采集序列重置")
            self.live_guard.observe(sequence, captured)
        self.public_frames.append(self.frame.copy())
        self.runtime_frames.append((sequence, self.frame.copy()))
        self._ensure_auto_recorder()
        if self.auto_recorder:
            path = self.auto_recorder.process(
                self.frame, self.source, captured, wall_time
            )
            if path and self.evidence:
                self.evidence.mark(
                    "HAND_RECORDING_SAVED", {"path": str(path)}, source=self.source
                )
        self._schedule_runtime_read(captured)
        self._schedule_public_read(captured)
        self.capture_status.set(
            f"{self.backend_name} | {size[0]}×{size[1]} | "
            "正在采集；Executor OFF"
        )
        self._refresh_health()
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
            if self.live_guard.stale(time.monotonic()):
                self._invalidate_advice("画面或识别结果已过期")
            self._consume_public_result()
            self._consume_runtime_result()
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
            self._invalidate_advice("采集错误")
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
    parser.add_argument(
        "--experimental-runtime-advisory",
        action="store_true",
        help=(
            "内部开发验证：允许未正式promotion的Runtime Vision驱动只读向听显示；"
            "不会启用Executor"
        ),
    )
    args = parser.parse_args()
    dpi_awareness()
    HintAlphaApp(
        demo=args.demo,
        experimental_runtime_advisory=args.experimental_runtime_advisory,
    ).mainloop()


if __name__ == "__main__":
    main()
