"""Conditional reward statistics for complete, verified seat-swapped pairs.

Incomplete pairs are counted, never imputed as draws or zero-reward games.
Conditioning on two completed hands can still introduce selection bias.
"""
from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite
from typing import Protocol


class _HandSummary(Protocol):
    pair_index: int
    seed: int
    swapped: bool
    agents: tuple[str, str]
    status: str
    rewards: tuple[int, int]
    wall_hash: str | None
    initial_state_hash: str | None


@dataclass(frozen=True)
class PairedSummary:
    total_pairs: int
    completed_pairs: int
    incomplete_pairs: int
    only_first_completed: int
    only_swapped_completed: int
    neither_completed: int
    paired_average_reward_by_agent: dict[str, float | None]
    reward_samples: int


def summarize_swapped_pairs(per_seed: Iterable[_HandSummary]) -> PairedSummary:
    """Average identity A/B rewards only when both games in a pair completed.

    ``pair_index`` identifies an input position, so repeated seeds remain
    independent pairs. A is the original seat-0 factory, B the seat-1 factory;
    identical agent class names do not merge these identities. Each completed
    pair contributes two reward samples per identity.
    """
    pairs: dict[int, dict[bool, _HandSummary]] = {}
    statuses = {"COMPLETED", "STOPPED_UNKNOWN", "MAX_STEPS", "STOPPED_LOOP"}
    for hand in per_seed:
        if type(hand.pair_index) is not int or hand.pair_index < 0:
            raise ValueError("pair_index must be a nonnegative integer")
        if type(hand.seed) is not int or type(hand.swapped) is not bool:
            raise ValueError("Pair seeds must be integers and swapped must be boolean")
        if hand.status not in statuses:
            raise ValueError(f"Unsupported paired evaluation status: {hand.status}")
        if (len(hand.agents) != 2
                or any(not isinstance(name, str) or not name for name in hand.agents)):
            raise ValueError("Each hand must identify two agents")
        if any(not isinstance(value, str) or not value
               for value in (hand.wall_hash, hand.initial_state_hash)):
            raise ValueError("Pair comparison requires wall and initial-state hashes")
        if (len(hand.rewards) != 2
                or any(type(value) not in (int, float) or not isfinite(value)
                       for value in hand.rewards)
                or sum(hand.rewards) != 0):
            raise ValueError("Paired rewards must be finite, two-seat and zero-sum")
        pair = pairs.setdefault(hand.pair_index, {})
        if hand.swapped in pair:
            raise ValueError(f"Duplicate swapped={hand.swapped} in pair {hand.pair_index}")
        pair[hand.swapped] = hand

    completed = only_first = only_swapped = neither = 0
    sums = [0, 0]
    for pair_index in sorted(pairs):
        pair = pairs[pair_index]
        if len(pair) != 2:
            raise ValueError(f"Pair {pair_index} requires both original and swapped hands")
        first, swapped = pair[False], pair[True]
        if (first.seed != swapped.seed or first.wall_hash != swapped.wall_hash
                or first.initial_state_hash != swapped.initial_state_hash):
            raise ValueError(f"Pair {pair_index} does not share seed and initial state")
        if tuple(first.agents) != tuple(reversed(swapped.agents)):
            raise ValueError(f"Pair {pair_index} does not swap agent seats")
        first_done = first.status == "COMPLETED"
        swapped_done = swapped.status == "COMPLETED"
        if first_done and swapped_done:
            completed += 1
            sums[0] += first.rewards[0] + swapped.rewards[1]
            sums[1] += first.rewards[1] + swapped.rewards[0]
        elif first_done:
            only_first += 1
        elif swapped_done:
            only_swapped += 1
        else:
            neither += 1

    samples = 2 * completed
    return PairedSummary(
        total_pairs=len(pairs), completed_pairs=completed,
        incomplete_pairs=len(pairs) - completed,
        only_first_completed=only_first, only_swapped_completed=only_swapped,
        neither_completed=neither,
        paired_average_reward_by_agent={
            "A": sums[0] / samples if samples else None,
            "B": sums[1] / samples if samples else None,
        },
        reward_samples=samples,
    )
