"""Deterministic simulator scaffolding with evidence-safe stopping.

The simulator may drive only phases whose complete legal action set is known.
Unknown Huian rules yield a replayable result rather than a guessed action.
"""
from dataclasses import dataclass, field
import random

from huian._legacy import env
from huian.environment import HuianEnvironment


def make_wall(seed=None):
    wall = env.full_wall()
    random.Random(seed).shuffle(wall)
    return wall


class RandomAgent:
    def __init__(self, seed=None):
        self._random = random.Random(seed)

    def choose_action(self, state, legal_actions):
        if not legal_actions:
            raise ValueError("No legal actions")
        return self._random.choice(list(legal_actions))


@dataclass(frozen=True)
class SimulationResult:
    seed: int | None
    status: str
    events: tuple[dict, ...] = ()
    unresolved: tuple[str, ...] = ()
    dice_total: int | None = None
    phase: str | None = None
    state_hash: str | None = None
    wall_remaining: int | None = None


class Simulator:
    def __init__(self, environment_factory=HuianEnvironment):
        self.environment_factory = environment_factory

    @staticmethod
    def _dice_total(seed):
        dice = random.Random(seed)
        return dice.randint(1, 6) + dice.randint(1, 6)

    @staticmethod
    def _result(game, *, seed, status, dice_total=None, unresolved=()):
        state = game.state
        return SimulationResult(seed, status, tuple(game.events), tuple(unresolved),
                                dice_total, state.phase, state.state_hash(),
                                state.wall_remaining())

    def run(self, seed=None, agent=None, max_steps=100):
        """Preserve the legacy READY-only simulator entry point."""
        game = self.environment_factory(max_steps=max_steps)
        game.reset(wall=make_wall(seed))
        try:
            game.legal_actions()
        except Exception as exc:
            return self._result(game, seed=seed, status="UNRESOLVED",
                                unresolved=getattr(exc, "rule_ids", (str(exc),)))
        return self._result(game, seed=seed, status="READY")

    def run_opening(self, seed=None, dice_total=None, max_steps=100):
        """Replay dealing, flower replacement and opening gold to a safe stop."""
        if dice_total is None:
            dice_total = self._dice_total(seed)
        game = self.environment_factory(max_steps=max_steps)
        game.reset(wall=make_wall(seed))
        try:
            game.begin_opening(dice_total)
            game.legal_actions()
        except Exception as exc:
            return self._result(game, seed=seed, status="STOPPED_UNKNOWN",
                                dice_total=dice_total,
                                unresolved=getattr(exc, "rule_ids", (str(exc),)))
        return self._result(game, seed=seed, status="READY", dice_total=dice_total)