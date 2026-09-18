"""Explainable ordinary-hand heuristics, independent of legality and scoring."""
from dataclasses import dataclass
from collections import Counter
from typing import Any

from huian._legacy import env


@dataclass(frozen=True)
class AgentDecision:
    action: Any
    reason: str


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

    @classmethod
    def from_state(cls, state):
        """Never expose the opponent hand, wall order, or reserved tiles."""
        seat = state.current_player
        return cls(
            seat, tuple(state.hands[seat]), state.gold_tile, state.phase,
            state.dealer, state.wall_remaining(),
            tuple(tuple(river) for river in state.discards),
            tuple(tuple(flowers) for flowers in state.flowers),
            tuple(tuple((meld.kind, tuple(meld.tiles)) for meld in melds)
                  for melds in state.melds),
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
