"""Explainable ordinary-hand heuristics, independent of legality and scoring."""
from dataclasses import dataclass
from collections import Counter
from typing import Any

from huian._legacy import env
from .danger import estimate_discard_danger
from .opponent import (estimate_tenpai_wait_loss_scores,
                       estimate_tenpai_wait_risk_scores)
from .shanten import (analyze_two_ply_offense, best_discard,
                      best_offense_ties, min_shanten_discards)


@dataclass(frozen=True)
class AgentDecision:
    action: Any
    reason: str


@dataclass(frozen=True)
class MatchObservationContext:
    """Public eight-hand match context available to the acting player."""

    scores: tuple[int, int]
    hand_index: int
    hands_remaining: int
    dealer: int
    current_dealer_base: int
    consecutive_dealer_hands: int

    def __post_init__(self):
        if (not isinstance(self.scores, tuple) or len(self.scores) != 2
                or any(type(value) is not int for value in self.scores)):
            raise ValueError("scores must be a two-integer tuple")
        if type(self.hand_index) is not int or not 0 <= self.hand_index <= 7:
            raise ValueError("hand_index must be between 0 and 7")
        if type(self.hands_remaining) is not int or not 1 <= self.hands_remaining <= 8:
            raise ValueError("hands_remaining must be between 1 and 8")
        if self.hand_index + self.hands_remaining != 8:
            raise ValueError("hand_index + hands_remaining must equal 8")
        if type(self.dealer) is not int or self.dealer not in (0, 1):
            raise ValueError("dealer must be seat 0 or 1")
        if type(self.current_dealer_base) is not int or self.current_dealer_base < 0:
            raise ValueError("current_dealer_base must be a nonnegative integer")
        if (type(self.consecutive_dealer_hands) is not int
                or self.consecutive_dealer_hands < 1):
            raise ValueError("consecutive_dealer_hands must be >= 1")

    @property
    def margin(self):
        """Seat-0 score minus seat-1 score."""
        return self.scores[0] - self.scores[1]

    def margin_for(self, seat):
        if type(seat) is not int or seat not in (0, 1):
            raise ValueError("seat must be 0 or 1")
        return self.margin if seat == 0 else -self.margin

@dataclass(frozen=True)
class PlayerObservation:
    seat: int
    hand: tuple[str, ...]
    gold_tile: str | None
    phase: str
    dealer: int
    wall_remaining: int
    discards: tuple[tuple[str, ...], ...]
    flowers: tuple[tuple[str, ...], ...]
    melds: tuple[tuple[tuple[str, tuple[str, ...]], ...], ...]
    match_context: MatchObservationContext | None = None

    @classmethod
    def from_state(cls, state, match_context=None):
        """Never expose the opponent hand, wall order, or reserved tiles."""
        if match_context is not None and not isinstance(match_context, MatchObservationContext):
            raise TypeError("match_context must be MatchObservationContext or None")
        seat = state.current_player
        return cls(
            seat, tuple(state.hands[seat]), state.gold_tile, state.phase,
            state.dealer, state.wall_remaining(),
            tuple(tuple(river) for river in state.discards),
            tuple(tuple(flowers) for flowers in state.flowers),
            tuple(tuple((meld.kind, tuple(meld.tiles)) for meld in melds)
                  for melds in state.melds),
            match_context,
        )


