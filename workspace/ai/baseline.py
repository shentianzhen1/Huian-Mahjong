"""Explainable ordinary-hand heuristics, independent of legality and scoring."""
from dataclasses import dataclass
from collections import Counter
from typing import Any


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
