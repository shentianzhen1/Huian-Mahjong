
from dataclasses import dataclass, field, asdict
import hashlib, json

@dataclass
class Meld:
    kind: str
    tiles: list[str]
    from_player: int | None = None

@dataclass
class GameState:
    players: int = 2
    dealer: int = 0
    current_player: int = 0

    hands: list[list[str]] = field(default_factory=lambda: [[], []])
    discards: list[list[str]] = field(default_factory=lambda: [[], []])
    melds: list[list[Meld]] = field(default_factory=lambda: [[], []])
    flowers: list[list[str]] = field(default_factory=lambda: [[], []])

    wall: list[str] = field(default_factory=list)
    gold_tile: str | None = None
    phase: str = "INIT"

    terminal: bool = False
    rewards: list[int] = field(default_factory=lambda: [0, 0])
    turn_index: int = 0
    last_action: dict | None = None

    def wall_remaining(self) -> int:
        return len(self.wall)

    def canonical_dict(self):
        def melds_to_obj(ms):
            return [
                [{"kind": m.kind, "tiles": list(m.tiles), "from_player": m.from_player} for m in p]
                for p in ms
            ]
        return {
            "players": self.players,
            "dealer": self.dealer,
            "current_player": self.current_player,
            "hands": [list(x) for x in self.hands],
            "discards": [list(x) for x in self.discards],
            "melds": melds_to_obj(self.melds),
            "flowers": [list(x) for x in self.flowers],
            "wall": list(self.wall),
            "gold_tile": self.gold_tile,
            "phase": self.phase,
            "terminal": self.terminal,
            "rewards": list(self.rewards),
            "turn_index": self.turn_index,
            "last_action": self.last_action,
        }

    def state_hash(self):
        raw = json.dumps(self.canonical_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