class BaselineAgent:
    """HU first; retain gold, pairs and suited connections; otherwise PASS.

    This is a deterministic single-hand heuristic, not EV, match-score-aware,
    or a special-rule strategy. The project objective is final score after 8 hands.
    Reasons belong to the decision/log, never to executable action metadata.
    """

    def __init__(self, seed=None):
        # Accept the same factory signature as RandomAgent. No randomness needed.
        pass

    @staticmethod
    def _retention(tile, hand, gold_tile):
        counts = Counter(hand)
        pair = counts[tile] >= 2
        adjacent = gapped = 0
        if len(tile) == 2 and tile[0] in "MPS" and tile[1] in "123456789":
            rank = int(tile[1])
            adjacent = sum(counts[f"{tile[0]}{rank + d}"] > 0 for d in (-1, 1))
            gapped = sum(counts[f"{tile[0]}{rank + d}"] > 0 for d in (-2, 2))
        # Lexicographic priorities make the policy easy to inspect.
        return (tile == gold_tile, pair, adjacent + gapped, adjacent)

    @staticmethod
    def _key(action):
        return (action.type.value, action.tile or "", tuple(action.tiles))

    def choose_action(self, observation, legal_actions):
        """Return an action plus its explanation."""
        return self.choose_decision(observation, legal_actions)

    def choose_decision(self, observation, legal_actions):
        if not legal_actions:
            raise ValueError("No legal actions")
        actions = sorted(legal_actions, key=self._key)
        wins = [a for a in actions if a.type.value in ("HU", "ROB_KONG_HU")]
        if wins:
            return AgentDecision(wins[0], f"{wins[0].type.value}: take the legal ordinary-shape win")
        discards = [a for a in actions if a.type.value == "DISCARD"]
        if discards:
            action = min(discards, key=lambda a: (
                self._retention(a.tile, observation.hand, observation.gold_tile),
                self._key(a),
            ))
            gold, pair, connections, adjacent = self._retention(
                action.tile, observation.hand, observation.gold_tile)
            return AgentDecision(
                action,
                f"DISCARD {action.tile}: lowest retention "
                f"(gold={gold}, pair={pair}, connections={connections}, "
                f"adjacent={adjacent}); preserve gold, pairs and suited connections",
            )
        passes = [a for a in actions if a.type.value == "PASS"]
        if passes:
            return AgentDecision(passes[0], "PASS: preserve the current hand over optional melds")
        return AgentDecision(actions[0], f"{actions[0].type.value}: take the required legal action")


class EfficiencyAgent(BaselineAgent):
    """Experimental V0.2 discard policy using public one-draw improvement potential.

    It deliberately keeps the BaselineAgent action priorities: take a legal Hu,
    PASS optional meld claims, and execute forced actions. Only DISCARD ranking
    changes. The evaluator uses the player's concealed hand plus public discards
    and melds; it never receives the opponent concealed hand or wall order.
    """

    _COUNT_VALUE = (0, 0, 5, 9, 11)

    @classmethod
    def _shape_value(cls, hand, gold_tile):
        counts = Counter(hand)
        value = 0
        for tile, count in counts.items():
            if tile == gold_tile:
                value += 14 * count
                continue
            value += cls._COUNT_VALUE[min(count, 4)]

        for suit in "MPS":
            ranks = {rank: counts[f"{suit}{rank}"] for rank in range(1, 10)}
            for rank in range(1, 9):
                value += 3 * min(ranks[rank], ranks[rank + 1])
            for rank in range(1, 8):
                value += min(ranks[rank], ranks[rank + 2])
        return value

    @staticmethod
    def _public_visible_counts(observation):
        visible = Counter()
        for river in observation.discards:
            visible.update(tile for tile in river if tile in env.BASE_TILES)
        for melds in observation.melds:
            for _, tiles in melds:
                visible.update(tile for tile in tiles if tile in env.BASE_TILES)
        return visible

    @classmethod
    def discard_diagnostics(cls, observation, tile):
        remaining_hand = list(observation.hand)
        remaining_hand.remove(tile)
        base_value = cls._shape_value(remaining_hand, observation.gold_tile)
        own = Counter(remaining_hand)
        public = cls._public_visible_counts(observation)

        weighted_gain = 0
        live_improving_copies = 0
        improving_types = 0
        for draw in env.BASE_TILES:
            live = max(0, 4 - own[draw] - public[draw])
            if not live:
                continue
            gain = cls._shape_value(
                [*remaining_hand, draw], observation.gold_tile) - base_value
            if gain <= 0:
                continue
            weighted_gain += gain * live
            live_improving_copies += live
            improving_types += 1

        retention = cls._retention(
            tile, observation.hand, observation.gold_tile)
        return {
            "base_shape": base_value,
            "weighted_gain": weighted_gain,
            "live_improving_copies": live_improving_copies,
            "improving_types": improving_types,
            "discard_retention": retention,
        }

    def choose_decision(self, observation, legal_actions):
        if not legal_actions:
            raise ValueError("No legal actions")
        actions = sorted(legal_actions, key=self._key)
        wins = [a for a in actions if a.type.value in ("HU", "ROB_KONG_HU")]
        if wins:
            return AgentDecision(
                wins[0], f"{wins[0].type.value}: take the legal ordinary-shape win")

        discards = [a for a in actions if a.type.value == "DISCARD"]
        if discards:
            diagnostics = {
                action.tile: self.discard_diagnostics(observation, action.tile)
                for action in discards
            }
            action = max(
                discards,
                key=lambda a: (
                    diagnostics[a.tile]["base_shape"],
                    diagnostics[a.tile]["weighted_gain"],
                    diagnostics[a.tile]["live_improving_copies"],
                    diagnostics[a.tile]["improving_types"],
                    tuple(-int(x)
                          for x in diagnostics[a.tile]["discard_retention"]),
                    tuple(-ord(ch) for ch in a.tile),
                ),
            )
            info = diagnostics[action.tile]
            return AgentDecision(
                action,
                f"DISCARD {action.tile}: efficiency_v0.2 "
                f"(shape={info['base_shape']}, weighted_gain={info['weighted_gain']}, "
                f"live_improving={info['live_improving_copies']}, "
                f"types={info['improving_types']}); use only private hand + public table",
            )

        passes = [a for a in actions if a.type.value == "PASS"]
        if passes:
            return AgentDecision(
                passes[0], "PASS: preserve the current hand over optional melds")
        return AgentDecision(
            actions[0], f"{actions[0].type.value}: take the required legal action")



