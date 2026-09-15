"""Regression scenarios for confirmed added-kong transitions and unknown scores."""
from collections import Counter
from copy import deepcopy
import unittest

from huian import (HuianEnvironment, HuianGameState, HuianRules,
                   HuianRulesAdapter, RulesConfig, UnknownRuleError)
from huian._legacy import env
from workspace.ai import AgentDecision, BaselineAgent, PlayerObservation
from workspace.simulator import Simulator


KONG_TILE = "P1"
KONG_HAND = [
    "P1", "M1", "M2", "M4", "M5", "M7", "M8",
    "P4", "P5", "S1", "S2", "S4", "E", "N",
]
NON_WINNING_OPPONENT = [
    "M2", "M3", "M6", "M8", "M9", "P2", "P4", "P6",
    "P8", "S2", "S4", "S6", "S8", "E", "W", "N",
]
ROB_WAITING_HAND = [
    "M1", "M1", "M2", "M3", "M4", "M5", "M6", "M7",
    "P2", "P3", "S1", "S2", "S3", "E", "E", "E",
]
KONG_WIN_HAND = [
    "P1", "M1", "M1", "M2", "M3", "M4", "M5",
    "M6", "M7", "P4", "P5", "P6", "E", "E",
]


def added_kong_state(*, rob=False, gold_count=0, tail=("P8",),
                     multiple_melds=False, kong_hu=False, wall_count=None):
    """Account for all 144 tiles; tail is given in intended draw order."""
    state = HuianGameState(
        phase="AFTER_DRAW", gold_tile="P9", dealer=0, current_player=0,
        special_states=["NORMAL", "NORMAL"])
    state.melds[0] = [env.Meld("PENG", [KONG_TILE] * 3, 1)]
    if multiple_melds:
        state.melds[0].append(env.Meld("CHI", ["P6", "P7", "P8"], 1))
    expected = 17 - 3 * len(state.melds[0])
    state.hands[0] = list(KONG_WIN_HAND if kong_hu else KONG_HAND)[:expected]
    state.hands[1] = list(ROB_WAITING_HAND if rob else NON_WINNING_OPPONENT)
    for index in range(gold_count):
        state.hands[1][2 + index] = state.gold_tile
    # This reservation is physical fixture bookkeeping, not a gold-opening rule.
    state.reserved_tiles = [state.gold_tile]
    state.last_action = env.Action(
        0, env.ActionType.DRAW,
        metadata={"source": "wall_head", "drawn_tile": KONG_TILE}).to_dict()
    remaining = env.full_wall()
    for tile in state.physical_tiles():
        remaining.remove(tile)
    for tile in tail:
        remaining.remove(tile)
    state.wall = remaining + list(reversed(tail))
    if wall_count is not None:
        state.reserved_tiles.extend(state.wall[:-wall_count])
        state.wall = state.wall[-wall_count:]
    return state


def environment(state, **kwargs):
    rules = HuianRulesAdapter(HuianRules(RulesConfig(
        simulation_only_normal_hand=True, enable_added_kong=True)))
    instance = HuianEnvironment(rules=rules, **kwargs)
    instance.set_state(state)
    return instance


def action_of(instance, action_type):
    return next(action for action in instance.action_report().known_actions
                if action.type == action_type)


class AddedKongFixtureAgent:
    """Choose the requested branch without looking at another player's hand."""
    def __init__(self, rob=True):
        self.rob = rob

    def choose_action(self, observation, legal_actions):
        types = env.ActionType
        priority = [types.ADD_KONG]
        if self.rob:
            priority.append(types.ROB_KONG_HU)
        priority += [types.HU, types.PASS, types.DRAW]
        for kind in priority:
            for action in legal_actions:
                if action.type == kind:
                    return AgentDecision(action, "Fixed added-kong regression branch")
        raise AssertionError("Fixture reached an unexpected action phase")


