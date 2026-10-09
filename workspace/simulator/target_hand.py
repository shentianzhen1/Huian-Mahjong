"""Target-room hand simulation using confirmed staged opening and rule windows.

This runner is deliberately separate from the historical ordinary benchmark.
It uses the real target-room state machine, including staged flower replacement,
player-confirmed system-random Gold selection over nonflower tiles, Tianhu,
Sanjindao, Eight-Flower and first-round Qiangjin. Unknown contracts still fail
closed instead of being replaced with simulator guesses.
"""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json

from huian.environment import DeadLoopError, HuianEnvironment
from huian.rules import UnknownRuleError
from huian.rules.adapter import HuianRulesAdapter
from huian.rules.config import RulesConfig
from huian.rules.engine import HuianRules
from workspace.ai import AgentDecision, MatchObservationContext, PlayerObservation

from .core import RandomAgent, Simulator, SimulatorConfig, make_wall
from .tianting_routing import snapshot_tianting
from .staged_opening import (
    OPEN_GOLD_RANDOM_EVIDENCE_ID,
    simulator_random_gold_candidate,
)
from .unknowns import build_unknown_evidence


def run_target_hand(
        seed=None, agent=None, max_steps=1000, *, simulator=None, agents=None,
        wall=None, dealer=0, current_dealer_base=10, match_context=None,
        decision_observer=None, gold_random_seed=None):
    """Run one hand through the confirmed target-room rule path.

    The Gold choice is a seeded *simulator convention* over the confirmed
    nonflower candidate pool. It is never evidence about the server's unknown
    RNG distribution and is never used to predict a live room.

    Unlike ``Simulator.run_normal_hand``, this function does not set
    ``simulation_only_normal_hand=True`` and therefore does not bypass special
    declaration windows. It stops with ``STOPPED_UNKNOWN`` whenever a later
    rule contract is still unresolved.
    """
    if type(max_steps) is not int or max_steps <= 0:
        raise ValueError("max_steps must be a positive integer")
    if type(dealer) is not int or dealer not in (0, 1):
        raise ValueError("dealer must be seat 0 or 1")
    if type(current_dealer_base) is not int or current_dealer_base < 0:
        raise ValueError("current_dealer_base must be a nonnegative integer")
    if agent is not None and agents is not None:
        raise ValueError("Use agent or two seat agents, not both")
    if agents is not None and len(agents) != 2:
        raise ValueError("Exactly two seat agents are required")
    if match_context is not None and not isinstance(match_context, MatchObservationContext):
        raise TypeError("match_context must be MatchObservationContext or None")
    if decision_observer is not None and not callable(decision_observer):
        raise TypeError("decision_observer must be callable or None")

    simulator = Simulator() if simulator is None else simulator
    if not isinstance(simulator, Simulator):
        raise TypeError("simulator must be Simulator or None")
    profile = simulator.config if simulator.config is not None else SimulatorConfig()
    if profile.enable_rob_kong:
        raise ValueError(
            "enable_rob_kong requests unsupported broad rob-kong scopes; "
            "target-room added-kong robbery is already handled separately"
        )

    rules = HuianRulesAdapter(HuianRules(RulesConfig(
        enable_added_kong=profile.enable_added_kong,
    )))
    game = simulator.environment_factory(rules=rules, max_steps=max_steps + 8)
    tiles = make_wall(seed) if wall is None else list(wall)
    game.reset(wall=tiles, dealer=dealer)
    initial_hash = game.state.state_hash()
    wall_hash = hashlib.sha256(json.dumps(tiles).encode()).hexdigest()
    selector_seed = seed if gold_random_seed is None else gold_random_seed
    seats = tuple(agents) if agents is not None else (
        (agent, agent) if agent is not None
        else (RandomAgent(seed), RandomAgent(None if seed is None else seed + 1))
    )
    decisions = []
    steps = 0
    opening_selection = {}

    def finish(status, unresolved=(), stop_reason=None):
        evidence = (
            build_unknown_evidence(game, unresolved)
            if unresolved else None
        )
        if evidence is not None:
            evidence["simulation"] = {
                "seed": seed,
                "steps": steps,
                "initial_state_hash": initial_hash,
                "wall_hash": wall_hash,
                "stop_reason": stop_reason,
                "opening_mode": "STAGED_SYSTEM_RANDOM_NONFLOWER",
                "gold_random_seed": selector_seed,
            }
        config = {
            "mode": "TARGET_ROOM_STAGED",
            "opening_mode": "STAGED_SYSTEM_RANDOM_NONFLOWER",
            "selection_evidence_id": OPEN_GOLD_RANDOM_EVIDENCE_ID,
            "target_selection": "SYSTEM_RANDOM",
            "target_candidate_pool": "NONFLOWER_TILES_ONLY",
            "target_distribution": "UNKNOWN",
            "simulator_sampling": "SEEDED_UNIFORM_NONFLOWER",
            "simulator_sampling_status": "SIMULATOR_CONVENTION_ONLY",
            "gold_random_seed": selector_seed,
            "current_dealer_base": current_dealer_base,
            "tianting": snapshot_tianting(getattr(game.state, "first_round", None)),
            "legacy_profile": asdict(profile),
            **opening_selection,
        }
        return Simulator._result(
            game,
            seed=seed,
            status=status,
            dice_total=None,
            unresolved=unresolved,
            decisions=decisions,
            steps=steps,
            stop_reason=stop_reason,
            simulation_only=True,
            real_scoring=True,
            config=config,
            initial_state_hash=initial_hash,
            wall_hash=wall_hash,
            unknown_evidence=evidence,
        )

    def choose_and_step(state, actions):
        nonlocal steps
        actor = seats[state.current_player]
        observation = PlayerObservation.from_state(
            state, match_context=match_context
        )
        if decision_observer is not None:
            decision_observer(
                deepcopy(state), observation, deepcopy(actions)
            )
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
        if action not in actions:
            raise ValueError("Agent selected an illegal action")
        _, event = game.step(action)
        steps += 1
        decisions.append({
            "seq": event["seq"],
            "decision": {"agent": type(actor).__name__, "reason": reason},
        })

    try:
        game.begin_confirmed_opening()
        while True:
            if game.is_terminal():
                return finish("COMPLETED")
            state = game.state

            if state.phase == "OPENING_GOLD_PENDING":
                wall_index, selected_tile, candidate_pool_size = (
                    simulator_random_gold_candidate(
                        state.wall, seed=selector_seed
                    )
                )
                opening_selection.update({
                    "candidate_pool_size": candidate_pool_size,
                    "selected_wall_index": wall_index,
                    "selected_tile": selected_tile,
                })
                game.reveal_opening_candidate(
                    wall_index=wall_index,
                    current_dealer_base=current_dealer_base,
                )
                continue

            if state.phase == "SANJINDAO_DECLARED":
                game.finalize_sanjindao_outcome(
                    current_dealer_base=current_dealer_base
                )
                continue
            if state.phase in (
                    "EIGHT_FLOWER_YOU_DECLARED",
                    "OPENING_EIGHT_FLOWER_DECLARED"):
                game.finalize_eight_flower_outcome(
                    current_dealer_base=current_dealer_base
                )
                continue
            if state.phase == "YOUJIN_SETTLEMENT_READY":
                return finish(
                    "STOPPED_UNKNOWN",
                    ("settlement.youjin_full",),
                    "youjin_full_settlement_unresolved",
                )
            if state.phase in ("HU_DECLARED", "ROB_KONG_HU_DECLARED"):
                game.finalize_ordinary_outcome(
                    current_dealer_base=current_dealer_base
                )
                continue
            if state.phase == "QIANGJIN_DECLARED":
                # The confirmed first-round Qiangjin path settles immediately.
                # Reaching this legacy declaration phase would therefore be a
                # runtime/provenance mismatch, not a newly invented rule gap.
                return finish(
                    "STOPPED_UNKNOWN",
                    stop_reason="legacy_qiangjin_declaration_without_first_round_provenance",
                )

            if steps >= max_steps:
                return finish("MAX_STEPS", stop_reason="max_steps")
            actions = game.legal_actions()
            if not actions:
                return finish(
                    "STOPPED_UNKNOWN",
                    ("environment_phase",),
                    "no_legal_actions",
                )
            choose_and_step(state, actions)
    except UnknownRuleError as exc:
        return finish("STOPPED_UNKNOWN", exc.rule_ids, "unresolved_rule")
    except DeadLoopError as exc:
        return finish("STOPPED_LOOP", stop_reason=str(exc))