class ShantenAgent(BaselineAgent):
    """Experimental V0.3: ordinary shanten + live effective tiles for discards.

    Action priority deliberately stays conservative: legal Hu first, optional
    claims PASS, forced actions unchanged. Only discard selection uses the
    Huian 16/17-tile shanten engine, public rivers and public melds.
    """

    @staticmethod
    def _public_tiles(observation):
        tiles = []
        for river in observation.discards:
            tiles.extend(river)
        for melds in observation.melds:
            for _, meld_tiles in melds:
                tiles.extend(meld_tiles)
        return tuple(tile for tile in tiles if tile in env.BASE_TILES)

    def choose_decision(self, observation, legal_actions):
        if not legal_actions:
            raise ValueError("No legal actions")
        actions = sorted(legal_actions, key=self._key)
        wins = [a for a in actions if a.type.value in ("HU", "ROB_KONG_HU")]
        if wins:
            return AgentDecision(
                wins[0], f"{wins[0].type.value}: take the legal ordinary-shape win")

        discards = [a for a in actions if a.type.value == "DISCARD"]
        if discards:
            open_melds = len(observation.melds[observation.seat])
            legal_by_tile = {action.tile: action for action in discards}
            choice = best_discard(
                observation.hand,
                gold_tile=observation.gold_tile,
                open_melds=open_melds,
                visible_tiles=self._public_tiles(observation),
                allowed_discards=tuple(legal_by_tile),
            )
            action = legal_by_tile[choice.discard]
            waits = ",".join(choice.effective_tile_types[:8])
            if len(choice.effective_tile_types) > 8:
                waits += ",..."
            return AgentDecision(
                action,
                f"DISCARD {choice.discard}: shanten_v0.1 "
                f"(shanten={choice.shanten}, live={choice.total_live_copies}, "
                f"types={len(choice.effective_tiles)}, effective=[{waits}]); "
                f"use private hand + public table only",
            )

        passes = [a for a in actions if a.type.value == "PASS"]
        if passes:
            return AgentDecision(
                passes[0], "PASS: preserve the current hand over optional melds")
        return AgentDecision(
            actions[0], f"{actions[0].type.value}: take the required legal action")


