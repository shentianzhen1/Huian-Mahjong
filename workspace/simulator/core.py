"""Deterministic ordinary-hand simulation, with explicit UNKNOWN exits."""
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
import random

from huian._legacy import env
from huian.environment import DeadLoopError, HuianEnvironment
from huian.rules import UnknownRuleError
from huian.rules.adapter import HuianRulesAdapter
from huian.rules.engine import HuianRules
from huian.rules.config import RulesConfig
from workspace.ai import AgentDecision, PlayerObservation


def make_wall(seed=None):
    wall = env.full_wall()
    random.Random(seed).shuffle(wall)
    return wall


class RandomAgent:
    def __init__(self, seed=None):
        self._random = random.Random(seed)

    def choose_action(self, state, legal_actions):
        """Legacy action-only API; choose_decision adds a reason for simulation."""
        if not legal_actions:
            raise ValueError("No legal actions")
        return self._random.choice(list(legal_actions))

    def choose_decision(self, observation, legal_actions):
        action = self.choose_action(observation, legal_actions)
        return AgentDecision(action, "Seeded uniform choice among legal actions")


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
    winner: int | None = None
    win_source: str | None = None
    terminal_reason: str | None = None
    steps: int = 0
    stop_reason: str | None = None
    simulation_only: bool = False
    config: dict | None = None
    initial_state_hash: str | None = None
    wall_hash: str | None = None


@dataclass(frozen=True)
class SimulatorConfig:
    normal_hand_mode: bool = True
    enable_qiangjin: bool = False
    enable_sanjindao: bool = False
    enable_youjin: bool = False  # Includes Double-You / Triple-You.
    enable_eight_flower_you: bool = False
    # Broad rob-kong scopes (concealed/exposed) are still unsupported.
    # The added-kong-only response window is part of enable_added_kong.
    enable_rob_kong: bool = False
    enable_added_kong: bool = True
    enable_real_scoring: bool = False

    def __post_init__(self):
        for name, value in asdict(self).items():
            if type(value) is not bool:
                raise ValueError(f"{name} must be boolean")

    def unsupported_rules(self):
        return tuple(name.removeprefix("enable_")
                     for name, value in asdict(self).items()
                     if name.startswith("enable_") and name != "enable_added_kong" and value)


