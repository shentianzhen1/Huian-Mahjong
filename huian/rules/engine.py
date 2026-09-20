from dataclasses import dataclass
from numbers import Integral

from huian._legacy import core
from qzcore.legal_actions import chi_options, can_peng, can_ming_gang, can_an_gang
from qzcore.win_checker import winning_decompositions
from .config import EvidenceStatus, RulesConfig, UnknownRuleError
from .context import (HuContext, KongKind, SanjindaoChoice, SanjindaoDecision,
                      WinSource, YoujinStage)
from .special_outcomes import special_outcome_profile
from .dealer_base import (
    DEALER_WIN_MULTIPLIER,
    MATCH_HAND_COUNT,
    SITTING_DEALER_BASE,
    dealer_base_for_consecutive_hands,
    match_hand_in_range,
    next_consecutive_dealer_hands,
)


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


@dataclass(frozen=True)
class KongFanResult:
    """Adopted kong fan value with its evidence grade."""

    kind: KongKind
    tile: str
    fan: int
    status: EvidenceStatus
    evidence: str


@dataclass(frozen=True)
class YoujinScoreTerms:
    """Confirmed target-room factors without inferring base or payer."""

    stage: YoujinStage
    youjin_multiplier: int
    dealer_multiplier: int
    winner_fan: int

    def total_for_current_dealer_base(self, current_dealer_base):
        nonnegative_int(current_dealer_base, "current_dealer_base")
        return ((current_dealer_base + self.winner_fan)
                * self.youjin_multiplier * self.dealer_multiplier)