class DangerAwareShantenAgent(ShantenAgent):
    """Experimental V0.4: shanten offense plus public exposure risk.

    Shanten is a hard constraint: the agent never chooses a discard from a
    worse shanten layer for safety. Inside the minimum-shanten frontier it
    balances live effective copies/types against an auditable public risk
    proxy. risk_units is not a deal-in probability.
    """

    def __init__(self, seed=None, danger_weight=0.5):
        if isinstance(danger_weight, bool) or not isinstance(danger_weight, (int, float)):
            raise ValueError("danger_weight must be a non-negative number")
        if danger_weight < 0:
            raise ValueError("danger_weight must be a non-negative number")
        self.danger_weight = float(danger_weight)

    @staticmethod
    def _tile_order(tile):
        return env.BASE_TILES.index(tile)

    def _danger_weight_for(self, observation):
        return self.danger_weight

    def _policy_label(self):
        return "danger_shanten_v0.4"

    def choose_decision(self, observation, legal_actions):
        if not legal_actions:
            raise ValueError("No legal actions")
        actions = sorted(legal_actions, key=self._key)
        wins = [a for a in actions if a.type.value in ("HU", "ROB_KONG_HU")]
        if wins:
            return AgentDecision(
                wins[0], f"{wins[0].type.value}: take the legal ordinary-shape win")

        discards = [a for a in actions if a.type.value == "DISCARD"]
        if discards:
            open_melds = len(observation.melds[observation.seat])
            legal_by_tile = {action.tile: action for action in discards}
            frontier = min_shanten_discards(
                observation.hand,
                gold_tile=observation.gold_tile,
                open_melds=open_melds,
                visible_tiles=self._public_tiles(observation),
                allowed_discards=tuple(legal_by_tile),
            )
            danger_weight = self._danger_weight_for(observation)
            diagnostics = {}
            for item in frontier:
                danger = estimate_discard_danger(observation, item.discard)
                offense = float(item.total_live_copies)
                adjusted = offense - danger_weight * danger.risk_units
                diagnostics[item.discard] = (item, danger, offense, adjusted)

            choice = max(
                frontier,
                key=lambda item: (
                    diagnostics[item.discard][3],
                    item.total_live_copies,
                    len(item.effective_tiles),
                    -self._tile_order(item.discard),
                ),
            )
            item, danger, offense, adjusted = diagnostics[choice.discard]
            action = legal_by_tile[choice.discard]
            waits = ",".join(item.effective_tile_types[:8])
            if len(item.effective_tile_types) > 8:
                waits += ",..."
            return AgentDecision(
                action,
                f"DISCARD {choice.discard}: {self._policy_label()} "
                f"(shanten={item.shanten}, live={item.total_live_copies}, "
                f"types={len(item.effective_tiles)}, offense={offense:.2f}, "
                f"risk_units={danger.risk_units}, weight={danger_weight:.2f}, "
                f"adjusted={adjusted:.2f}, effective=[{waits}]); "
                f"risk_units is public exposure, not a probability",
            )

        passes = [a for a in actions if a.type.value == "PASS"]
        if passes:
            return AgentDecision(
                passes[0], "PASS: preserve the current hand over optional melds")
        return AgentDecision(
            actions[0], f"{actions[0].type.value}: take the required legal action")


class MatchAwareShantenAgent(DangerAwareShantenAgent):
    """Experimental V0.5: use risk only to protect a late-match lead.

    Ordinary shanten remains a hard constraint. Before the final late_hands
    or whenever the acting player is tied/behind, this policy is exactly the
    V0.3 live-effective-tile policy. A small public-risk penalty is enabled
    only while leading late in the fixed eight-hand match.
    """

    def __init__(self, seed=None, late_lead_weight=0.25, late_hands=3):
        super().__init__(seed=seed, danger_weight=late_lead_weight)
        if type(late_hands) is not int or not 1 <= late_hands <= 8:
            raise ValueError("late_hands must be an integer between 1 and 8")
        self.late_hands = late_hands

    def _danger_weight_for(self, observation):
        context = observation.match_context
        if context is None:
            return 0.0
        if context.hands_remaining > self.late_hands:
            return 0.0
        if context.margin_for(observation.seat) <= 0:
            return 0.0
        return self.danger_weight

    def _policy_label(self):
        return "match_aware_shanten_v0.5"


