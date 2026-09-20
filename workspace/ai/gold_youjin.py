"""Public-information structural value for Jin / Youjin AI research.

This module deliberately does not assign a score EV to Youjin.  It measures a
narrow, confirmed structural signal only:

- whether a discard can enter single-Youjin immediately;
- after that ordinary discard, how many publicly-live next draws would create
  at least one confirmed Youjin entry discard.

The signal uses only the acting player's hand and public table information.
Opponent concealed tiles and future wall order are never read.
"""
from collections import Counter
from dataclasses import dataclass

from huian._legacy import env
from huian.rules import HuianRules

from .baseline import AgentDecision, MeldAwareShantenAgent
from .shanten import min_shanten_discards, youjin_meld_deficit


@dataclass(frozen=True)
class YoujinDiscardPotential:
    discard: str
    immediate_entry: bool
    future_entry_live_copies: int
    future_entry_types: int
    enabling_draws: tuple[tuple[str, int], ...]
    gold_count_after_discard: int
    meld_deficit: int | None = None

    @property
    def structural_key(self):
        deficit = 99 if self.meld_deficit is None else self.meld_deficit
        return (
            self.immediate_entry,
            -deficit,
            self.future_entry_live_copies,
            self.future_entry_types,
        )


@dataclass(frozen=True)
class GoldYoujinShadowDiagnostic:
    decision_index: int
    phase: str
    gold_count: int
    shanten: int
    min_shanten_frontier_size: int
    baseline_tile: str
    structural_choice_tile: str
    would_change_v010: bool
    signal_differentiated: bool
    baseline_immediate_entry: bool
    best_immediate_entry: bool
    baseline_future_live_copies: int
    best_future_live_copies: int
    future_live_delta: int
    baseline_future_types: int
    best_future_types: int
    future_type_delta: int
    baseline_meld_deficit: int | None
    best_meld_deficit: int | None
    meld_deficit_delta: int | None
    baseline_live_copies: int
    best_live_copies: int
    immediate_live_delta: int
    baseline_effective_types: int
    best_effective_types: int
    immediate_type_delta: int
    hand_index: int | None
    score_margin_for_actor: int | None
    wall_remaining: int


def _public_base_tiles(observation):
    tiles = []
    for river in observation.discards:
        tiles.extend(tile for tile in river if tile in env.BASE_TILES)
    for melds in observation.melds:
        for _, meld_tiles in melds:
            tiles.extend(tile for tile in meld_tiles if tile in env.BASE_TILES)
    return tuple(tiles)


def estimate_youjin_discard_potentials(
        observation, candidate_discards, *, rules=None):
    """Return structural Youjin opportunity for candidate ordinary discards.

    The candidate discard itself becomes public before future-draw live-copy
    counting. The opened Jin indicator is non-drawable, so Jin capacity is 3;
    all other base tiles have physical capacity 4.
    """
    candidates = tuple(dict.fromkeys(candidate_discards))
    if not candidates:
        raise ValueError("candidate_discards must be non-empty")
    if observation.gold_tile is None:
        raise ValueError("Youjin potential requires an opened gold tile")
    if any(tile not in observation.hand for tile in candidates):
        raise ValueError("every candidate discard must be in the acting hand")

    rules = HuianRules() if rules is None else rules
    open_melds = len(observation.melds[observation.seat])
    public = Counter(_public_base_tiles(observation))
    out = []

    for discard in candidates:
        after = list(observation.hand)
        after.remove(discard)
        own = Counter(after)
        public_after = public.copy()
        public_after[discard] += 1

        deficit = youjin_meld_deficit(
            after, observation.gold_tile, open_melds
        )
        immediate = rules.is_youjin_ready_hand(
            after, observation.gold_tile, open_melds
        )
        if (deficit == 0) != immediate:
            raise RuntimeError(
                "youjin_meld_deficit=0 must match confirmed Youjin-ready structure"
            )
        enabling = []
        for draw in env.BASE_TILES:
            capacity = 3 if draw == observation.gold_tile else 4
            live = capacity - own[draw] - public_after[draw]
            if live <= 0:
                continue
            drawn = [*after, draw]
            if rules.youjin_entry_discards(
                    drawn, observation.gold_tile, open_melds):
                enabling.append((draw, live))

        out.append(YoujinDiscardPotential(
            discard=discard,
            immediate_entry=immediate,
            future_entry_live_copies=sum(live for _, live in enabling),
            future_entry_types=len(enabling),
            enabling_draws=tuple(enabling),
            gold_count_after_discard=after.count(observation.gold_tile),
            meld_deficit=deficit,
        ))
    return tuple(out)


