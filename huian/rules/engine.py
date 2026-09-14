from dataclasses import dataclass
from numbers import Integral

from huian._legacy import core
from qzcore.legal_actions import chi_options, can_peng, can_ming_gang, can_an_gang
from qzcore.win_checker import winning_decompositions
from .config import EvidenceStatus, RulesConfig, UnknownRuleError
from .context import HuContext, SanjindaoChoice, SanjindaoDecision, WinSource


def nonnegative_int(value, name):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")


@dataclass(frozen=True)
class Settlement:
    rewards: tuple[int, int]
    current_dealer_base: int
    winner_fan: int
    multiplier: int
    status: EvidenceStatus = EvidenceStatus.HIGH_CONFIDENCE
    evidence: str = "RULE_STATUS.md: settlement examples A/B; third example pending"


@dataclass(frozen=True)
class HuDecomposition:
    """One structural ordinary-Hu split; ``GOLD`` denotes a wildcard position."""

    pair: tuple[str, str]
    groups: tuple[tuple[str, str, str], ...]

    @property
    def gold_used(self):
        return self.pair.count("GOLD") + sum(group.count("GOLD") for group in self.groups)


@dataclass(frozen=True)
class HuResult:
    """Structural Hu analysis only; fan and settlement remain separate concerns."""

    legal: bool
    decompositions: tuple[HuDecomposition, ...]
    gold_tile: str | None
    open_melds: int
    context: HuContext
    may_be_truncated: bool = False

    @property
    def win_source(self):
        return self.context.source

    @property
    def winning_tile(self):
        return self.context.winning_tile

    @property
    def kong_kind(self):
        return self.context.kong_kind

    @property
    def is_gang_hu(self):
        return self.context.is_gang_hu