class TenpaiRiskTieBreakAgent(ShantenAgent):
    """Promoted V0.6: risk only breaks exact V0.3 offense ties.

    The policy may never trade away shanten, total live effective copies or
    effective-tile type count. Tenpai-conditioned risk replaces only V0.3's
    final canonical tile-order tie break. risk_score is explicitly not an
    absolute deal-in probability.
    """

    def __init__(self, seed=None, template_samples=32):
        if seed is not None and (type(seed) is not int):
            raise ValueError("seed must be an integer or None")
        if type(template_samples) is not int or template_samples <= 0:
            raise ValueError("template_samples must be a positive integer")
        self.seed = 0 if seed is None else seed
        self.template_samples = template_samples
        self._discard_index = 0

    @staticmethod
    def _tile_order(tile):
        return env.BASE_TILES.index(tile)

    def _next_risk_seed(self):
        value = self.seed * 1_000_003 + self._discard_index
        self._discard_index += 1
        return value

    def choose_decision(self, observation, legal_actions):
        if not legal_actions:
            raise ValueError("No legal actions")
        actions = sorted(legal_actions, key=self._key)
        wins = [a for a in actions if a.type.value in ("HU", "ROB_KONG_HU")]
        if wins:
            return AgentDecision(
                wins[0], f"{wins[0].type.value}: take the legal ordinary-shape win")

        discards = [a for a in actions if a.type.value == "DISCARD"]
        if discards:
            open_melds = len(observation.melds[observation.seat])
            legal_by_tile = {action.tile: action for action in discards}
            ties = best_offense_ties(
                observation.hand,
                gold_tile=observation.gold_tile,
                open_melds=open_melds,
                visible_tiles=self._public_tiles(observation),
                allowed_discards=tuple(legal_by_tile),
            )
            risk_seed = self._next_risk_seed()
            if len(ties) == 1:
                choice = ties[0]
                action = legal_by_tile[choice.discard]
                return AgentDecision(
                    action,
                    f"DISCARD {choice.discard}: tenpai_risk_tiebreak_v0.6 "
                    f"(no exact offense tie; shanten={choice.shanten}, "
                    f"live={choice.total_live_copies}, "
                    f"types={len(choice.effective_tiles)}); preserve V0.3 choice",
                )

            candidates = tuple(item.discard for item in ties)
            # Risk currently models ordinary Ron only. Never let it learn that
            # discarding Jin is "safe" and thereby override Jin fan/Youjin value.
            if observation.gold_tile in candidates:
                choice = ties[0]
                action = legal_by_tile[choice.discard]
                return AgentDecision(
                    action,
                    f"DISCARD {choice.discard}: tenpai_risk_tiebreak_v0.6 "
                    f"(exact offense tie includes gold; preserve V0.3 tile-order "
                    f"choice because special/gold EV is outside risk model)",
                )
            try:
                estimates = estimate_tenpai_wait_risk_scores(
                    observation, candidates, samples=self.template_samples,
                    seed=risk_seed)
            except RuntimeError:
                choice = ties[0]
                action = legal_by_tile[choice.discard]
                return AgentDecision(
                    action,
                    f"DISCARD {choice.discard}: tenpai_risk_tiebreak_v0.6 "
                    f"(risk templates unavailable; preserve V0.3 tile-order choice)",
                )
            by_tile = {item.tile: item for item in estimates}
            choice = min(
                ties,
                key=lambda item: (
                    by_tile[item.discard].risk_score,
                    self._tile_order(item.discard),
                ),
            )
            risk = by_tile[choice.discard]
            action = legal_by_tile[choice.discard]
            alternatives = ",".join(
                f"{tile}:{by_tile[tile].risk_score:.3f}"
                for tile in candidates)
            return AgentDecision(
                action,
                f"DISCARD {choice.discard}: tenpai_risk_tiebreak_v0.6 "
                f"(exact offense tie: shanten={choice.shanten}, "
                f"live={choice.total_live_copies}, "
                f"types={len(choice.effective_tiles)}; "
                f"relative_risk={risk.risk_score:.3f}, "
                f"templates={risk.templates_used}; candidates=[{alternatives}]); "
                f"risk_score is relative tenpai-wait ranking, not a probability",
            )

        passes = [a for a in actions if a.type.value == "PASS"]
        if passes:
            return AgentDecision(
                passes[0], "PASS: preserve the current hand over optional melds")
        return AgentDecision(
            actions[0], f"{actions[0].type.value}: take the required legal action")


