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

from . import app as shell
from .runtime_pipeline import (
    RuntimeAdvicePipeline,
    confirmed_public_hand_boundary,
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
        self.runtime_advice_pipeline = RuntimeAdvicePipeline()

    def _invalidate_advice(self, reason):
        pipeline = getattr(self, "runtime_advice_pipeline", None)
        if pipeline is not None:
            pipeline.reset()
        return super()._invalidate_advice(reason)

    def _update_public_view(self, observation):
        # stream_epoch is a capture generation, not a Mahjong-hand identifier.
        # Gold may legitimately change while capture generation stays constant.
        # Only an initial or sequentially confirmed PublicState hand boundary
        # can clear the previous hand's Gold; regressions/jumps fail closed.
        if confirmed_public_hand_boundary(self.timeline_hand, observation):
            self.runtime_advice_pipeline.reset()
        return super()._update_public_view(observation)

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
