from dataclasses import dataclass, field
import random
from huian._legacy import env
from huian.environment import HuianEnvironment

def make_wall(seed=None):
    wall = env.full_wall()
    random.Random(seed).shuffle(wall)
    return wall

class RandomAgent:
    def choose_action(self, state, legal_actions):
        if not legal_actions:
            raise ValueError("No legal actions")
        return random.choice(list(legal_actions))

@dataclass
class SimulationResult:
    seed: int | None
    status: str
    events: list[dict] = field(default_factory=list)
    unresolved: tuple[str, ...] = ()

class Simulator:
    def __init__(self, environment_factory=HuianEnvironment):
        self.environment_factory = environment_factory

    def run(self, seed=None, agent=None, max_steps=100):
        game = self.environment_factory(max_steps=max_steps)
        game.reset(wall=make_wall(seed))
        try:
            game.legal_actions()
        except Exception as exc:
            return SimulationResult(seed, "UNRESOLVED", game.events,
                                    tuple(getattr(exc, "rule_ids", (str(exc),))))
        return SimulationResult(seed, "READY", game.events)