class TenpaiLossTieBreakAgent(TenpaiRiskTieBreakAgent):
    """Experimental V0.7a: loss-index-first inside V0.6 offense ties.

    Like V0.6, this policy may never trade away shanten, total live effective
    copies or effective-tile type count. If all score inputs for every matching
    synthetic ordinary-Ron template are CONFIRMED, it ranks tied discards by a
    tenpai-conditioned loss index. That index is not an absolute EV because the
    model is conditioned on the opponent already being in tenpai.

    Missing match context, Jin in the tied candidates, template failure or any
    unconfirmed/incomplete fan input falls back to V0.6 relative-risk ranking.
    """

    def _policy_label(self):
        return "tenpai_loss_tiebreak_v0.7a"

    def _loss_sort_key(self, item, estimate):
        return (
            estimate.loss_index,
            estimate.risk_score,
            self._tile_order(item.discard),
        )

    def _v06_risk_fallback(self, observation, ties, legal_by_tile, risk_seed,
                           reason):
        candidates = tuple(item.discard for item in ties)
        try:
            estimates = estimate_tenpai_wait_risk_scores(
                observation, candidates, samples=self.template_samples,
                seed=risk_seed)
        except RuntimeError:
            choice = ties[0]
            return AgentDecision(
                legal_by_tile[choice.discard],
                f"DISCARD {choice.discard}: {self._policy_label()} "
                f"({reason}; V0.6 templates unavailable; preserve V0.3 tile-order choice)",
            )
        by_tile = {item.tile: item for item in estimates}
        choice = min(
            ties,
            key=lambda item: (
                by_tile[item.discard].risk_score,
                self._tile_order(item.discard),
            ),
        )
        risk = by_tile[choice.discard]
        alternatives = ",".join(
            f"{tile}:{by_tile[tile].risk_score:.3f}"
            for tile in candidates)
        return AgentDecision(
            legal_by_tile[choice.discard],
            f"DISCARD {choice.discard}: {self._policy_label()} "
            f"({reason}; fallback=v0.6_relative_risk; "
            f"relative_risk={risk.risk_score:.3f}, "
            f"templates={risk.templates_used}; candidates=[{alternatives}]); "
            f"risk_score is not a probability",
        )

    def choose_decision(self, observation, legal_actions):
        if not legal_actions:
            raise ValueError("No legal actions")
        actions = sorted(legal_actions, key=self._key)
        wins = [a for a in actions if a.type.value in ("HU", "ROB_KONG_HU")]
        if wins:
            return AgentDecision(
                wins[0], f"{wins[0].type.value}: take the legal ordinary-shape win")

        discards = [a for a in actions if a.type.value == "DISCARD"]
        if discards:
            open_melds = len(observation.melds[observation.seat])
            legal_by_tile = {action.tile: action for action in discards}
            ties = best_offense_ties(
                observation.hand,
                gold_tile=observation.gold_tile,
                open_melds=open_melds,
                visible_tiles=self._public_tiles(observation),
                allowed_discards=tuple(legal_by_tile),
            )
            risk_seed = self._next_risk_seed()
            if len(ties) == 1:
                choice = ties[0]
                return AgentDecision(
                    legal_by_tile[choice.discard],
                    f"DISCARD {choice.discard}: {self._policy_label()} "
                    f"(no exact offense tie; preserve V0.6/V0.3 choice)",
                )

            candidates = tuple(item.discard for item in ties)
            if observation.gold_tile in candidates:
                choice = ties[0]
                return AgentDecision(
                    legal_by_tile[choice.discard],
                    f"DISCARD {choice.discard}: {self._policy_label()} "
                    f"(exact offense tie includes gold; preserve V0.3 tile-order "
                    f"choice because special/gold EV is outside loss model)",
                )

            if observation.match_context is None:
                return self._v06_risk_fallback(
                    observation, ties, legal_by_tile, risk_seed,
                    "match context unavailable")

            try:
                estimates = estimate_tenpai_wait_loss_scores(
                    observation, candidates, samples=self.template_samples,
                    seed=risk_seed)
            except RuntimeError:
                return self._v06_risk_fallback(
                    observation, ties, legal_by_tile, risk_seed,
                    "loss templates unavailable")

            by_tile = {item.tile: item for item in estimates}
            if any(not by_tile[tile].complete for tile in candidates):
                return self._v06_risk_fallback(
                    observation, ties, legal_by_tile, risk_seed,
                    "ordinary score evidence incomplete")

            choice = min(
                ties,
                key=lambda item: self._loss_sort_key(
                    item, by_tile[item.discard]),
            )
            loss = by_tile[choice.discard]
            alternatives = ",".join(
                f"{tile}:loss={by_tile[tile].loss_index:.3f}"
                f"/risk={by_tile[tile].risk_score:.3f}"
                for tile in candidates)
            return AgentDecision(
                legal_by_tile[choice.discard],
                f"DISCARD {choice.discard}: {self._policy_label()} "
                f"(exact offense tie: shanten={choice.shanten}, "
                f"live={choice.total_live_copies}, "
                f"types={len(choice.effective_tiles)}; "
                f"conditional_loss_index={loss.loss_index:.3f}, "
                f"mean_loss_if_hit={loss.mean_loss_if_hit:.3f}, "
                f"templates={loss.templates_used}; candidates=[{alternatives}]); "
                f"loss_index is tenpai-conditioned relative score exposure, not absolute EV",
            )

        passes = [a for a in actions if a.type.value == "PASS"]
        if passes:
            return AgentDecision(
                passes[0], "PASS: preserve the current hand over optional melds")
        return AgentDecision(
            actions[0], f"{actions[0].type.value}: take the required legal action")


