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