class AddedKongTests(unittest.TestCase):
    def assert_conserved(self, state):
        self.assertEqual(Counter(state.physical_tiles()), Counter(env.full_wall()))
        self.assertEqual(len(state.physical_tiles()), 144)
        self.assertGreaterEqual(len(state.wall), 16)

    def assert_rejected_atomically(self, instance, action):
        state_hash, events = instance.state.state_hash(), instance.events
        with self.assertRaises((ValueError, UnknownRuleError)):
            instance.step(action)
        self.assertEqual(instance.state.state_hash(), state_hash)
        self.assertEqual(instance.events, events)

    def declare(self, instance):
        action = action_of(instance, env.ActionType.ADD_KONG)
        self.assertEqual(action.tile, KONG_TILE)
        self.assertEqual(action.tiles, (KONG_TILE,) * 4)
        self.assertEqual(action.metadata, {"meld_index": 0})
        return instance.step(action)

    def test_declaration_opens_response_without_moving_any_tile(self):
        original = added_kong_state(rob=True)
        instance = environment(original)
        state, event = self.declare(instance)
        self.assertEqual(state.phase, "ROB_KONG_WINDOW")
        self.assertEqual(state.current_player, 1)
        self.assertEqual(state.pending_kong, {
            "kong_player": 0, "tile": KONG_TILE, "meld_index": 0})
        self.assertEqual(state.hands, original.hands)
        self.assertEqual(state.melds, original.melds)
        self.assertEqual(state.wall, original.wall)
        self.assertIsNone(state.pending_discard)
        self.assertFalse(state.terminal)
        self.assertEqual(event["before_hash"], original.state_hash())
        self.assert_conserved(state)

    def test_pass_completes_kong_then_exact_tail_draw(self):
        original = added_kong_state()
        instance = environment(original)
        self.declare(instance)
        state, pass_event = instance.step(env.Action(1, env.ActionType.PASS))
        self.assertEqual(state.phase, "AFTER_ADDED_GANG")
        self.assertEqual(state.current_player, 0)
        self.assertEqual(state.melds[0][0].kind, "ADDED_GANG")
        self.assertEqual(state.melds[0][0].tiles, [KONG_TILE] * 4)
        self.assertEqual(state.melds[0][0].from_player, 1)
        self.assertNotIn(KONG_TILE, state.hands[0])
        self.assertEqual(len(state.hands[0]), 13)
        self.assertEqual(state.wall, original.wall)
        self.assertTrue(pass_event["action"]["metadata"])  # Audited response reference.
        self.assert_conserved(state)
        draw = action_of(instance, env.ActionType.DRAW)
        self.assertEqual(draw.metadata, {
            "source": "wall_tail", "kong_kind": "ADDED_GANG"})
        state, event = instance.step(draw)
        self.assertEqual(state.phase, "AFTER_DRAW")
        self.assertEqual(state.hands[0][-1], "P8")
        self.assertEqual(len(state.hands[0]), 14)
        self.assertEqual(len(state.wall), len(original.wall) - 1)
        self.assertEqual(event["action"]["metadata"]["drawn_tile"], "P8")
        self.assertFalse(state.terminal)
        self.assert_conserved(state)

    def test_non_last_peng_is_upgraded_in_place(self):
        original = added_kong_state(multiple_melds=True)
        instance = environment(original)
        self.declare(instance)
        state, _ = instance.step(env.Action(1, env.ActionType.PASS))
        self.assertEqual(len(state.melds[0]), 2)
        self.assertEqual(state.melds[0][0].kind, "ADDED_GANG")
        self.assertEqual(state.melds[0][1], original.melds[0][1])
        state, _ = instance.step(action_of(instance, env.ActionType.DRAW))
        self.assertEqual(len(state.hands[0]), 11)
        self.assert_conserved(state)

    def test_rob_hu_preserves_peng_and_fourth_tile_as_a_reference(self):
        original = added_kong_state(rob=True)
        instance = environment(original)
        self.declare(instance)
        rob = action_of(instance, env.ActionType.ROB_KONG_HU)
        self.assertEqual(rob.tile, KONG_TILE)
        self.assertEqual(rob.metadata, {
            "win_source": "rob_kong", "kong_player": 0, "meld_index": 0})
        state, _ = instance.step(rob)
        self.assertEqual(state.phase, "ROB_KONG_HU_DECLARED")
        self.assertEqual(state.current_player, 1)
        self.assertEqual(state.pending_kong, {
            "kong_player": 0, "tile": KONG_TILE, "meld_index": 0})
        self.assertEqual(state.pending_hu, {
            "winner": 1, "loser": 0, "source": "rob_kong",
            "robbed_tile": KONG_TILE, "winning_tile": KONG_TILE,
            "kong_player": 0, "meld_index": 0})
        self.assertEqual(state.hands, original.hands)
        self.assertEqual(state.melds, original.melds)
        self.assertEqual(state.wall, original.wall)
        self.assertEqual(state.rewards, [0, 0])
        self.assertFalse(state.terminal)
        self.assert_conserved(state)

    def test_available_rob_hu_can_be_declined_with_pass(self):
        instance = environment(added_kong_state(rob=True))
        self.declare(instance)
        actions = instance.legal_actions()
        self.assertIn(env.Action(1, env.ActionType.PASS), actions)
        self.assertTrue(any(action.type == env.ActionType.ROB_KONG_HU
                            for action in actions))
        state, _ = instance.step(env.Action(1, env.ActionType.PASS))
        self.assertEqual(state.phase, "AFTER_ADDED_GANG")
        self.assertEqual(state.melds[0][0].kind, "ADDED_GANG")
        self.assert_conserved(state)

    def test_no_structural_win_means_pass_only(self):
        instance = environment(added_kong_state())
        self.declare(instance)
        self.assertEqual(instance.legal_actions(), [env.Action(1, env.ActionType.PASS)])

    def test_one_or_two_gold_cannot_rob_despite_self_draw_structure(self):
        for count in (1, 2):
            with self.subTest(gold_count=count):
                state = added_kong_state(rob=True, gold_count=count)
                self.assertTrue(HuianRules().analyze_hu(
                    state.hands[1] + [KONG_TILE], state.gold_tile,
                    winning_tile=KONG_TILE, win_type="zimo").legal)
                instance = environment(state)
                self.declare(instance)
                actions = instance.legal_actions()
                self.assertEqual(actions, [env.Action(1, env.ActionType.PASS)])

    def test_pure_options_filter_gold_and_require_peng_fourth_copy(self):
        state = added_kong_state(multiple_melds=True)
        rules = HuianRules()
        hand, melds = deepcopy(state.hands[0]), deepcopy(state.melds[0])
        self.assertEqual(rules.added_kong_options(hand, melds, "P9"),
                         ((0, KONG_TILE),))
        self.assertEqual(rules.added_kong_options(hand, melds, KONG_TILE), ())
        hand.remove(KONG_TILE)
        self.assertEqual(rules.added_kong_options(hand, melds, "P9"), ())
        self.assertEqual(melds, state.melds[0])
        self.assertEqual(state.hands[0].count(KONG_TILE), 1)

    def test_illegal_declarations_are_atomic(self):
        instance = environment(added_kong_state(multiple_melds=True))
        for action in (
            env.Action(1, env.ActionType.ADD_KONG, tile=KONG_TILE,
                       tiles=(KONG_TILE,) * 4, metadata={"meld_index": 0}),
            env.Action(0, env.ActionType.ADD_KONG, tile="P2",
                       tiles=("P2",) * 4, metadata={"meld_index": 0}),
            env.Action(0, env.ActionType.ADD_KONG, tile=KONG_TILE,
                       tiles=(KONG_TILE,) * 3, metadata={"meld_index": 0}),
            env.Action(0, env.ActionType.ADD_KONG, tile=KONG_TILE,
                       tiles=(KONG_TILE,) * 4),
        ):
            with self.subTest(action=action):
                self.assert_rejected_atomically(instance, action)
        for index in (-1, 1, 99, True, 0.0):
            with self.subTest(meld_index=index):
                self.assert_rejected_atomically(instance, env.Action(
                    0, env.ActionType.ADD_KONG, tile=KONG_TILE,
                    tiles=(KONG_TILE,) * 4, metadata={"meld_index": index}))

    def test_only_after_draw_may_declare_added_kong(self):
        state = added_kong_state()
        state.phase = "AFTER_PENG"
        instance = environment(state)
        self.assertTrue(all(action.type == env.ActionType.DISCARD
                            for action in instance.legal_actions()))
        self.assert_rejected_atomically(instance, env.Action(
            0, env.ActionType.ADD_KONG, tile=KONG_TILE,
            tiles=(KONG_TILE,) * 4, metadata={"meld_index": 0}))

    def test_forged_rob_and_pass_references_are_atomic(self):
        instance = environment(added_kong_state(rob=True))
        self.declare(instance)
        for action in (
            env.Action(0, env.ActionType.PASS),
            env.Action(1, env.ActionType.ROB_KONG_HU, tile="P2",
                       metadata={"win_source": "rob_kong", "kong_player": 0,
                                 "meld_index": 0}),
            env.Action(1, env.ActionType.ROB_KONG_HU, tile=KONG_TILE,
                       metadata={"win_source": "rob_kong", "kong_player": 1,
                                 "meld_index": 0}),
            env.Action(1, env.ActionType.ROB_KONG_HU, tile=KONG_TILE,
                       metadata={"win_source": "rob_kong", "kong_player": 0,
                                 "meld_index": 1}),
            env.Action(1, env.ActionType.PASS,
                       metadata={"kong_player": 1, "tile": KONG_TILE,
                                 "meld_index": 0}),
        ):
            with self.subTest(action=action):
                self.assert_rejected_atomically(instance, action)

    def test_boolean_kong_action_references_are_not_integer_indices(self):
        instance = environment(added_kong_state(rob=True))
        add = action_of(instance, env.ActionType.ADD_KONG)
        add.metadata["meld_index"] = False
        self.assert_rejected_atomically(instance, add)
        self.declare(instance)
        for key in ("meld_index", "kong_player"):
            action = action_of(instance, env.ActionType.ROB_KONG_HU)
            action.metadata[key] = False
            self.assert_rejected_atomically(instance, action)

    def test_invalid_pending_reference_import_preserves_history(self):
        instance = environment(added_kong_state(rob=True))
        self.declare(instance)
        original_hash, original_events = instance.state.state_hash(), instance.events
        for key, value in (("tile", "P2"), ("meld_index", -1),
                           ("meld_index", True), ("kong_player", 1)):
            with self.subTest(field=key, value=value):
                invalid = instance.state
                invalid.pending_kong[key] = value
                with self.assertRaises(ValueError):
                    instance.set_state(invalid)
                self.assertEqual(instance.state.state_hash(), original_hash)
                self.assertEqual(instance.events, original_events)
        instance.step(action_of(instance, env.ActionType.ROB_KONG_HU))
        original_hash, original_events = instance.state.state_hash(), instance.events
        invalid = instance.state
        invalid.pending_hu["robbed_tile"] = "P2"
        with self.assertRaises(ValueError):
            instance.set_state(invalid)
        self.assertEqual(instance.state.state_hash(), original_hash)
        self.assertEqual(instance.events, original_events)

    def test_tail_flowers_reuse_pipeline_and_preserve_kong_source(self):
        original = added_kong_state(tail=("F1", "F2", "P8"))
        instance = environment(original)
        self.declare(instance)
        instance.step(env.Action(1, env.ActionType.PASS))
        state, event = instance.step(action_of(instance, env.ActionType.DRAW))
        self.assertEqual(state.phase, "AFTER_DRAW")
        self.assertEqual(state.flowers[0], ["F1", "F2"])
        self.assertEqual(state.hands[0][-1], "P8")
        self.assertEqual(len(state.hands[0]), 14)
        self.assertEqual(len(state.wall), len(original.wall) - 3)
        metadata = event["action"]["metadata"]
        self.assertEqual(metadata["source"], "wall_tail")
        self.assertEqual(metadata["kong_kind"], "ADDED_GANG")
        self.assertEqual(metadata["drawn_tile"], "F1")
        self.assertEqual(metadata["effective_drawn_tile"], "P8")
        self.assertTrue(event["flower_replacements"])
        self.assertFalse(any(tile in env.FLOWERS for tile in state.hands[0]))
        self.assert_conserved(state)

    def test_clone_checkpoint_and_replay_preserve_pending_audit_and_flowers(self):
        original = added_kong_state(tail=("F1", "F2", "P8"))
        instance = environment(original)
        self.declare(instance)
        pending_hash = instance.state.state_hash()
        checkpoint = instance.checkpoint()
        clone = instance.clone()
        instance.step(env.Action(1, env.ActionType.PASS))
        instance.step(action_of(instance, env.ActionType.DRAW))
        final_hash, events = instance.state.state_hash(), instance.events
        self.assertEqual(clone.state.state_hash(), pending_hash)
        for event in events[1:]:
            clone.step(env.Action.from_dict(event["action"]))
        self.assertEqual(clone.state.state_hash(), final_hash)
        self.assertEqual(clone.events, events)
        self.assertEqual(instance.rollback(checkpoint).state_hash(), pending_hash)
        for event in events[1:]:
            instance.step(env.Action.from_dict(event["action"]))
        self.assertEqual(instance.events, events)
        replay = environment(original)
        for event in events:
            action = env.Action.from_dict(event["action"])
            if action.type == env.ActionType.DRAW:
                # Derived log values must be recomputed, never trusted as input.
                action.metadata["drawn_tile"] = "M9"
                action.metadata["effective_drawn_tile"] = "M9"
            replay.step(action)
        self.assertEqual(replay.events, events)
        self.assertEqual(replay.state.state_hash(), final_hash)
        self.assert_conserved(replay.state)

    def test_robbed_kong_replay_keeps_same_physical_reference(self):
        original = added_kong_state(rob=True)
        instance = environment(original)
        self.declare(instance)
        instance.step(action_of(instance, env.ActionType.ROB_KONG_HU))
        replay = environment(original)
        for event in instance.events:
            replay.step(env.Action.from_dict(event["action"]))
        self.assertEqual(replay.events, instance.events)
        self.assertEqual(replay.state.state_hash(), instance.state.state_hash())
        self.assertEqual(replay.state.hands, original.hands)
        self.assert_conserved(replay.state)

    def test_three_scoring_unknowns_keep_declaration_audit(self):
        cases = (
            (added_kong_state(rob=True), True, "ROB_KONG_SCORING_UNKNOWN",
             "ROB_KONG_HU_DECLARED", 1, "rob_kong", 2),
            (added_kong_state(kong_hu=True, tail=("E",)), False,
             "GANG_HU_SCORING_UNKNOWN", "HU_DECLARED", 0, "kong_tail_draw", 4),
            (added_kong_state(), False, "ADD_KONG_SCORING_UNKNOWN",
             "AFTER_DRAW", None, None, 3),
        )
        for state, rob, reason, phase, winner, source, steps in cases:
            with self.subTest(reason=reason):
                instances = []
                def factory(**options):
                    instance = HuianEnvironment(**options)
                    instances.append(instance)
                    return instance
                result = Simulator(factory).run_normal_hand(
                    seed=17, initial_state=state, agent=AddedKongFixtureAgent(rob),
                    max_steps=steps)
                self.assertEqual(result.status, "STOPPED_UNKNOWN")
                self.assertEqual(result.unresolved, (reason,))
                self.assertEqual(result.stop_reason, "unresolved_rule")
                self.assertEqual(result.phase, phase)
                self.assertEqual(result.winner, winner)
                self.assertEqual(result.win_source, source)
                self.assertEqual(result.steps, steps)
                self.assertEqual(result.rewards, (0, 0))
                self.assertFalse(instances[0].state.terminal)
                self.assertIsNone(result.terminal_reason)
                self.assertNotIn("END_HAND", [e["action"]["type"] for e in result.events])
                previous_hash = result.initial_state_hash
                for event in result.events:
                    self.assertEqual(event["before_hash"], previous_hash)
                    previous_hash = event["after_hash"]
                    self.assertTrue(event["decision"]["reason"])
                self.assertEqual(previous_hash, result.state_hash)
                self.assert_conserved(instances[0].state)

    def test_unknown_scores_cannot_be_finalized_as_observed_ordinary_wins(self):
        for branch, reason, winner, win_type in (
            ("rob", "ROB_KONG_SCORING_UNKNOWN", 1, "PINGHU"),
            ("gang_hu", "GANG_HU_SCORING_UNKNOWN", 0, "ZIMO"),
            ("add", "ADD_KONG_SCORING_UNKNOWN", 0, "ZIMO"),
        ):
            with self.subTest(branch=branch):
                instance = environment(added_kong_state(
                    rob=branch == "rob", kong_hu=branch == "gang_hu",
                    tail=("E",) if branch == "gang_hu" else ("P8",)))
                self.declare(instance)
                if branch == "rob":
                    instance.step(action_of(instance, env.ActionType.ROB_KONG_HU))
                else:
                    instance.step(env.Action(1, env.ActionType.PASS))
                    instance.step(action_of(instance, env.ActionType.DRAW))
                    if branch == "gang_hu":
                        instance.step(action_of(instance, env.ActionType.HU))
                before, events = instance.state.state_hash(), instance.events
                with self.assertRaises(UnknownRuleError) as caught:
                    instance.finalize_observed_outcome(
                        winner=winner, current_dealer_base=10, winner_fan=1,
                        win_type=win_type)
                self.assertEqual(caught.exception.rule_ids, (reason,))
                self.assertEqual(instance.state.state_hash(), before)
                self.assertEqual(instance.events, events)

    def test_ming_and_an_tail_draw_cannot_bypass_gang_scoring_without_hu(self):
        for kind in ("MING_GANG", "AN_GANG"):
            with self.subTest(kong_kind=kind):
                # Import only the already-completed kong, after its response
                # resolution; this does not assume that every kong is unrobbable.
                state = added_kong_state()
                state.hands[0].remove(KONG_TILE)
                state.melds[0][0] = env.Meld(
                    kind, [KONG_TILE] * 4, None if kind == "AN_GANG" else 1)
                state.phase = "AFTER_" + kind
                state.last_action = env.Action(
                    0, env.ActionType(kind), tile=KONG_TILE,
                    tiles=(KONG_TILE,) * 4).to_dict()
                instance = environment(state)
                instance.step(action_of(instance, env.ActionType.DRAW))
                self.assertEqual(instance.state.phase, "AFTER_DRAW")
                self.assertIsNone(instance.state.pending_hu)
                self.assertEqual(instance.state.last_action["metadata"]["source"],
                                 "wall_tail")
                self.assertEqual(instance.state.last_action["metadata"]["kong_kind"],
                                 kind)
                before, events = instance.state.state_hash(), instance.events
                with self.assertRaises(UnknownRuleError) as caught:
                    instance.finalize_observed_outcome(
                        winner=0, current_dealer_base=10, winner_fan=1,
                        win_type="ZIMO")
                self.assertEqual(caught.exception.rule_ids,
                                 ("GANG_HU_SCORING_UNKNOWN",))
                self.assertEqual(instance.state.state_hash(), before)
                self.assertEqual(instance.events, events)
                self.assert_conserved(instance.state)

    def test_added_kong_cannot_be_imported_as_forged_observed_terminal(self):
        instance = environment(added_kong_state())
        self.declare(instance)
        instance.step(env.Action(1, env.ActionType.PASS))
        instance.step(action_of(instance, env.ActionType.DRAW))
        before, events = instance.state.state_hash(), instance.events
        for reason in ("OBSERVED_PINGHU", "OBSERVED_ZIMO"):
            with self.subTest(terminal_reason=reason):
                forged = instance.state
                forged.phase = "TERMINAL"
                forged.terminal = True
                forged.terminal_reason = reason
                forged.rewards = [11, -11]
                with self.assertRaises(ValueError):
                    instance.set_state(forged)
                self.assertEqual(instance.state.state_hash(), before)
                self.assertEqual(instance.events, events)

    def test_added_kong_at_16_tiles_does_not_fabricate_zero_score_draw(self):
        state = added_kong_state(wall_count=17)
        result = Simulator().run_normal_hand(
            seed=17, initial_state=state, agent=AddedKongFixtureAgent(False),
            max_steps=3)
        self.assertEqual(result.wall_remaining, 16)
        self.assertEqual(result.status, "STOPPED_UNKNOWN")
        self.assertEqual(result.unresolved, ("ADD_KONG_SCORING_UNKNOWN",))
        self.assertEqual(result.steps, 3)
        self.assertIsNone(result.terminal_reason)
        self.assertEqual(result.rewards, (0, 0))

    def test_disabling_candidates_does_not_skip_an_existing_rob_window(self):
        disabled_rules = HuianRulesAdapter(HuianRules(RulesConfig(
            simulation_only_normal_hand=True, enable_added_kong=False)))
        disabled = HuianEnvironment(rules=disabled_rules)
        disabled.set_state(added_kong_state(rob=True))
        self.assertFalse(any(action.type == env.ActionType.ADD_KONG
                             for action in disabled.legal_actions()))
        enabled = environment(added_kong_state(rob=True))
        self.declare(enabled)
        pending_hash = enabled.state.state_hash()
        disabled.set_state(enabled.state)
        self.assertEqual(disabled.state.state_hash(), pending_hash)
        self.assertEqual(disabled.state.phase, "ROB_KONG_WINDOW")
        self.assertEqual(
            {action.type for action in disabled.legal_actions()},
            {env.ActionType.ROB_KONG_HU, env.ActionType.PASS})
        state, _ = disabled.step(action_of(disabled, env.ActionType.ROB_KONG_HU))
        self.assertEqual(state.phase, "ROB_KONG_HU_DECLARED")
        self.assert_conserved(state)

    def test_baseline_takes_rob_hu_before_pass_with_a_reason(self):
        instance = environment(added_kong_state(rob=True))
        self.declare(instance)
        rob = action_of(instance, env.ActionType.ROB_KONG_HU)
        actions = [env.Action(1, env.ActionType.PASS), rob]
        original = deepcopy(actions)
        observation = PlayerObservation.from_state(instance.state)
        decision = BaselineAgent().choose_decision(observation, actions)
        self.assertIsInstance(decision, AgentDecision)
        self.assertEqual(decision.action, rob)
        self.assertIn(decision.action, instance.legal_actions())
        self.assertIsInstance(decision.reason, str)
        self.assertTrue(decision.reason.strip())
        self.assertEqual(actions, original)

    def test_pass_audit_rejects_boolean_integer_aliases_atomically(self):
        instance = environment(added_kong_state(rob=True))
        self.declare(instance)
        for field in ("meld_index", "kong_player"):
            with self.subTest(field=field):
                forged = deepcopy(instance.state.pending_kong)
                # False compares equal to integer zero in Python; audit inputs
                # must still reject it instead of canonicalizing the reference.
                forged[field] = False
                self.assert_rejected_atomically(instance, env.Action(
                    1, env.ActionType.PASS, metadata=forged))

    def test_no_fifth_copy_or_negative_wall_can_enter_new_phases(self):
        valid = added_kong_state()
        fifth = deepcopy(valid)
        index = next(i for i, tile in enumerate(fifth.wall) if tile != KONG_TILE)
        fifth.wall[index] = KONG_TILE
        with self.assertRaises(ValueError):
            environment(fifth)
        short = added_kong_state(wall_count=15)
        with self.assertRaises(ValueError):
            environment(short)


if __name__ == "__main__":
    unittest.main()