class TenpaiRiskLossTieBreakAgent(TenpaiLossTieBreakAgent):
    """Experimental V0.7b: V0.6 risk first, loss severity second.

    This is a strict refinement of the promoted V0.6 tie-break: shanten/live
    offense remains unchanged, and among exact offense ties a lower relative
    tenpai-wait risk always wins. Confirmed conditional loss is consulted only
    when the V0.6 risk score itself is tied.
    """

    def _policy_label(self):
        return "tenpai_risk_loss_tiebreak_v0.7b"

    def _loss_sort_key(self, item, estimate):
        return (
            estimate.risk_score,
            estimate.loss_index,
            self._tile_order(item.discard),
        )


class TwoPlyShantenRiskAgent(TenpaiRiskTieBreakAgent):
    """Experimental V0.8: deterministic two-ply offense before V0.6 risk.

    The policy cannot leave V0.3's exact offense-tie frontier. Inside that
    frontier it compares the next-draw / next-best-discard ordinary state using
    only own hand and public tile counts. If multiple candidates remain tied on
    the two-ply metrics, the promoted V0.6 32-template relative risk is the
    final tie-break.

    This remains ordinary-hand lookahead, not score EV and not a special-win
    model.
    """

    @staticmethod
    def _two_ply_key(estimate):
        return (
            estimate.weighted_post_shanten,
            -estimate.terminal_win_copies,
            -estimate.weighted_post_live_copies,
            -estimate.weighted_post_effective_types,
        )

    def choose_decision(self, observation, legal_actions):
        if not legal_actions:
            raise ValueError("No legal actions")
        actions = sorted(legal_actions, key=self._key)
        wins = [a for a in actions if a.type.value in ("HU", "ROB_KONG_HU")]
        if wins:
            return AgentDecision(
                wins[0], f"{wins[0].type.value}: take the legal ordinary-shape win")

        discards = [a for a in actions if a.type.value == "DISCARD"]
        if discards:
            open_melds = len(observation.melds[observation.seat])
            legal_by_tile = {action.tile: action for action in discards}
            public_tiles = self._public_tiles(observation)
            ties = best_offense_ties(
                observation.hand,
                gold_tile=observation.gold_tile,
                open_melds=open_melds,
                visible_tiles=public_tiles,
                allowed_discards=tuple(legal_by_tile),
            )
            # Advance the stochastic stream at the same decision point as V0.6
            # so paired comparisons keep identity-stable risk seeds aligned.
            risk_seed = self._next_risk_seed()
            if len(ties) == 1:
                choice = ties[0]
                return AgentDecision(
                    legal_by_tile[choice.discard],
                    f"DISCARD {choice.discard}: two_ply_shanten_risk_v0.8 "
                    f"(no exact offense tie; preserve V0.6/V0.3 choice)",
                )

            candidates = tuple(item.discard for item in ties)
            if observation.gold_tile in candidates:
                choice = ties[0]
                return AgentDecision(
                    legal_by_tile[choice.discard],
                    f"DISCARD {choice.discard}: two_ply_shanten_risk_v0.8 "
                    f"(exact offense tie includes gold; preserve V0.3 tile-order "
                    f"choice because special/gold EV is outside ordinary lookahead)",
                )

            estimates = analyze_two_ply_offense(
                observation.hand,
                candidates,
                gold_tile=observation.gold_tile,
                open_melds=open_melds,
                visible_tiles=public_tiles,
            )
            by_tile = {item.discard: item for item in estimates}
            best_key = min(self._two_ply_key(by_tile[tile]) for tile in candidates)
            finalists = tuple(
                item for item in ties
                if self._two_ply_key(by_tile[item.discard]) == best_key
            )

            if len(finalists) == 1:
                choice = finalists[0]
                look = by_tile[choice.discard]
                alternatives = ",".join(
                    f"{tile}:s={by_tile[tile].expected_post_shanten:.3f}"
                    f"/live={by_tile[tile].expected_post_live_copies:.2f}"
                    f"/types={by_tile[tile].expected_post_effective_types:.2f}"
                    for tile in candidates
                )
                return AgentDecision(
                    legal_by_tile[choice.discard],
                    f"DISCARD {choice.discard}: two_ply_shanten_risk_v0.8 "
                    f"(exact V0.3 offense tie resolved by deterministic two-ply "
                    f"ordinary offense; candidates=[{alternatives}]); "
                    f"no opponent concealed tiles or future wall order used",
                )

            risk_candidates = tuple(item.discard for item in finalists)
            try:
                risk_estimates = estimate_tenpai_wait_risk_scores(
                    observation, risk_candidates,
                    samples=self.template_samples, seed=risk_seed)
            except RuntimeError:
                choice = min(
                    finalists,
                    key=lambda item: self._tile_order(item.discard),
                )
                return AgentDecision(
                    legal_by_tile[choice.discard],
                    f"DISCARD {choice.discard}: two_ply_shanten_risk_v0.8 "
                    f"(two-ply tie; V0.6 risk templates unavailable; "
                    f"preserve canonical tile order within two-ply finalists)",
                )

            risk_by_tile = {item.tile: item for item in risk_estimates}
            choice = min(
                finalists,
                key=lambda item: (
                    risk_by_tile[item.discard].risk_score,
                    self._tile_order(item.discard),
                ),
            )
            risk = risk_by_tile[choice.discard]
            return AgentDecision(
                legal_by_tile[choice.discard],
                f"DISCARD {choice.discard}: two_ply_shanten_risk_v0.8 "
                f"(two-ply offense still tied; V0.6 relative_risk="
                f"{risk.risk_score:.3f}, templates={risk.templates_used}); "
                f"risk_score is relative tenpai-wait ranking, not a probability",
            )

        passes = [a for a in actions if a.type.value == "PASS"]
        if passes:
            return AgentDecision(
                passes[0], "PASS: preserve the current hand over optional melds")
        return AgentDecision(
            actions[0], f"{actions[0].type.value}: take the required legal action")
