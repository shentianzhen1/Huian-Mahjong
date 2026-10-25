"""Capture-generation and freshness gate for internal read-only advice."""
from dataclasses import dataclass
import math


@dataclass
class LiveAdviceGuard:
    generation: int = 0
    last_frame: float | None = None
    last_sequence: int | None = None
    last_result: float | None = None
    active: bool = False
    max_age: float = 2.0

    def invalidate(self):
        self.generation += 1
        self.last_frame = self.last_sequence = self.last_result = None
        self.active = False

    def observe(self, sequence, captured):
        if not math.isfinite(captured):
            self.invalidate()
            return False
        if self.last_sequence is not None and (
            sequence <= self.last_sequence or captured <= self.last_frame
        ):
            self.invalidate()
        self.active = True
        self.last_sequence = sequence
        self.last_frame = captured
        return True

    def accepts(self, generation, captured, now):
        return bool(
            self.active
            and generation == self.generation
            and math.isfinite(captured)
            and math.isfinite(now)
            and 0 <= now - captured <= self.max_age
            and (self.last_result is None or captured > self.last_result)
        )

    def stale(self, now):
        return self.active and (
            self.last_frame is None or now - self.last_frame > self.max_age
            or (self.last_result is not None and now - self.last_result > self.max_age)
        )


def eligible_prior_identity(report, *, captured, previous_captured, now, max_age):
    """Only a fresh earlier identity from this same burst may prime confirmation."""
    prior = report.get('prior_identity_report')
    timestamp = report.get('prior_identity_captured')
    if (not isinstance(prior, dict) or isinstance(timestamp, bool)
            or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp)
            or not timestamp < captured or not 0 <= now - timestamp <= max_age
            or (previous_captured is not None and timestamp <= previous_captured)
            or prior.get('session') != report.get('session')
            or prior.get('stream_epoch') != report.get('stream_epoch')
            or prior.get('geometry_untrusted', True)
            or report.get('geometry_untrusted', True)
            or prior.get('frames') != report.get('frames')):
        return None
    frames = report.get('frames', ())
    if len(frames) < 3 or len(set(frames)) != len(frames):
        return None
    for source, expected in ((prior, frames[-2]), (report, frames[-1])):
        identities = [c for c in source.get('components', ())
                      if c.get('region_candidate') in {'hand', 'draw_visual', 'meld'}]
        if not identities or any(c.get('frame') != expected for c in identities):
            return None
    return prior