class HuianRules:
    DRAW_WALL_REMAINING = 16

    def is_wall_draw(self, state):
        return state.phase != "READY" and len(state.wall) == self.DRAW_WALL_REMAINING

    def __init__(self, config=None):
        self.config = config if config is not None else RulesConfig()

    @staticmethod
    def validate_tiles(tiles):
        ok, message = core.validate_tile_multiset(tiles, include_flowers=False)
        if not ok:
            raise ValueError(message)

    def _validate_hand(self, hand, gold_tile):
        self.validate_tiles(hand)
        if gold_tile is not None and gold_tile not in core.BASE_TILES:
            raise ValueError("Gold must be a normal tile")

    def meld_options(self, hand, discard, gold_tile=None):
        """Local composition candidates, NOT a complete phase-aware action set."""
        self._validate_hand(hand, gold_tile)
        self.validate_tiles([*hand, discard])
        return {
            "chi": [seq for seq in chi_options(hand, discard, True, gold_tile)
                    if gold_tile not in seq],
            "peng": can_peng(hand, discard, gold_tile),
            "ming_gang": can_ming_gang(hand, discard, gold_tile),
        }

    def concealed_kongs(self, hand, gold_tile=None):
        self._validate_hand(hand, gold_tile)
        return tuple(t for t in core.BASE_TILES if can_an_gang(hand, t, gold_tile))

    def can_sanjindao(self, hand, gold_tile):
        """Confirmed eligibility only; phase timing and settlement remain separate."""
        self._validate_hand(hand, gold_tile)
        return gold_tile is not None and hand.count(gold_tile) >= 3

    def sanjindao_decision(self, hand, gold_tile):
        """Return the confirmed declare/continue choice without inventing its phase."""
        eligible = self.can_sanjindao(hand, gold_tile)
        count = hand.count(gold_tile) if gold_tile is not None else 0
        choices = ((SanjindaoChoice.DECLARE_SANJINDAO,
                    SanjindaoChoice.CONTINUE_PLAY) if eligible else ())
        return SanjindaoDecision(eligible, count, choices)

    @staticmethod
    def _hu_context(win_type, win_context, winning_tile, kong_kind):
        if win_context is not None:
            if win_type not in (None, "zimo") or winning_tile is not None or kong_kind is not None:
                raise ValueError("Use win_context or legacy win arguments, not both")
            if not isinstance(win_context, HuContext):
                raise TypeError("win_context must be HuContext")
            return win_context
        source_aliases = {
            None: WinSource.SELF_DRAW,
            "zimo": WinSource.SELF_DRAW,
            "self_draw": WinSource.SELF_DRAW,
            "pinghu": WinSource.DISCARD,
            "discard": WinSource.DISCARD,
            "kong_tail_draw": WinSource.KONG_TAIL_DRAW,
        }
        if win_type not in source_aliases:
            raise UnknownRuleError("rob_kong" if win_type == "qianggang" else win_type)
        return HuContext(source_aliases[win_type], winning_tile, kong_kind)

    def analyze_hu(self, hand, gold_tile=None, open_melds=0, win_type="zimo",
                   max_decompositions=64, *, win_context=None, winning_tile=None,
                   kong_kind=None):
        """Return ordinary structural Hu splits without inferring fan or special Hu.

        The legacy solver has a result cap. ``may_be_truncated`` warns callers
        when the cap was reached so scoring code never mistakes this for a full
        enumeration.
        """
        self._validate_hand(hand, gold_tile)
        nonnegative_int(open_melds, "open_melds")
        if open_melds > 5:
            raise ValueError("At most five melds")
        if (isinstance(max_decompositions, bool)
                or not isinstance(max_decompositions, Integral)
                or max_decompositions <= 0):
            raise ValueError("max_decompositions must be a positive integer")
        context = self._hu_context(win_type, win_context, winning_tile, kong_kind)
        if context.winning_tile is not None:
            self.validate_tiles([context.winning_tile])
            if context.winning_tile not in hand:
                raise ValueError("Winning tile must be present in the analyzed hand")
        if context.source == WinSource.DISCARD and context.winning_tile is None:
            raise ValueError("Discard Hu analysis requires winning_tile")
        gold_count = hand.count(gold_tile) if gold_tile else 0
        if context.source == WinSource.DISCARD:
            if context.winning_tile == gold_tile:
                return HuResult(False, (), gold_tile, open_melds, context)
            if gold_count == 1 and not self.config.single_gold_can_pinghu:
                return HuResult(False, (), gold_tile, open_melds, context)
            if gold_count == 2:
                return HuResult(False, (), gold_tile, open_melds, context)
        if gold_count >= 3:
            raise UnknownRuleError("three_plus_gold_ordinary_hu")
        raw_splits = winning_decompositions(
            hand, gold_tile, open_melds, max_solutions=max_decompositions + 1
        )
        may_be_truncated = len(raw_splits) > max_decompositions
        raw_splits = raw_splits[:max_decompositions]
        decompositions = tuple(
            HuDecomposition(
                pair=tuple(split["pair"]),
                groups=tuple(tuple(group) for group in split["groups"]),
            )
            for split in raw_splits
        )
        return HuResult(
            legal=bool(decompositions),
            decompositions=decompositions,
            gold_tile=gold_tile,
            open_melds=open_melds,
            context=context,
            may_be_truncated=may_be_truncated,
        )

    def can_win(self, hand, gold_tile=None, open_melds=0, win_type="zimo", **context):
        """Compatibility boolean wrapper around :meth:`analyze_hu`."""
        return self.analyze_hu(hand, gold_tile, open_melds, win_type, **context).legal

    def ting_tiles(self, hand, gold_tile=None, open_melds=0, win_type="zimo",
                   visible_tiles=(), *, win_context=None):
        """Ordinary structural waits; remaining counts exclude supplied public tiles."""
        self._validate_hand(hand, gold_tile)
        self.validate_tiles([*hand, *visible_tiles])
        if win_context is not None and not isinstance(win_context, HuContext):
            raise TypeError("win_context must be HuContext")
        if win_context is not None and win_context.winning_tile is not None:
            raise ValueError("Ting context must not preselect a winning tile")
        waits = []
        for tile in core.BASE_TILES:
            remaining = 4 - hand.count(tile) - visible_tiles.count(tile)
            context = win_context.with_winning_tile(tile) if win_context is not None else None
            kwargs = {"win_context": context} if context is not None else {}
            if win_type in ("pinghu", "discard"):
                kwargs["winning_tile"] = tile
            if remaining and self.can_win([*hand, tile], gold_tile, open_melds,
                                          win_type, **kwargs):
                waits.append({"tile": tile, "remaining": remaining})
        return waits

    def settle(self, *, winner, current_dealer_base, winner_fan, multiplier=None):
        if self.config.settlement_model is None:
            raise UnknownRuleError("settlement_formula")
        if multiplier is None:
            raise UnknownRuleError("room_multipliers")
        for name, value in (("winner", winner), ("current_dealer_base", current_dealer_base),
                            ("winner_fan", winner_fan), ("multiplier", multiplier)):
            nonnegative_int(value, name)
        if winner not in (0, 1) or multiplier == 0:
            raise ValueError("Two seats and a positive multiplier are required")
        net = (current_dealer_base + winner_fan) * multiplier
        rewards = (net, -net) if winner == 0 else (-net, net)
        return Settlement(rewards, current_dealer_base, winner_fan, multiplier)

    def calculate_fan(self, *args, **kwargs):
        """No automatic fan aggregation until values and decomposition policy are explicit."""
        raise UnknownRuleError("fan_edge_cases", "flower_groups", "decomposition_scoring")