class Simulator:
    def __init__(self, environment_factory=HuianEnvironment, config=None):
        if config is not None and not isinstance(config, SimulatorConfig):
            raise TypeError("config must be SimulatorConfig")
        self.environment_factory = environment_factory
        self.config = config

    @staticmethod
    def _dice_total(seed):
        dice = random.Random(seed)
        return dice.randint(1, 6) + dice.randint(1, 6)

    @staticmethod
    def _result(game, *, seed, status, dice_total=None, unresolved=(),
                decisions=(), **extra):
        state = game.state
        events = game.events
        for item in decisions:
            events[item["seq"]]["decision"] = deepcopy(item["decision"])
        declaration = next((
            event["action"]["metadata"]["hu_declaration"]
            for event in reversed(events)
            if event["action"]["type"] == "END_HAND"
            and "hu_declaration" in event["action"].get("metadata", {})
        ), None) or state.pending_hu
        return SimulationResult(
            seed=seed, status=status, events=tuple(events),
            unresolved=tuple(unresolved), dice_total=dice_total,
            phase=state.phase, state_hash=state.state_hash(),
            wall_remaining=state.wall_remaining(), rewards=tuple(state.rewards),
            winner=declaration["winner"] if declaration else None,
            win_source=declaration["source"] if declaration else None,
            terminal_reason=state.terminal_reason, **extra,
        )

    def run(self, seed=None, agent=None, max_steps=100):
        """Keep historical safe stop unless normal mode is explicitly configured."""
        if self.config is not None and self.config.normal_hand_mode:
            return self.run_normal_hand(seed=seed, agent=agent, max_steps=max_steps)
        game = self.environment_factory(max_steps=max_steps)
        game.reset(wall=make_wall(seed))
        try:
            game.legal_actions()
        except UnknownRuleError as exc:
            return self._result(game, seed=seed, status="UNRESOLVED",
                                unresolved=exc.rule_ids)
        return self._result(game, seed=seed, status="READY")

    def run_opening(self, seed=None, dice_total=None, max_steps=100):
        """Preserve the evidence-safe opening path and its Qiangjin stop."""
        if dice_total is None:
            dice_total = self._dice_total(seed)
        game = self.environment_factory(max_steps=max_steps)
        game.reset(wall=make_wall(seed))
        try:
            game.begin_opening(dice_total)
            game.legal_actions()
        except UnknownRuleError as exc:
            return self._result(game, seed=seed, status="STOPPED_UNKNOWN",
                                dice_total=dice_total, unresolved=exc.rule_ids)
        return self._result(game, seed=seed, status="READY", dice_total=dice_total)

    @staticmethod
    def _special_rules(state):
        """Observable out-of-scope situations; never infer Youjin from shape."""
        if state.terminal:
            return ()
        unknown = []
        if state.special_states != ["NORMAL", "NORMAL"]:
            unknown.append("youjin_permissions")
        if any(len(flowers) == 8 for flowers in state.flowers):
            unknown.append("eight_flowers_special_win")
        return tuple(unknown)

    def run_normal_hand(self, seed=None, agent=None, dice_total=None, max_steps=1000,
                        *, agents=None, wall=None, initial_state=None, dealer=0):
        """Run ordinary play with unit rewards, never real fan aggregation.

        wall is a complete 144-tile opening wall. initial_state is a validated
        mid-hand fixture with its wall and reserved tiles explicitly accounted.
        Agents receive only their own hand plus public information.
        """
        if type(max_steps) is not int or max_steps <= 0:
            raise ValueError("max_steps must be a positive integer")
        if type(dealer) is not int or dealer not in (0, 1):
            raise ValueError("dealer must be seat 0 or 1")
        if wall is not None and initial_state is not None:
            raise ValueError("Use wall or initial_state, not both")
        if initial_state is not None and initial_state.terminal:
            raise ValueError("initial_state must be an active mid-hand fixture")
        if agent is not None and agents is not None:
            raise ValueError("Use agent or two seat agents, not both")
        if agents is not None and len(agents) != 2:
            raise ValueError("Exactly two seat agents are required")
        profile = self.config if self.config is not None else SimulatorConfig()
        if not profile.normal_hand_mode:
            raise ValueError("run_normal_hand requires normal_hand_mode")
        rules = HuianRulesAdapter(HuianRules(RulesConfig(
            simulation_only_normal_hand=True, enable_added_kong=profile.enable_added_kong)))
        # Environment also limits events. Two setup events are not agent steps.
        game = self.environment_factory(rules=rules, max_steps=max_steps + 2)
        if initial_state is None:
            tiles = make_wall(seed) if wall is None else list(wall)
            game.reset(wall=tiles, dealer=dealer)
        else:
            game.set_state(initial_state)
            tiles = list(initial_state.wall)
        initial_hash = game.state.state_hash()
        wall_hash = hashlib.sha256(json.dumps(tiles).encode()).hexdigest()
        if dice_total is None and initial_state is None:
            dice_total = self._dice_total(seed)
        seats = tuple(agents) if agents is not None else (
            (agent, agent) if agent is not None
            else (RandomAgent(seed), RandomAgent(None if seed is None else seed + 1))
        )
        decisions = []
        steps = 0

        def finish(status, unresolved=(), stop_reason=None):
            return self._result(
                game, seed=seed, status=status, dice_total=dice_total,
                unresolved=unresolved, decisions=decisions, steps=steps,
                stop_reason=stop_reason, simulation_only=True,
                config=asdict(profile), initial_state_hash=initial_hash,
                wall_hash=wall_hash,
            )

        unsupported = profile.unsupported_rules()
        if unsupported:
            return finish("STOPPED_UNKNOWN", unsupported, "unsupported_config")
        try:
            if initial_state is None:
                game.begin_normal_hand(dice_total)
            while True:
                if game.is_terminal():
                    return finish("COMPLETED")
                state = game.state
                if state.phase == "ROB_KONG_HU_DECLARED":
                    return finish("STOPPED_UNKNOWN", ("ROB_KONG_SCORING_UNKNOWN",),
                                  "unresolved_rule")
                if (state.phase == "HU_DECLARED"
                        and state.pending_hu["source"] == "kong_tail_draw"):
                    return finish("STOPPED_UNKNOWN", ("GANG_HU_SCORING_UNKNOWN",),
                                  "unresolved_rule")
                unknown = self._special_rules(state)
                if unknown:
                    return finish("STOPPED_UNKNOWN", unknown, "special_rule_encountered")
                if state.phase == "HU_DECLARED":
                    # Settlement is part of the declaring action, even on last step.
                    game.finalize_simulation_only_outcome()
                    continue
                if (any(meld.kind == "ADDED_GANG" for zone in state.melds for meld in zone)
                        and game.rules.rules.is_wall_draw(state)):
                    report = game.action_report()
                    if "KONG_FEE_SETTLEMENT_UNKNOWN" in report.unresolved:
                        return finish("STOPPED_UNKNOWN", report.unresolved,
                                      "unresolved_rule")
                if steps >= max_steps:
                    return finish("MAX_STEPS", stop_reason="max_steps")
                actions = game.legal_actions()
                if not actions:
                    return finish("STOPPED_UNKNOWN", ("environment_phase",),
                                  "no_legal_actions")
                actor = seats[state.current_player]
                observation = PlayerObservation.from_state(state)
                chooser = getattr(actor, "choose_decision", None)
                if chooser is None:
                    chooser = actor.choose_action
                choice = chooser(observation, deepcopy(actions))
                if isinstance(choice, AgentDecision):
                    action, reason = choice.action, choice.reason
                else:
                    action = choice
                    reason = f"{type(actor).__name__} selected a legal action"
                if not isinstance(reason, str) or not reason.strip():
                    raise ValueError("Agent decisions require a nonempty reason")
                # Never allow reason text or mutated metadata to bypass legality.
                if action not in actions:
                    raise ValueError("Agent selected an illegal action")
                _, event = game.step(action)
                steps += 1
                decisions.append({
                    "seq": event["seq"],
                    "decision": {"agent": type(actor).__name__, "reason": reason},
                })
        except UnknownRuleError as exc:
            return finish("STOPPED_UNKNOWN", exc.rule_ids, "unresolved_rule")
        except DeadLoopError as exc:
            return finish("STOPPED_LOOP", stop_reason=str(exc))

    def run_many_normal_hands(self, seeds=range(20), *, agent_factories=None,
                              max_steps=1000, swap_seats=False, dealer=0, on_hand=None):
        from .evaluation import run_many_normal_hands
        return run_many_normal_hands(
            seeds, simulator=self, agent_factories=agent_factories,
            max_steps=max_steps, swap_seats=swap_seats, dealer=dealer, on_hand=on_hand,
        )

    def benchmark_normal_hands(self, count=100, *, seed_offset=0, max_steps=1000):
        """Historical raw-result benchmark; prefer run_many for compact summaries."""
        if type(count) is not int or count <= 0:
            raise ValueError("count must be a positive integer")
        return tuple(self.run_normal_hand(seed=seed_offset + seed, max_steps=max_steps)
                     for seed in range(count))
