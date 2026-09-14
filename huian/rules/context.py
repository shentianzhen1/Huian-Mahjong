"""Confirmed Huian draw/win provenance without settlement assumptions."""
from dataclasses import dataclass
from enum import Enum


class DrawSource(str, Enum):
    WALL_HEAD = "wall_head"
    WALL_TAIL = "wall_tail"

    @classmethod
    def parse(cls, value):
        """Accept old recorder/replay names while emitting canonical values."""
        aliases = {"head": cls.WALL_HEAD, "tail": cls.WALL_TAIL}
        if isinstance(value, cls):
            return value
        if isinstance(value, str) and value in aliases:
            return aliases[value]
        try:
            return cls(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Draw source must be wall_head or wall_tail") from exc


class WinSource(str, Enum):
    SELF_DRAW = "self_draw"
    DISCARD = "discard"
    KONG_TAIL_DRAW = "kong_tail_draw"


class KongKind(str, Enum):
    MING_GANG = "MING_GANG"
    AN_GANG = "AN_GANG"
    ADDED_GANG = "ADDED_GANG"


class SanjindaoChoice(str, Enum):
    DECLARE_SANJINDAO = "DECLARE_SANJINDAO"
    CONTINUE_PLAY = "CONTINUE_PLAY"


@dataclass(frozen=True)
class HuContext:
    """Facts required by Hu eligibility; fan and settlement are deliberately absent."""

    source: WinSource
    winning_tile: str | None = None
    kong_kind: KongKind | None = None

    def __post_init__(self):
        source = self.source if isinstance(self.source, WinSource) else WinSource(self.source)
        kind = self.kong_kind
        if kind is not None and not isinstance(kind, KongKind):
            kind = KongKind(kind)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "kong_kind", kind)
        if source == WinSource.KONG_TAIL_DRAW and kind is None:
            raise ValueError("Kong-tail Hu requires a kong kind")
        if source != WinSource.KONG_TAIL_DRAW and kind is not None:
            raise ValueError("Kong kind is valid only for a kong-tail Hu")

    @property
    def is_self_draw(self):
        return self.source in (WinSource.SELF_DRAW, WinSource.KONG_TAIL_DRAW)

    @property
    def is_gang_hu(self):
        return self.source == WinSource.KONG_TAIL_DRAW

    def with_winning_tile(self, tile):
        return HuContext(self.source, winning_tile=tile, kong_kind=self.kong_kind)

    @classmethod
    def from_draw_metadata(cls, metadata):
        source = DrawSource.parse(metadata.get("source"))
        tile = metadata.get("effective_drawn_tile", metadata.get("drawn_tile"))
        if tile is None:
            raise ValueError("Completed draw metadata must record drawn_tile")
        if source == DrawSource.WALL_HEAD:
            if metadata.get("kong_kind") is not None:
                raise ValueError("Wall-head draw cannot carry a kong kind")
            return cls(WinSource.SELF_DRAW, winning_tile=tile)
        kind = metadata.get("kong_kind")
        if kind is None:
            raise ValueError("Wall-tail draw must record kong_kind for Gang-Hu classification")
        return cls(WinSource.KONG_TAIL_DRAW, winning_tile=tile, kong_kind=kind)


@dataclass(frozen=True)
class SanjindaoDecision:
    eligible: bool
    gold_count: int
    choices: tuple[SanjindaoChoice, ...]
