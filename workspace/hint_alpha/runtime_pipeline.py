"""Shared read-only Runtime -> snapshot -> structural advisory boundary."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from numbers import Integral

from workspace.vision.live_opening_fact import (
    LiveOpeningFact,
    LiveOpeningTracker,
    live_opening_fact_from_snapshot,
)
from workspace.vision.runtime_public_adapter import current_snapshot_from_runtime
from .current_snapshot_advisor import analyze_snapshot_shanten
from .live_snapshot_stability import LiveSnapshotStability
from huian._legacy import env
from workspace.vision.live_opening_fact import LiveOpeningFactStatus


_ACTIVE_OPENING_TRACKER: ContextVar[LiveOpeningTracker | None] = ContextVar(
    "hint_alpha_active_opening_tracker",
    default=None,
)
_ACTIVE_STABILITY_TRACKER: ContextVar[LiveSnapshotStability | None] = ContextVar(
    "hint_alpha_active_stability_tracker", default=None,
)
_ACTIVE_MANUAL_GOLD = ContextVar('hint_alpha_manual_gold', default=None)
_ACTIVE_HAND_SOURCE_TRIAL = ContextVar('hint_alpha_hand_source_trial', default=False)


@dataclass(frozen=True)
class ManualGoldSelection:
    tile_id: str
    source_session: str
    stream_epoch: int

    def applies_to(self, snapshot):
        return (snapshot.source_session, snapshot.stream_epoch) == (self.source_session, self.stream_epoch)

    def apply(self, snapshot):
        # The human supplies only Gold. Current hand/meld/public trust is intact.
        snapshot = replace(snapshot, gold_tile=self.tile_id, gold_trusted=True,
            adapter_issues=tuple(i for i in snapshot.adapter_issues
                                if not str(i).startswith(('runtime_gold_', 'live_gold_'))))
        fact = LiveOpeningFact(timestamp_seconds=snapshot.timestamp_seconds,
            source_session=snapshot.source_session, stream_epoch=snapshot.stream_epoch,
            status=LiveOpeningFactStatus.TRUSTED, gold_tile=self.tile_id,
            gold_trusted=True, source_kind='MANUAL_USER_SELECTED', state_tracker_ready=True)
        return snapshot, fact


def interrupt_runtime_observations():
    """Break live identity confirmation after an accepted worker error.

    The persisted opening fact belongs to the hand, not to one successful
    classification burst. Keep Gold memory and conflicts until a trusted reset.
    Stateless callers have no confirmation streak to interrupt.
    """
    tracker = _ACTIVE_STABILITY_TRACKER.get()
    if tracker is not None:
        tracker.reset()


def confirmed_public_hand_boundary(previous_hand, observation, *, minimum_votes=2):
    """Return True only for an initial or sequentially confirmed public hand.

    Runtime ``stream_epoch`` is a capture generation and can span multiple
    Mahjong hands, so it cannot reset Gold by itself. PublicState hand number is
    the observable boundary, but a regression or jump must not clear a conflict.
    With an existing hand, only N -> N+1 is accepted. With no prior hand, an
    in-range consensus establishes the initial hand boundary.
    """
    if isinstance(minimum_votes, bool) or not isinstance(minimum_votes, Integral):
        raise ValueError("minimum_votes must be an integer")
    if minimum_votes < 1:
        raise ValueError("minimum_votes must be >= 1")

    hand_number = getattr(observation, "hand_number", None)
    hand_votes = getattr(observation, "hand_votes", 0)
    if (
        isinstance(hand_number, bool)
        or not isinstance(hand_number, Integral)
        or not 1 <= hand_number <= 8
    ):
        return False
    if (
        isinstance(hand_votes, bool)
        or not isinstance(hand_votes, Integral)
        or hand_votes < minimum_votes
    ):
        return False

    if previous_hand is None:
        return True
    if isinstance(previous_hand, bool) or not isinstance(previous_hand, Integral):
        return False
    return hand_number == previous_hand + 1


@dataclass(frozen=True)
class RuntimeAdvice:
    snapshot: object
    hint: object
    display_allowed: bool
    opening_fact: LiveOpeningFact
    safe_for_executor: bool = False
    hand_source_trial: bool = False


def evaluate_runtime_report(
    report,
    *,
    captured,
    experimental=False,
    opening_tracker: LiveOpeningTracker | None = None,
    stability_tracker: LiveSnapshotStability | None = None,
    manual_gold: ManualGoldSelection | None = None,
    allow_unvalidated_hand_sources=None,
):
    """Evaluate one Runtime burst without enabling any action path.

    ``opening_tracker`` is explicit for tests and non-UI callers. A live UI may
    instead bind one tracker to the current synchronous evaluation context via
    :meth:`RuntimeAdvicePipeline.bind`. With neither form present the function
    stays stateless, preserving isolated diagnostics and replay behavior.
    """
    tracker = opening_tracker
    if tracker is None:
        tracker = _ACTIVE_OPENING_TRACKER.get()

    trial = (_ACTIVE_HAND_SOURCE_TRIAL.get() if allow_unvalidated_hand_sources is None
             else allow_unvalidated_hand_sources)
    trial_tiles = ()
    adapter_report = report
    if trial and experimental:
        from .hand_source_trial import trial_hand_report
        adapter_report, trial_tiles = trial_hand_report(report)
    snapshot = current_snapshot_from_runtime(adapter_report, timestamp_seconds=captured)
    if trial_tiles:
        snapshot = replace(snapshot, river_trusted=(False, False),
            adapter_issues=(*snapshot.adapter_issues, 'experimental_hand_sources_unvalidated'))
    manual_gold = manual_gold or _ACTIVE_MANUAL_GOLD.get()
    if manual_gold is not None and manual_gold.applies_to(snapshot):
        snapshot, opening_fact = manual_gold.apply(snapshot)
    elif tracker is None:
        opening_fact = live_opening_fact_from_snapshot(snapshot)
    else:
        snapshot, opening_fact = tracker.update(snapshot)
    stability_tracker = stability_tracker or _ACTIVE_STABILITY_TRACKER.get()
    if stability_tracker is not None:
        snapshot = stability_tracker.update(snapshot, report)
    hint = analyze_snapshot_shanten(snapshot)
    return RuntimeAdvice(
        snapshot=snapshot,
        hint=hint,
        display_allowed=bool(
            hint.allowed and (report.get("safe_for_hint") is True or experimental)
        ),
        opening_fact=opening_fact,
        safe_for_executor=False,
        hand_source_trial=bool(trial_tiles),
    )


@dataclass
class RuntimeAdvicePipeline:
    """Long-lived advisory session with explicitly resettable Gold memory."""

    opening_tracker: LiveOpeningTracker = field(default_factory=LiveOpeningTracker)
    stability_tracker: LiveSnapshotStability | None = None
    manual_gold: ManualGoldSelection | None = None
    allow_unvalidated_hand_sources: bool = False

    def select_manual_gold(self, tile_id, *, source_session, stream_epoch):
        if tile_id not in env.BASE_TILES:
            raise ValueError('请选择34种普通牌中的金牌')
        if (not isinstance(source_session, str) or not source_session
                or isinstance(stream_epoch, bool) or not isinstance(stream_epoch, int) or stream_epoch < 0):
            raise ValueError('手动金牌需要当前采集会话')
        self.reset()
        self.manual_gold = ManualGoldSelection(tile_id, source_session, stream_epoch)

    def reset(self, *, preserve_manual_gold=False) -> None:
        """Forget all persisted opening facts at a trusted boundary."""
        self.opening_tracker.reset()
        if not preserve_manual_gold:
            self.manual_gold = None
        if self.stability_tracker is not None:
            self.stability_tracker.reset()

    @contextmanager
    def bind(self):
        """Bind this pipeline only for the current synchronous UI evaluation."""
        token = _ACTIVE_OPENING_TRACKER.set(self.opening_tracker)
        stability_token = _ACTIVE_STABILITY_TRACKER.set(self.stability_tracker)
        manual_token = _ACTIVE_MANUAL_GOLD.set(self.manual_gold)
        trial_token = _ACTIVE_HAND_SOURCE_TRIAL.set(self.allow_unvalidated_hand_sources)
        try:
            yield self
        finally:
            _ACTIVE_HAND_SOURCE_TRIAL.reset(trial_token)
            _ACTIVE_MANUAL_GOLD.reset(manual_token)
            _ACTIVE_STABILITY_TRACKER.reset(stability_token)
            _ACTIVE_OPENING_TRACKER.reset(token)

    def evaluate(self, report, *, captured, experimental=False) -> RuntimeAdvice:
        return evaluate_runtime_report(
            report,
            captured=captured,
            experimental=experimental,
            opening_tracker=self.opening_tracker,
            stability_tracker=self.stability_tracker,
            manual_gold=self.manual_gold,
            allow_unvalidated_hand_sources=self.allow_unvalidated_hand_sources,
        )