class HuianRules:
    DRAW_WALL_REMAINING = 16
    SANJINDAO_MULTIPLIER = special_outcome_profile("SANJINDAO").multiplier
    SITTING_DEALER_BASE = SITTING_DEALER_BASE
    MATCH_HAND_COUNT = MATCH_HAND_COUNT
    YOUJIN_MULTIPLIERS = {
        YoujinStage.YOUJIN: special_outcome_profile("YOUJIN").multiplier,
        YoujinStage.DOUBLE_YOU: special_outcome_profile("DOUBLE_YOU").multiplier,
        YoujinStage.TRIPLE_YOU: special_outcome_profile("TRIPLE_YOU").multiplier,
    }

    def is_wall_draw(self, state):
        return state.phase != "READY" and len(state.wall) == self.DRAW_WALL_REMAINING

    def __init__(self, config=None):
        self.config = config if config is not None else RulesConfig()

    @staticmethod
    def validate_tiles(tiles):
        ok, message = core.validate_tile_multiset(tiles, include_flowers=False)
        if not ok:
            raise ValueError(message)

    def dealer_base_for_consecutive_hands(self, consecutive_dealer_hands):
        return dealer_base_for_consecutive_hands(consecutive_dealer_hands)

    def next_consecutive_dealer_hands(self, consecutive_dealer_hands, *, dealer_stays):
        return next_consecutive_dealer_hands(
            consecutive_dealer_hands, dealer_stays=dealer_stays
        )

    def match_hand_in_range(self, hand_index):
        return match_hand_in_range(hand_index)

    def _validate_hand(self, hand, gold_tile):
        self.validate_tiles(hand)
        if gold_tile is not None and gold_tile not in core.BASE_TILES:
            raise ValueError("Gold must be a normal tile")
        if gold_tile is not None and hand.count(gold_tile) > 3:
            raise ValueError(
                "Opened gold indicator is non-drawable; a hand can contain at most three gold copies"
            )

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

    def aggregate_fan(self, hand, melds=(), flowers=(), gold_tile=None, *,
                      hu_result=None):
        """Run the evidence-aware FanAggregator V0.1."""
        from .fan import FanAggregator
        return FanAggregator(self).aggregate(
            hand, melds, flowers, gold_tile, hu_result=hu_result
        )

    def kong_fan(self, kind, tile):
        """Return the currently adopted target-room fan for a completed kong.

        Operational rule adopted 2026-09-18, subject to revision if stronger
        direct video evidence conflicts:
        - 大明杠 / MING_GANG: suited 2, honor 3.
        - 补杠/蓄杠/加杠 / ADDED_GANG: same exposed-kong table, suited 2, honor 3.
        - 暗杠 / AN_GANG: suited 3, honor 4.

        Direct target-room confirmations:
        - suited ADD_KONG=2: replay 66fe863f.
        - suited AN_GANG=3: room541913 hand 6 (2026-09-19), where the player
          draws the fourth suited tile, declares a concealed kong, and the
          settlement explicitly lists 杠牌3番.
        Remaining cells are adopted from the in-game Huian rule page and retain
        HIGH_CONFIDENCE provenance.
        """
        try:
            kind = kind if isinstance(kind, KongKind) else KongKind(kind)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid kong kind") from exc
        if tile not in core.BASE_TILES:
            raise ValueError("Kong fan requires a normal tile")
        honor = core.is_honor(tile)
        if kind == KongKind.AN_GANG:
            fan = 4 if honor else 3
        else:
            fan = 3 if honor else 2
        direct_added_suited = kind == KongKind.ADDED_GANG and not honor
        direct_concealed_suited = kind == KongKind.AN_GANG and not honor
        direct_confirmed = direct_added_suited or direct_concealed_suited
        if direct_added_suited:
            evidence = "66fe863f replay: suited added kong displayed as 2 fan"
        elif direct_concealed_suited:
            evidence = (
                "room541913 hand 6 replay 2026-09-19: suited concealed kong "
                "followed by settlement 杠牌3番"
            )
        else:
            evidence = "Huian in-game rule page fan table; adopted pending contrary video"
        return KongFanResult(
            kind=kind,
            tile=tile,
            fan=fan,
            status=(EvidenceStatus.CONFIRMED if direct_confirmed
                    else EvidenceStatus.HIGH_CONFIDENCE),
            evidence=evidence,
        )

    def added_kong_options(self, hand, melds, gold_tile=None):
        """补杠/蓄杠/加杠 candidates: upgrade an existing Peng with a self-drawn fourth tile.

        This is the robbable exposed-kong upgrade branch. It is distinct from
        ``ming_gang`` (大明杠 from an opponent discard) and ``concealed_kongs``
        (暗杠), neither of which is robbable in the target room.
        """
        self._validate_hand(hand, gold_tile)
        self.validate_tiles([*hand, *(tile for meld in melds for tile in meld.tiles)])
        options = []
        for index, meld in enumerate(melds):
            if (meld.kind == "PENG" and len(meld.tiles) == 3
                    and len(set(meld.tiles)) == 1):
                tile = meld.tiles[0]
                if tile != gold_tile and tile in hand:
                    options.append((index, tile))
        return tuple(options)

    def can_sanjindao(
            self, hand, gold_tile, *,
            third_gold_just_received=False,
            opening_check=False,
            later_draw_check=False):
        """Return whether the current Sanjindao choice is open.

        Confirmed target-room forms:
        - opening check: after opening replacement/open-gold, current actor has
          all three playable gold tiles;
        - first mid-hand arrival: a valid draw has just changed 2 gold -> 3 gold;
        - later own-draw re-check: after previously passing, a later draw while
          the player still holds exactly 3 gold can offer Sanjindao again.

        PASS closes only the *current* prompt. It does not permanently disable
        Sanjindao for the hand, and ordinary/Youjin-family play remains available.
        Four playable golds are physically impossible because the opened
        indicator is the fourth copy and never enters the drawable wall.
        """
        self._validate_hand(hand, gold_tile)
        for name, value in (
                ("third_gold_just_received", third_gold_just_received),
                ("opening_check", opening_check),
                ("later_draw_check", later_draw_check)):
            if type(value) is not bool:
                raise ValueError(f"{name} must be boolean")
        if gold_tile is None:
            return False
        count = hand.count(gold_tile)
        return ((opening_check and count == 3)
                or (third_gold_just_received and count == 3)
                or (later_draw_check and count == 3))

    def sanjindao_decision(
            self, hand, gold_tile, *,
            third_gold_just_received=False,
            opening_check=False,
            later_draw_check=False):
        """Return the current Sanjindao declare-or-continue choice."""
        eligible = self.can_sanjindao(
            hand, gold_tile,
            third_gold_just_received=third_gold_just_received,
            opening_check=opening_check,
            later_draw_check=later_draw_check)
        count = hand.count(gold_tile) if gold_tile is not None else 0
        choices = ((SanjindaoChoice.DECLARE_SANJINDAO,
                    SanjindaoChoice.CONTINUE_PLAY) if eligible else ())
        return SanjindaoDecision(eligible, count, choices, self.SANJINDAO_MULTIPLIER)

    def is_youjin_ready_hand(self, hand, gold_tile, open_melds=0):
        """Return whether a post-discard hand is structurally ready to enter Youjin.

        Confirmed 2026-09-20 semantics: reserve exactly one gold as the roaming
        singleton.  All remaining concealed tiles, including any other golds as
        wildcards, must already form every concealed meld still required by the
        5-meld Huian hand.  The next ordinary draw can then pair with the reserved
        gold and complete an ordinary structural Hu.

        This checks structure only.  It does not advance the Youjin stage or
        encode later Double-/Triple-You upgrade timing.
        """
        self._validate_hand(hand, gold_tile)
        nonnegative_int(open_melds, "open_melds")
        if open_melds > 5:
            raise ValueError("At most five melds")
        if gold_tile is None or hand.count(gold_tile) < 1:
            return False
        groups_needed = 5 - open_melds
        if len(hand) != groups_needed * 3 + 1:
            return False

        # Reuse the audited ordinary-Hu solver rather than maintain a second
        # wildcard meld solver.  Add one legal non-gold sentinel draw and require
        # a decomposition whose pair is exactly sentinel + GOLD.  Such a split is
        # equivalent to: current hand = all remaining melds + one roaming gold.
        for tile in core.BASE_TILES:
            if tile == gold_tile or hand.count(tile) >= 4:
                continue
            splits = winning_decompositions(
                [*hand, tile], gold_tile, open_melds, max_solutions=64
            )
            if any(split["pair"] == (tile, "GOLD") for split in splits):
                return True
        return False

    def youjin_entry_discards(self, hand, gold_tile, open_melds=0):
        """Enumerate discards that leave the confirmed single-Youjin-ready shape."""
        self._validate_hand(hand, gold_tile)
        nonnegative_int(open_melds, "open_melds")
        if open_melds > 5:
            raise ValueError("At most five melds")
        expected = (5 - open_melds) * 3 + 2
        if len(hand) != expected:
            return ()
        out = []
        for tile in sorted(set(hand)):
            candidate = list(hand)
            candidate.remove(tile)
            if self.is_youjin_ready_hand(candidate, gold_tile, open_melds):
                out.append(tile)
        return tuple(out)

    def youjin_score_terms(self, stage, *, winner, dealer, winner_fan):
        """Return confirmed terms; fan aggregation and payer remain external."""
        try:
            stage = stage if isinstance(stage, YoujinStage) else YoujinStage(stage)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid Youjin stage") from exc
        for name, value in (("winner", winner), ("dealer", dealer),
                            ("winner_fan", winner_fan)):
            nonnegative_int(value, name)
        if winner not in (0, 1) or dealer not in (0, 1):
            raise ValueError("winner and dealer must be seat 0 or 1")
        if stage not in self.YOUJIN_MULTIPLIERS:
            raise ValueError("Score terms require Youjin, Double-You or Triple-You")
        return YoujinScoreTerms(
            stage=stage,
            youjin_multiplier=self.YOUJIN_MULTIPLIERS[stage],
            dealer_multiplier=DEALER_WIN_MULTIPLIER,
            winner_fan=winner_fan,
        )

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
            "rob_kong": WinSource.ROB_KONG,
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
        if context.source in (WinSource.DISCARD, WinSource.ROB_KONG) and context.winning_tile is None:
            raise ValueError("Non-self-draw Hu analysis requires winning_tile")
        gold_count = hand.count(gold_tile) if gold_tile else 0
        if context.source in (WinSource.DISCARD, WinSource.ROB_KONG):
            if context.winning_tile == gold_tile:
                return HuResult(False, (), gold_tile, open_melds, context)
            if gold_count == 1 and not self.config.single_gold_can_pinghu:
                return HuResult(False, (), gold_tile, open_melds, context)
            if gold_count == 2:
                return HuResult(False, (), gold_tile, open_melds, context)
        # Declining Sanjindao closes only that prompt. Ordinary Hu rights stay
        # independent, and later eligible Sanjindao prompts are handled by the
        # state machine. match_evidence_002 directly confirms a later own-draw
        # re-prompt while all three playable golds remain. A fourth playable
        # copy cannot exist because the opened indicator is non-drawable.
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
            physical_copies = 3 if tile == gold_tile else 4
            remaining = physical_copies - hand.count(tile) - visible_tiles.count(tile)
            context = win_context.with_winning_tile(tile) if win_context is not None else None
            kwargs = {"win_context": context} if context is not None else {}
            if win_type in ("pinghu", "discard", "rob_kong"):
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
