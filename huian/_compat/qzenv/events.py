
from dataclasses import dataclass
from .actions import Action

@dataclass
class Event:
    seq: int
    action: Action
    before_hash: str
    after_hash: str
    wall_remaining: int
    current_player_after: int
    phase_after: str

    def to_dict(self):
        return {
            "seq": self.seq,
            "action": self.action.to_dict(),
            "before_hash": self.before_hash,
            "after_hash": self.after_hash,
            "wall_remaining": self.wall_remaining,
            "current_player_after": self.current_player_after,
            "phase_after": self.phase_after,
        }
