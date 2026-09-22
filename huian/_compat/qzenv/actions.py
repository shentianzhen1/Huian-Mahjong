
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class ActionType(str, Enum):
    DRAW = "DRAW"
    DISCARD = "DISCARD"
    CHI = "CHI"
    PENG = "PENG"
    MING_GANG = "MING_GANG"
    AN_GANG = "AN_GANG"
    ADD_KONG = "ADD_KONG"
    ROB_KONG_HU = "ROB_KONG_HU"
    PASS = "PASS"
    PASS_QIANGJIN = "PASS_QIANGJIN"
    QIANGJIN = "QIANGJIN"
    HU = "HU"
    FLOWER_REPLACE = "FLOWER_REPLACE"
    OPEN_GOLD = "OPEN_GOLD"
    YOUJIN = "YOUJIN"
    DOUBLE_YOU = "DOUBLE_YOU"
    TRIPLE_YOU = "TRIPLE_YOU"
    END_HAND = "END_HAND"

@dataclass(frozen=True)
class Action:
    player: int
    type: ActionType
    tile: str | None = None
    tiles: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "player": self.player,
            "type": self.type.value,
            "tile": self.tile,
            "tiles": list(self.tiles),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            player=int(d["player"]),
            type=ActionType(d["type"]),
            tile=d.get("tile"),
            tiles=tuple(d.get("tiles", [])),
            metadata=dict(d.get("metadata", {})),
        )
