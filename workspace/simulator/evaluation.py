"""Reproducible, seat-aware summaries; censored hands are never scored as draws."""
from collections import Counter
from dataclasses import asdict, dataclass

from .core import RandomAgent, Simulator
from .pairing import PairedSummary, summarize_swapped_pairs


@dataclass(frozen=True)
class HandSummary:
    seed: int
    swapped: bool
    agents: tuple[str, str]
    status: str
    winner: int | None
    win_source: str | None
    terminal_reason: str | None
    rewards: tuple[int, int]
    steps: int
    unresolved: tuple[str, ...]
    stop_reason: str | None
    state_hash: str | None
    wall_hash: str | None
    initial_state_hash: str | None
    pair_index: int = 0


def make_hand_summary(result, *, seed, swapped, agent_names, pair_index=0):
    return HandSummary(
        seed, swapped, tuple(agent_names), result.status, result.winner,
        result.win_source, result.terminal_reason, result.rewards, result.steps,
        result.unresolved, result.stop_reason, result.state_hash, result.wall_hash,
        result.initial_state_hash, pair_index,
    )


@dataclass(frozen=True)
class BatchEvaluation:
    total: int
    completed: int
    wins: tuple[int, int]
    losses: tuple[int, int]
    draws: int
    self_draws: int
    discard_wins: int
    unknown: int
    max_steps: int
    stopped_loops: int
    average_reward: tuple[float, float]
    reward_samples: int
    unknown_reasons: dict[str, int]
    by_agent: dict
    per_seed: tuple[HandSummary, ...]
    simulation_only: bool = True
    paired: PairedSummary | None = None

    def to_dict(self):
        return asdict(self)


def run_many_normal_hands(seeds=range(20), *, simulator=None, agent_factories=None,
                          max_steps=1000, swap_seats=False, dealer=0, on_hand=None):
    """Fresh agents each run; swapped pairs reuse wall, dice and agent RNG seeds.

    Average rewards use COMPLETED hands only. UNKNOWN/MAX_STEPS/STOPPED_LOOP
    are censored observations, excluded from wins/losses/draws and rewards.
    by_agent keys identify factories (A/B), even if both classes are identical.
    on_hand(summary, result) observes each finished attempt before the next.
    """
    seeds = tuple(seeds)
    if not seeds or any(type(seed) is not int for seed in seeds):
        raise ValueError("seeds must be a nonempty iterable of integers")
    if type(swap_seats) is not bool:
        raise ValueError("swap_seats must be boolean")
    if type(max_steps) is not int or max_steps <= 0:
        raise ValueError("max_steps must be a positive integer")
    if type(dealer) is not int or dealer not in (0, 1):
        raise ValueError("dealer must be seat 0 or 1")
    if on_hand is not None and not callable(on_hand):
        raise ValueError("on_hand must be callable")
    factories = tuple(agent_factories) if agent_factories is not None else (
        RandomAgent, RandomAgent)
    if len(factories) != 2 or not all(callable(f) for f in factories):
        raise ValueError("Two callable agent factories are required")
    simulator = simulator if simulator is not None else Simulator()
    summaries = []
    by_agent = {
        name: {"name": None, "hands": 0, "completed": 0, "wins": 0, "losses": 0,
               "draws": 0, "unknown": 0, "max_steps": 0, "stopped_loops": 0,
               "reward_sum": 0, "average_reward": 0.0}
        for name in ("A", "B")
    }
    wins = [0, 0]
    reward_sums = [0, 0]
    completed = draws = self_draws = discard_wins = unknown = limited = loops = 0
    reasons = Counter()
    for pair_index, seed in enumerate(seeds):
        for swapped in ((False, True) if swap_seats else (False,)):
            identities = (1, 0) if swapped else (0, 1)
            identity_agents = [factory(seed=seed * 2 + i)
                               for i, factory in enumerate(factories)]
            agents = tuple(identity_agents[i] for i in identities)
            result = simulator.run_normal_hand(
                seed=seed, agents=agents, max_steps=max_steps, dealer=dealer)
            if result.status not in ("COMPLETED", "STOPPED_UNKNOWN", "MAX_STEPS", "STOPPED_LOOP"):
                raise ValueError(f"Unsupported evaluation status: {result.status}")
            if sum(result.rewards) != 0:
                raise ValueError("Evaluation requires zero-sum rewards")
            if result.status == "COMPLETED":
                completed += 1
                if result.winner is None:
                    if result.terminal_reason != "WALL_16" or result.rewards != (0, 0):
                        raise ValueError("Unrecognized terminal draw")
                    draws += 1
                else:
                    if result.winner not in (0, 1):
                        raise ValueError("Invalid winner")
                    wins[result.winner] += 1
                    if result.win_source == "self_draw":
                        self_draws += 1
                    elif result.win_source == "discard":
                        discard_wins += 1
                    else:
                        raise ValueError("Unsupported normal-hand win source")
                for seat in (0, 1):
                    reward_sums[seat] += result.rewards[seat]
            elif result.status == "STOPPED_UNKNOWN":
                unknown += 1
                reasons.update(set(result.unresolved))
            elif result.status == "MAX_STEPS":
                limited += 1
            else:
                loops += 1
            for seat, identity in enumerate(identities):
                item = by_agent[("A", "B")[identity]]
                item["name"] = type(agents[seat]).__name__
                item["hands"] += 1
                if result.status == "COMPLETED":
                    item["completed"] += 1
                    item["reward_sum"] += result.rewards[seat]
                    if result.winner is None:
                        item["draws"] += 1
                    else:
                        item["wins" if result.winner == seat else "losses"] += 1
                else:
                    key = {"STOPPED_UNKNOWN": "unknown", "MAX_STEPS": "max_steps",
                           "STOPPED_LOOP": "stopped_loops"}[result.status]
                    item[key] += 1
            summary = make_hand_summary(
                result, seed=seed, swapped=swapped, pair_index=pair_index,
                agent_names=tuple(type(agent).__name__ for agent in agents))
            summaries.append(summary)
            if on_hand is not None:
                on_hand(summary, result)
    for item in by_agent.values():
        item["average_reward"] = (item["reward_sum"] / item["completed"]
                                  if item["completed"] else 0.0)
    return BatchEvaluation(
        len(summaries), completed, tuple(wins), (wins[1], wins[0]),
        draws, self_draws, discard_wins, unknown, limited, loops,
        tuple(value / completed if completed else 0.0 for value in reward_sums),
        completed, dict(sorted(reasons.items())), by_agent, tuple(summaries),
        paired=summarize_swapped_pairs(summaries) if swap_seats else None,
    )
