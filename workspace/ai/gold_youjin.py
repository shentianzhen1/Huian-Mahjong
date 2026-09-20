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
from .shanten import best_offense_ties, min_shanten_discards


@dataclass(frozen=True)
class YoujinDiscardPotential:
    discard: str
    immediate_entry: bool
    future_entry_live_copies: int
    future_entry_types: int
    enabling_draws: tuple[tuple[str, int], ...]
    gold_count_after_discard: int

    @property
    def structural_key(self):
        return (
            self.immediate_entry,
            self.future_entry_live_copies,
            self.future_entry_types,
        )


@dataclass(frozen=True)
class GoldYoujinShadowDiagnostic:
    decision_index: int
    phase: str
    gold_count: int
    shanten: int
    exact_offense_tie_count: int
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

        immediate = rules.is_youjin_ready_hand(
            after, observation.gold_tile, open_melds
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
        ))
    return tuple(out)


class GoldYoujinShadowAgent(MeldAwareShantenAgent):
    """V0.10 policy with read-only Jin/Youjin structural diagnostics.

    The returned action is always exactly V0.10.  A hypothetical structural
    choice is computed only inside V0.10's exact ordinary-offense tie, so the
    audit can answer whether confirmed Youjin structure has enough signal to
    justify a future tie-break experiment without sacrificing current offense.
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
        ties = best_offense_ties(
            observation.hand,
            gold_tile=observation.gold_tile,
            open_melds=len(observation.melds[observation.seat]),
            visible_tiles=_public_base_tiles(observation),
            allowed_discards=tuple(legal_by_tile),
        )
        candidates = tuple(item.discard for item in ties)
        potentials = estimate_youjin_discard_potentials(
            observation, candidates
        )
        by_tile = {item.discard: item for item in potentials}
        structural_choice = max(
            potentials,
            key=lambda item: (
                item.structural_key,
                -env.BASE_TILES.index(item.discard),
            ),
        )
        baseline_potential = by_tile[baseline.action.tile]
        distinct_keys = {item.structural_key for item in potentials}
        context = observation.match_context
        self._gold_diagnostics.append(GoldYoujinShadowDiagnostic(
            decision_index=self._gold_diagnostic_index,
            phase=observation.phase,
            gold_count=observation.hand.count(observation.gold_tile),
            shanten=ties[0].shanten,
            exact_offense_tie_count=len(ties),
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
            f"immediate={structural_choice.immediate_entry}, "
            f"future_live={structural_choice.future_entry_live_copies}, "
            f"future_types={structural_choice.future_entry_types})",
        )


@dataclass(frozen=True)
class ConstrainedGoldYoujinDiagnostic:
    decision_index: int
    baseline_tile: str
    chosen_tile: str
    changed_from_v010: bool
    shanten: int
    baseline_live_copies: int
    chosen_live_copies: int
    immediate_live_delta: int
    baseline_effective_types: int
    chosen_effective_types: int
    immediate_type_delta: int
    baseline_immediate_entry: bool
    chosen_immediate_entry: bool
    baseline_future_live: int
    chosen_future_live: int
    future_live_delta: int
    baseline_future_types: int
    chosen_future_types: int
    future_type_delta: int
    reason_gate: str


class ConstrainedGoldYoujinAgent(MeldAwareShantenAgent):
    """Experimental V0.15 candidate: conservative Jin/Youjin structural override.

    Hard constraints:
    - V0.10 remains fallback and CurrentAgent is unchanged.
    - only ordinary discard decisions with exactly one concealed Jin;
    - ordinary shanten may never worsen;
    - effective-tile type count may never decrease;
    - immediate live effective copies may drop by at most max_live_loss;
    - Jin itself is never chosen as the V0.15 override discard.

    Override requires either immediate single-Youjin entry or a material
    next-draw Youjin-entry improvement. This is a constrained structural
    heuristic, not calibrated score EV.
    """

    def __init__(self, seed=None, template_samples=32, *,
                 max_live_loss=1, min_future_live_gain=4,
                 min_future_type_gain=1):
        super().__init__(seed=seed, template_samples=template_samples)
        for name, value in (
                ("max_live_loss", max_live_loss),
                ("min_future_live_gain", min_future_live_gain),
                ("min_future_type_gain", min_future_type_gain)):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        self.max_live_loss = max_live_loss
        self.min_future_live_gain = min_future_live_gain
        self.min_future_type_gain = min_future_type_gain
        self._v015_diagnostics = []
        self._v015_index = 0

    @property
    def v015_diagnostics(self):
        return tuple(self._v015_diagnostics)

    def _record(self, baseline_item, chosen_item, baseline_potential,
                chosen_potential, gate):
        self._v015_diagnostics.append(ConstrainedGoldYoujinDiagnostic(
            decision_index=self._v015_index,
            baseline_tile=baseline_item.discard,
            chosen_tile=chosen_item.discard,
            changed_from_v010=(chosen_item.discard != baseline_item.discard),
            shanten=baseline_item.shanten,
            baseline_live_copies=baseline_item.total_live_copies,
            chosen_live_copies=chosen_item.total_live_copies,
            immediate_live_delta=(
                chosen_item.total_live_copies - baseline_item.total_live_copies),
            baseline_effective_types=len(baseline_item.effective_tiles),
            chosen_effective_types=len(chosen_item.effective_tiles),
            immediate_type_delta=(
                len(chosen_item.effective_tiles) - len(baseline_item.effective_tiles)),
            baseline_immediate_entry=baseline_potential.immediate_entry,
            chosen_immediate_entry=chosen_potential.immediate_entry,
            baseline_future_live=baseline_potential.future_entry_live_copies,
            chosen_future_live=chosen_potential.future_entry_live_copies,
            future_live_delta=(
                chosen_potential.future_entry_live_copies
                - baseline_potential.future_entry_live_copies),
            baseline_future_types=baseline_potential.future_entry_types,
            chosen_future_types=chosen_potential.future_entry_types,
            future_type_delta=(
                chosen_potential.future_entry_types
                - baseline_potential.future_entry_types),
            reason_gate=gate,
        ))
        self._v015_index += 1

    def choose_decision(self, observation, legal_actions):
        baseline = super().choose_decision(observation, legal_actions)
        if (baseline.action.type != env.ActionType.DISCARD
                or observation.gold_tile is None
                or observation.hand.count(observation.gold_tile) != 1):
            return baseline

        actions = sorted(legal_actions, key=self._key)
        discards = [a for a in actions if a.type == env.ActionType.DISCARD]
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
        by_eff = {item.discard: item for item in frontier}
        baseline_item = by_eff.get(baseline.action.tile)
        if baseline_item is None:
            return baseline

        candidate_tiles = tuple(
            item.discard for item in frontier
            if item.discard != observation.gold_tile
            and item.total_live_copies >=
                baseline_item.total_live_copies - self.max_live_loss
            and len(item.effective_tiles) >= len(baseline_item.effective_tiles)
        )
        if not candidate_tiles:
            return baseline

        potential_tiles = tuple(dict.fromkeys((
            baseline.action.tile, *candidate_tiles
        )))
        potentials = estimate_youjin_discard_potentials(
            observation, potential_tiles)
        by_potential = {item.discard: item for item in potentials}
        baseline_potential = by_potential[baseline.action.tile]

        qualified = []
        for tile in candidate_tiles:
            potential = by_potential[tile]
            immediate_gain = (
                potential.immediate_entry and not baseline_potential.immediate_entry
            )
            future_gain = (
                potential.future_entry_live_copies
                    - baseline_potential.future_entry_live_copies
                    >= self.min_future_live_gain
                and potential.future_entry_types
                    - baseline_potential.future_entry_types
                    >= self.min_future_type_gain
            )
            if immediate_gain or future_gain:
                qualified.append((tile, immediate_gain, future_gain))

        if not qualified:
            self._record(baseline_item, baseline_item, baseline_potential,
                         baseline_potential, "no_material_youjin_gain")
            return baseline

        chosen_tile, immediate_gain, future_gain = max(
            qualified,
            key=lambda entry: (
                by_potential[entry[0]].immediate_entry,
                by_potential[entry[0]].future_entry_live_copies,
                by_potential[entry[0]].future_entry_types,
                by_eff[entry[0]].total_live_copies,
                len(by_eff[entry[0]].effective_tiles),
                -env.BASE_TILES.index(entry[0]),
            ),
        )
        chosen_item = by_eff[chosen_tile]
        chosen_potential = by_potential[chosen_tile]
        gate = "immediate_youjin_entry" if immediate_gain else "future_youjin_gain"
        self._record(baseline_item, chosen_item, baseline_potential,
                     chosen_potential, gate)

        if chosen_tile == baseline.action.tile:
            return baseline

        return AgentDecision(
            legal_by_tile[chosen_tile],
            f"DISCARD {chosen_tile}: constrained_gold_youjin_v0.15_candidate "
            f"(baseline={baseline.action.tile}; shanten={chosen_item.shanten}; "
            f"live={baseline_item.total_live_copies}->{chosen_item.total_live_copies}; "
            f"types={len(baseline_item.effective_tiles)}"
            f"->{len(chosen_item.effective_tiles)}; "
            f"immediate_youjin={baseline_potential.immediate_entry}"
            f"->{chosen_potential.immediate_entry}; "
            f"future_youjin_live={baseline_potential.future_entry_live_copies}"
            f"->{chosen_potential.future_entry_live_copies}; "
            f"future_youjin_types={baseline_potential.future_entry_types}"
            f"->{chosen_potential.future_entry_types}; gate={gate}); "
            f"hard constraints: same shanten, live loss<={self.max_live_loss}, "
            f"effective types nondecreasing, never override-discard Jin",
        )
