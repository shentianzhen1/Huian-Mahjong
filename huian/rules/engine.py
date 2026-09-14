from dataclasses import dataclass
from numbers import Integral

from huian._legacy import core
from qzcore.legal_actions import chi_options, can_peng, can_ming_gang, can_an_gang
from qzcore.win_checker import winning_decompositions
from .config import EvidenceStatus, RulesConfig, UnknownRuleError


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
    win_source: str
    may_be_truncated: bool = False


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

    def analyze_hu(self, hand, gold_tile=None, open_melds=0, win_type="zimo",
                   max_decompositions=64):
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
        if win_type not in ("zimo", "pinghu"):
            raise UnknownRuleError("rob_kong" if win_type == "qianggang" else win_type)
        gold_count = hand.count(gold_tile) if gold_tile else 0
        if win_type == "pinghu":
            if gold_count == 1 and not self.config.single_gold_can_pinghu:
                return HuResult(False, (), gold_tile, open_melds, win_type)
            if gold_count == 2:
                return HuResult(False, (), gold_tile, open_melds, win_type)
            if gold_count >= 3:
                raise UnknownRuleError("three_plus_gold_pinghu")
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
            win_source=win_type,
            may_be_truncated=may_be_truncated,
        )

    def can_win(self, hand, gold_tile=None, open_melds=0, win_type="zimo"):
        """Compatibility boolean wrapper around :meth:`analyze_hu`."""
        return self.analyze_hu(hand, gold_tile, open_melds, win_type).legal

    def ting_tiles(self, hand, gold_tile=None, open_melds=0, win_type="zimo", visible_tiles=()):
        """Ordinary structural waits; remaining counts exclude supplied public tiles."""
        self._validate_hand(hand, gold_tile)
        self.validate_tiles([*hand, *visible_tiles])
        waits = []
        for tile in core.BASE_TILES:
            remaining = 4 - hand.count(tile) - visible_tiles.count(tile)
            if remaining and self.can_win([*hand, tile], gold_tile, open_melds, win_type):
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
