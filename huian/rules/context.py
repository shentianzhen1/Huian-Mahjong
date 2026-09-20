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
    ROB_KONG = "rob_kong"


class KongKind(str, Enum):
    MING_GANG = "MING_GANG"
    AN_GANG = "AN_GANG"
    ADDED_GANG = "ADDED_GANG"


class YoujinStage(str, Enum):
    NORMAL = "NORMAL"
    YOUJIN = "YOUJIN"
    DOUBLE_YOU = "DOUBLE_YOU"
    TRIPLE_YOU = "TRIPLE_YOU"
    # Player terminology: 三金游 and 三游 are the same state.
    SANJIN_YOU = "TRIPLE_YOU"


@dataclass(frozen=True)
class YoujinOfferRule:
    """Confirmed semantics of a visible Youjin offer.

    The offer is optional: declining it keeps ordinary play alive and does not
    permanently disable later Youjin-family progression in the same hand.
    """

    optional: bool = True
    decline_keeps_playing: bool = True
    decline_blocks_later_youjin: bool = False


def youjin_offer_rule():
    return YoujinOfferRule()


@dataclass(frozen=True)
class YoujinOpponentResponseRule:
    """Confirmed opponent interception window for an established Youjin stage.

    This object deliberately says nothing about how the stage was entered or
    whether/when the Youjin player may choose to upgrade afterward. Those
    transition predicates remain evidence-gated.
    """

    stage: YoujinStage
    opponent_draw_chances: int = 1
    allowed_win_sources: tuple[WinSource, ...] = (WinSource.SELF_DRAW,)
    self_hu_optional: bool = True
    must_discard_after_miss: bool = True
    no_win_outcome: str = "YOUJIN_RESPONSE_DISCARD"


def youjin_opponent_response_rule(stage):
    """Return the confirmed one-draw self-Hu interception rule for a Youjin stage."""
    parsed = stage if isinstance(stage, YoujinStage) else YoujinStage(stage)
    if parsed == YoujinStage.NORMAL:
        raise ValueError("NORMAL has no Youjin opponent response window")
    return YoujinOpponentResponseRule(stage=parsed)


@dataclass(frozen=True)
class YoujinProgressionRule:
    """Confirmed post-interception progression for an established Youjin stage.

    For single/double You, an opponent miss first requires the opponent to
    discard one tile. Only after that response discard does the Youjin player
    receive one normal wall-head draw. If that draw creates
    a gold that can be independently discarded while preserving the roaming-gold
    ready structure, upgrade is optional; declining it settles the current stage.

    Triple-You has no further upgrade draw: after the opponent misses and
    completes the mandatory response discard, Triple-You settles.
    """

    stage: YoujinStage
    youjin_player_draw_chances: int
    next_stage: YoujinStage | None
    upgrade_optional: bool
    opponent_miss_outcome: str
    no_upgrade_outcome: str = "SETTLE_CURRENT_STAGE"


def youjin_progression_rule(stage):
    """Return the confirmed single->double->triple progression contract."""
    parsed = stage if isinstance(stage, YoujinStage) else YoujinStage(stage)
    if parsed == YoujinStage.NORMAL:
        raise ValueError("NORMAL has no Youjin progression rule")
    if parsed == YoujinStage.YOUJIN:
        return YoujinProgressionRule(
            stage=parsed,
            youjin_player_draw_chances=1,
            next_stage=YoujinStage.DOUBLE_YOU,
            upgrade_optional=True,
            opponent_miss_outcome="YOUJIN_PLAYER_DRAW",
        )
    if parsed == YoujinStage.DOUBLE_YOU:
        return YoujinProgressionRule(
            stage=parsed,
            youjin_player_draw_chances=1,
            next_stage=YoujinStage.TRIPLE_YOU,
            upgrade_optional=True,
            opponent_miss_outcome="YOUJIN_PLAYER_DRAW",
        )
    return YoujinProgressionRule(
        stage=YoujinStage.TRIPLE_YOU,
        youjin_player_draw_chances=0,
        next_stage=None,
        upgrade_optional=False,
        opponent_miss_outcome="SETTLE_CURRENT_STAGE",
    )


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
    multiplier: int = 3
