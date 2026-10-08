"""Confirm current hand/meld observations across distinct live identity frames.

This is an advisory deployment guard, not a classifier or promotion gate. It
never carries a previous hand into a missing/changed current observation.
"""
from dataclasses import dataclass, field, replace
import math

from workspace.vision.current_state_snapshot import assess_current_snapshot, SnapshotCapability


@dataclass
class LiveSnapshotStability:
    minimum_observations: int = 2
    max_gap_seconds: float = 2.0
    _scope: tuple | None = field(default=None, init=False)
    _signature: tuple | None = field(default=None, init=False)
    _last_frame: str | int | None = field(default=None, init=False)
    _last_time: float | None = field(default=None, init=False)
    _votes: int = field(default=0, init=False)

    def __post_init__(self):
        if (isinstance(self.minimum_observations, bool)
                or not isinstance(self.minimum_observations, int)
                or self.minimum_observations < 2):
            raise ValueError("minimum_observations must be an integer >= 2")
        if (isinstance(self.max_gap_seconds, bool)
                or not isinstance(self.max_gap_seconds, (int, float))
                or not math.isfinite(self.max_gap_seconds)
                or self.max_gap_seconds <= 0):
            raise ValueError("max_gap_seconds must be finite and positive")

    def reset(self):
        self._scope = self._signature = self._last_frame = self._last_time = None
        self._votes = 0

    @staticmethod
    def _blocked(snapshot, issue):
        return replace(snapshot, hand_trusted=False,
                       meld_trusted=(False, snapshot.meld_trusted[1]),
                       adapter_issues=(*snapshot.adapter_issues, issue))

    def update(self, snapshot, report):
        # Do not accumulate votes from incomplete, conflicted or physically
        # impossible snapshots. Gold persistence has already run in the pipeline.
        if not assess_current_snapshot(snapshot).allows(SnapshotCapability.SHANTEN):
            self.reset()
            return snapshot
        now = snapshot.timestamp_seconds
        if not math.isfinite(now):
            self.reset()
            return self._blocked(snapshot, "live_identity_time_invalid")

        components = [item for item in report.get("components", ())
                      if isinstance(item, dict)
                      and item.get("region_candidate") in {"hand", "draw_visual", "meld"}]
        frames = [item.get("frame") for item in components]
        # Region-count stability or repeated overlapping burst IDs are not
        # independent identity reads. Bind votes to the actual classified frame.
        if (not frames or any(isinstance(frame, bool) or not isinstance(frame, (str, int))
                              for frame in frames)
                or len(set(frames)) != 1
                or frames[0] not in (report.get("frames") or ())):
            self.reset()
            return self._blocked(snapshot, "live_identity_frame_scope_invalid")
        frame = frames[0]
        scope = (snapshot.source_session, snapshot.stream_epoch)
        signature = (tuple(sorted(snapshot.own_hand)), snapshot.gold_tile,
                     tuple(sorted(tuple(sorted(tile or "UNKNOWN" for tile in group))
                                  for group in snapshot.melds[0])))
        if scope != self._scope:
            self.reset()
            self._scope = scope
        if self._last_time is not None and now <= self._last_time:
            self.reset()
            return self._blocked(snapshot, "live_identity_time_not_increasing")
        if frame == self._last_frame:
            return self._blocked(snapshot, "live_identity_frame_repeated")
        if (signature != self._signature or self._last_time is None
                or now - self._last_time > self.max_gap_seconds):
            self._votes = 1
        else:
            self._votes = min(self.minimum_observations, self._votes + 1)
        self._signature, self._last_frame, self._last_time = signature, frame, now
        if self._votes < self.minimum_observations:
            return self._blocked(snapshot, "live_hand_meld_waiting_confirmation")
        return snapshot
