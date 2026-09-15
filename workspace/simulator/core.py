"""Deterministic simulator scaffolding with evidence-safe stopping.

The simulator may drive only phases whose complete legal action set is known.
Unknown Huian rules yield a replayable result rather than a guessed action.
"""
from dataclasses import dataclass, field
import random

from huian._legacy import env
from huian.environment import HuianEnvironment
from huian.rules import UnknownRuleError
from huian.rules.adapter import HuianRulesAdapter
from huian.rules.engine import HuianRules
from huian.rules.config import RulesConfig


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
    rewards: tuple[int, int] = (0, 0)

@dataclass(frozen=True)
class SimulatorConfig:
    normal_hand_mode: bool = False
    enable_qiangjin: bool = False
    enable_sanjindao: bool = False
    enable_youjin: bool = False
    enable_eight_flower_you: bool = False
    enable_rob_kong: bool = False
    enable_added_kong: bool = False


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
                                state.wall_remaining(), tuple(state.rewards))

    def run(self, seed=None, agent=None, max_steps=100):
        """Preserve the legacy READY-only simulator entry point."""
        game = self.environment_factory(max_steps=max_steps)
        game.reset(wall=make_wall(seed))
        try:
            game.legal_actions()
        except UnknownRuleError as exc:
            return self._result(game, seed=seed, status="UNRESOLVED",
                                unresolved=exc.rule_ids)
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
        except UnknownRuleError as exc:
            return self._result(game, seed=seed, status="STOPPED_UNKNOWN",
                                dice_total=dice_total,
                                unresolved=exc.rule_ids)
        return self._result(game, seed=seed, status="READY", dice_total=dice_total)

    def run_normal_hand(self, seed=None, agent=None, dice_total=None, max_steps=1000):
        """Run only ordinary draw/discard/claim/Hu logic with unit simulation rewards."""
        if dice_total is None:
            dice_total = self._dice_total(seed)
        config = RulesConfig(simulation_only_normal_hand=True)
        game = self.environment_factory(rules=HuianRulesAdapter(HuianRules(config=config)), max_steps=max_steps)
        game.reset(wall=make_wall(seed))
        game.begin_normal_hand(dice_total)
        agent = agent or RandomAgent(seed)
        try:
            for _ in range(max_steps):
                if game.is_terminal():
                    return self._result(game, seed=seed, status="COMPLETED", dice_total=dice_total)
                if game.state.phase == "HU_DECLARED":
                    game.finalize_simulation_only_outcome()
                    continue
                actions = game.legal_actions()
                game.step(agent.choose_action(game.state, actions))
        except UnknownRuleError as exc:
            return self._result(game, seed=seed, status="STOPPED_UNKNOWN", dice_total=dice_total, unresolved=exc.rule_ids)
        return self._result(game, seed=seed, status="MAX_STEPS", dice_total=dice_total)

    def benchmark_normal_hands(self, count=100, *, seed_offset=0, max_steps=1000):
        """Manual benchmark; intentionally excluded from default unit tests."""
        if type(count) is not int or count <= 0:
            raise ValueError("count must be a positive integer")
        return tuple(self.run_normal_hand(seed=seed_offset + seed, max_steps=max_steps)
                     for seed in range(count))
