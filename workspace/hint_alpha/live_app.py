"""Supported live Hint Alpha entry point with capture-scoped Gold memory.

The large UI shell remains deliberately unaware of hidden opening mechanics.
This thin wiring layer binds its existing Runtime Vision evaluation to one
``RuntimeAdvicePipeline`` and resets that pipeline only at trusted boundaries:

* capture invalidation / restart; or
* a PublicState observation that confirms the initial hand or N -> N+1.

A different visible Gold by itself never infers a new hand. Executor remains
OFF; this module only affects read-only advice/state presentation.
"""
from __future__ import annotations

import argparse
import time

from . import app as shell
from .live_snapshot_stability import LiveSnapshotStability
from .runtime_pipeline import (
    RuntimeAdvicePipeline,
    confirmed_public_hand_boundary,
    public_hand_boundary_pending,
)


class LiveHintAlphaApp(shell.HintAlphaApp):
    """Hint Alpha UI with explicit per-live-session opening fact state."""

    def __init__(self, demo=False, experimental_runtime_advisory=False):
        super().__init__(
            demo=demo,
            experimental_runtime_advisory=experimental_runtime_advisory,
        )
        # The base constructor does not consume live Runtime results until the
        # Tk event loop starts. Install state after Tk itself is initialized so
        # no pre-Tk attribute behavior is changed.
        self.runtime_advice_pipeline = RuntimeAdvicePipeline(
            stability_tracker=LiveSnapshotStability(),
        )
        self._gold_hand_number = None

    def _invalidate_advice(self, reason):
        pipeline = getattr(self, "runtime_advice_pipeline", None)
        if pipeline is not None:
            pipeline.reset()
            pipeline.hand_boundary_pending = False
        self._refresh_manual_gold()
        self._gold_hand_number = None
        return super()._invalidate_advice(reason)

    def _update_public_view(self, observation):
        result = super()._update_public_view(observation)
        self._update_gold_hand_boundary(observation)
        return result

    def _public_state_failed(self):
        self._update_gold_hand_boundary(None)

    def _update_gold_hand_boundary(self, observation):
        # stream_epoch is a capture generation, not a Mahjong-hand identifier.
        # Gold may legitimately change while capture generation stays constant.
        # Only an initial or sequentially confirmed PublicState hand boundary
        # can clear the previous hand's Gold; regressions/jumps fail closed.
        # Presentation may display a rejected OCR jump/regression. Keep the
        # trusted Gold boundary independent so that display cannot authorize
        # a later reset (e.g. 3 -> 2 -> 3 or 3 -> 5 -> 6).
        pipeline = self.runtime_advice_pipeline
        was_pending = pipeline.hand_boundary_pending
        boundary = confirmed_public_hand_boundary(self._gold_hand_number, observation)
        if boundary:
            # Initial OCR establishes this same hand; keep its user selection.
            if self._gold_hand_number is None:
                self.runtime_advice_pipeline.reset(preserve_manual_gold=True)
            else:
                self.runtime_advice_pipeline.reset()
            self._gold_hand_number = observation.hand_number
            self._refresh_manual_gold()
        pipeline.hand_boundary_pending = public_hand_boundary_pending(self._gold_hand_number, observation)
        if boundary or was_pending != pipeline.hand_boundary_pending:
            # Queued reads and partial bursts from before confirmation cannot
            # seed the next hand, even if their capture epoch is unchanged.
            self.runtime_observation_not_before = time.monotonic()
            frames = self.__dict__.get('runtime_frames')
            if frames is not None:
                frames.clear()
            if pipeline.stability_tracker is not None:
                pipeline.stability_tracker.reset()
        if boundary or pipeline.hand_boundary_pending:
            reason = ('局号尚未确认，等待当前局重新确认。' if pipeline.hand_boundary_pending
                      else '局号已确认，等待新的手牌画面。')
            self.ui_hand_ok = False
            self.ui_gold_ok = False
            self.ui_gold_tile = None
            if pipeline.hand_boundary_pending:
                self.ui_hand_number_ok = False
            for name, text in (
                ('blocked_detail', reason),
                ('hint_latency', '本次提示耗时：暂无'),
                ('turn_status', f'当前状态：UNKNOWN（{reason}）'),
                ('table_hand_status', '我的手牌：UNKNOWN'),
                ('table_meld_status', '我的副露：UNKNOWN'),
                ('hint_status', f'向听提示：BLOCKED（{reason}）'),
            ):
                variable = self.__dict__.get(name)
                if variable is not None:
                    variable.set(text)
            if 'match_header_status' in self.__dict__:
                self._refresh_header()
            if 'health_status' in self.__dict__:
                self._refresh_health()

    def _expire_runtime_advice(self):
        # Reset only identity confirmation; Gold and pending-hand state remain
        # owned by the still-active capture/hand, not by one worker's latency.
        with self.runtime_advice_pipeline.bind():
            return super()._expire_runtime_advice()

    def _consume_runtime_result(self):
        # Base UI already owns queue freshness, evidence, rendering and the
        # fail-closed Hint gate. Bind only the tracker for this synchronous call
        # instead of duplicating that large method or storing global state.
        with self.runtime_advice_pipeline.bind():
            return super()._consume_runtime_result()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--demo",
        action="store_true",
        help="只运行合成画面，验证内测壳与证据记录",
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
    shell.dpi_awareness()
    LiveHintAlphaApp(
        demo=args.demo,
        experimental_runtime_advisory=args.experimental_runtime_advisory,
    ).mainloop()


if __name__ == "__main__":
    main()