class GoldYoujinShadowAgent(MeldAwareShantenAgent):
    """V0.10 policy with read-only Jin/Youjin structural diagnostics.

    The returned action is always exactly V0.10. A hypothetical structural
    choice is computed across the whole minimum-shanten frontier, so the audit
    can measure how much immediate ordinary efficiency would be traded for a
    smaller confirmed Youjin meld deficit. No shadow choice is executed.
    """

    def __init__(self, seed=None, template_samples=32):
        super().__init__(seed=seed, template_samples=template_samples)
        self._gold_diagnostics = []
        self._gold_diagnostic_index = 0

    @property
    def gold_diagnostics(self):
        return tuple(self._gold_diagnostics)

    def choose_decision(self, observation, legal_actions):
        baseline = super().choose_decision(observation, legal_actions)
        if (baseline.action.type != env.ActionType.DISCARD
                or observation.gold_tile is None
                or observation.gold_tile not in observation.hand):
            return baseline

        actions = sorted(legal_actions, key=self._key)
        discards = [
            action for action in actions
            if action.type == env.ActionType.DISCARD
        ]
        if len(discards) < 2:
            return baseline

        legal_by_tile = {action.tile: action for action in discards}
        frontier = min_shanten_discards(
            observation.hand,
            gold_tile=observation.gold_tile,
            open_melds=len(observation.melds[observation.seat]),
            visible_tiles=_public_base_tiles(observation),
            allowed_discards=tuple(legal_by_tile),
        )
        candidates = tuple(item.discard for item in frontier)
        potentials = estimate_youjin_discard_potentials(
            observation, candidates
        )
        by_tile = {item.discard: item for item in potentials}
        by_eff = {item.discard: item for item in frontier}
        structural_choice = max(
            potentials,
            key=lambda item: (
                item.structural_key,
                -env.BASE_TILES.index(item.discard),
            ),
        )
        baseline_potential = by_tile[baseline.action.tile]
        baseline_eff = by_eff[baseline.action.tile]
        best_eff = by_eff[structural_choice.discard]
        distinct_keys = {item.structural_key for item in potentials}
        context = observation.match_context
        baseline_deficit = baseline_potential.meld_deficit
        best_deficit = structural_choice.meld_deficit
        deficit_delta = (
            None if baseline_deficit is None or best_deficit is None
            else best_deficit - baseline_deficit
        )
        self._gold_diagnostics.append(GoldYoujinShadowDiagnostic(
            decision_index=self._gold_diagnostic_index,
            phase=observation.phase,
            gold_count=observation.hand.count(observation.gold_tile),
            shanten=frontier[0].shanten,
            min_shanten_frontier_size=len(frontier),
            baseline_tile=baseline.action.tile,
            structural_choice_tile=structural_choice.discard,
            would_change_v010=(
                structural_choice.discard != baseline.action.tile),
            signal_differentiated=len(distinct_keys) > 1,
            baseline_immediate_entry=baseline_potential.immediate_entry,
            best_immediate_entry=structural_choice.immediate_entry,
            baseline_future_live_copies=(
                baseline_potential.future_entry_live_copies),
            best_future_live_copies=(
                structural_choice.future_entry_live_copies),
            future_live_delta=(
                structural_choice.future_entry_live_copies
                - baseline_potential.future_entry_live_copies),
            baseline_future_types=baseline_potential.future_entry_types,
            best_future_types=structural_choice.future_entry_types,
            future_type_delta=(
                structural_choice.future_entry_types
                - baseline_potential.future_entry_types),
            baseline_meld_deficit=baseline_deficit,
            best_meld_deficit=best_deficit,
            meld_deficit_delta=deficit_delta,
            baseline_live_copies=baseline_eff.total_live_copies,
            best_live_copies=best_eff.total_live_copies,
            immediate_live_delta=(
                best_eff.total_live_copies - baseline_eff.total_live_copies),
            baseline_effective_types=len(baseline_eff.effective_tiles),
            best_effective_types=len(best_eff.effective_tiles),
            immediate_type_delta=(
                len(best_eff.effective_tiles) - len(baseline_eff.effective_tiles)),
            hand_index=(context.hand_index if context else None),
            score_margin_for_actor=(
                context.margin_for(observation.seat) if context else None),
            wall_remaining=observation.wall_remaining,
        ))
        self._gold_diagnostic_index += 1
        return AgentDecision(
            baseline.action,
            f"{baseline.reason}; gold_youjin_shadow keeps V0.10 action "
            f"(shadow_choice={structural_choice.discard}, "
            f"meld_deficit={baseline_potential.meld_deficit}"
            f"->{structural_choice.meld_deficit}, "
            f"live={baseline_eff.total_live_copies}"
            f"->{best_eff.total_live_copies}, "
            f"types={len(baseline_eff.effective_tiles)}"
            f"->{len(best_eff.effective_tiles)}, "
            f"future_live={structural_choice.future_entry_live_copies})",
        )
