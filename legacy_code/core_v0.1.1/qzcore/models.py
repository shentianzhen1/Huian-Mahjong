
from dataclasses import dataclass, field
from enum import Enum

class MeldKind(str, Enum):
    CHI = "chi"
    PENG = "peng"
    MING_GANG = "ming_gang"
    AN_GANG = "an_gang"

@dataclass(frozen=True)
class Meld:
    kind: MeldKind
    tiles: tuple[str, ...]
    exposed: bool = True

@dataclass
class GameState:
    players: int = 2
    dealer: int = 0
    current_player: int = 0
    my_hand: list[str] = field(default_factory=list)
    opponent_public_tiles: list[str] = field(default_factory=list)
    discards: list[list[str]] = field(default_factory=lambda: [[], []])
    melds: list[list[Meld]] = field(default_factory=lambda: [[], []])
    flowers: list[list[str]] = field(default_factory=lambda: [[], []])
    gold_tile: str | None = None
    wall_remaining: int = 0
    phase: str = "NORMAL"
    scores: list[int] = field(default_factory=lambda: [0, 0])
