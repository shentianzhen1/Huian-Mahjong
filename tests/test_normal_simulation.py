import unittest
from collections import Counter
from copy import deepcopy

from huian import HuianEnvironment, DeadLoopError
from huian._legacy import env
from workspace.ai import AgentDecision, BaselineAgent
from workspace.simulator import Simulator, SimulatorConfig
from test_huian_environment import scenario


WIN_HAND = ["M1", "M1", "M2", "M3", "M4", "M5", "M6", "M7",
            "P1", "P2", "P3", "S1", "S2", "S3", "E", "E", "E"]
DEALER_HAND = ["M8", "M9", "M9", "P4", "P5", "P7", "P8", "S4",
               "S5", "S7", "S8", "S9", "N", "N", "W", "P6", "E"]


def opening_wall(self_draw=False):
    """Complete, deterministic 144-tile fixture in simulator dealing order."""
    dealer = list(DEALER_HAND)
    if self_draw:
        dealer[-1] = "N"
    waiting = WIN_HAND[:-1]
    prefix = [tile for pair in zip(dealer[:16], waiting) for tile in pair] + dealer[16:]
    remaining = env.full_wall()
    for tile in prefix:
        remaining.remove(tile)
    if self_draw:
        remaining.remove("E")
        remaining.insert(0, "E")
    # Dice total 7: indicator is the 13th tile from the remaining wall's tail.
    remaining.remove("P9")
    remaining.insert(len(remaining) + 1 - 13, "P9")
    return prefix + remaining


def boundary_state():
    state = scenario("NEED_DRAW")
    state.reserved_tiles.extend(state.wall[17:])
    state.wall = state.wall[:17]
    return state


class FirstDiscardAgent:
    def __init__(self, tile):
        self.tile = tile

    def choose_action(self, observation, legal_actions):
        action = next(a for a in legal_actions if a.type == env.ActionType.DISCARD
                      and a.tile == self.tile)
        return AgentDecision(action, "Fixed-wall fixture: specified first discard")


class NormalSimulationTests(unittest.TestCase):
    def run_fixture(self, **kwargs):
        instances = []

        def factory(**options):
            game = HuianEnvironment(**options)
            instances.append(game)
            return game

        result = Simulator(factory).run_normal_hand(**kwargs)
        return result, instances[0]

    def assert_audit(self, result, game):
        previous = result.initial_state_hash
        for seq, event in enumerate(result.events):
            self.assertEqual(event["seq"], seq)
            self.assertEqual(event["before_hash"], previous)
            previous = event["after_hash"]
            if event["action"]["type"] not in (
                    "OPEN_GOLD", "SIMULATION_SKIP_QIANGJIN", "END_HAND"):
                self.assertTrue(event["decision"]["reason"])
                self.assertNotIn("reason", event["action"].get("metadata", {}))
        self.assertEqual(previous, result.state_hash)
        self.assertEqual(Counter(game.state.physical_tiles()), Counter(env.full_wall()))
        self.assertEqual(sum(result.rewards), 0)
        self.assertEqual(game.legal_actions(), [])

    def test_fixed_full_wall_pinghu_both_dealers(self):
        for dealer in (0, 1):
            agents = [None, None]
            agents[dealer] = FirstDiscardAgent("E")
            agents[1 - dealer] = BaselineAgent()
            result, game = self.run_fixture(wall=opening_wall(), dice_total=7, dealer=dealer,
                                            agents=agents, max_steps=2)
            self.assertEqual(result.status, "COMPLETED")
            self.assertEqual(result.winner, 1 - dealer)
            self.assertEqual(result.win_source, "discard")
            self.assertEqual(result.rewards[1 - dealer], 1)
            self.assertEqual(result.steps, 2)
            self.assertEqual(game.state.discards[dealer], ["E"])
            self.assert_audit(result, game)
            end = result.events[-1]["action"]["metadata"]
            self.assertTrue(end["simulation_only"])
            self.assertEqual(end["hu_declaration"]["discard_player"], dealer)
            self.assertEqual(end["hu_declaration"]["river_index"], 0)

    def test_fixed_full_wall_self_draw_at_exact_step_limit(self):
        result, game = self.run_fixture(
            wall=opening_wall(True), dice_total=7,
            agents=(FirstDiscardAgent("P8"), BaselineAgent()), max_steps=4)
        self.assertEqual(result.status, "COMPLETED")
        self.assertEqual(result.winner, 1)
        self.assertEqual(result.win_source, "self_draw")
        self.assertEqual(result.rewards, (-2, 2))
        self.assertEqual(result.steps, 4)
        self.assert_audit(result, game)
        self.assertEqual(result.events[-1]["action"]["metadata"]["hu_declaration"]["winning_tile"], "E")

    def test_real_scoring_profile_uses_fan_aggregator_for_pinghu_and_zimo(self):
        instances = []

        def factory(**options):
            game = HuianEnvironment(**options)
            instances.append(game)
            return game

        simulator = Simulator(
            factory, config=SimulatorConfig(enable_real_scoring=True))

        result = simulator.run_normal_hand(
            wall=opening_wall(), dice_total=7, dealer=0,
            agents=(FirstDiscardAgent("E"), BaselineAgent()),
            max_steps=2, current_dealer_base=5)
        self.assertEqual(result.status, "COMPLETED")
        self.assertTrue(result.simulation_only)
        self.assertTrue(result.real_scoring)
        self.assertEqual(result.terminal_reason, "AUTO_PINGHU")
        self.assertEqual(result.rewards, (-5, 5))
        self.assertEqual(result.winner, 1)
        self.assertEqual(result.events[-1]["action"]["metadata"]["winner_fan"], 0)

        result = simulator.run_normal_hand(
            wall=opening_wall(True), dice_total=7, dealer=0,
            agents=(FirstDiscardAgent("P8"), BaselineAgent()),
            max_steps=4, current_dealer_base=5)
        self.assertEqual(result.status, "COMPLETED")
        self.assertTrue(result.real_scoring)
        self.assertEqual(result.terminal_reason, "AUTO_ZIMO")
        self.assertEqual(result.rewards, (-14, 14))
        self.assertEqual(result.events[-1]["action"]["metadata"]["winner_fan"], 2)

    def test_real_scoring_profile_requires_explicit_dealer_base(self):
        simulator = Simulator(config=SimulatorConfig(enable_real_scoring=True))
        with self.assertRaisesRegex(ValueError, "current_dealer_base"):
            simulator.run_normal_hand(seed=1, max_steps=1)
        with self.assertRaisesRegex(ValueError, "only valid"):
            Simulator().run_normal_hand(
                seed=1, max_steps=1, current_dealer_base=5)

    def test_fixed_wall_reaches_16_on_last_allowed_step(self):
        original = boundary_state()
        snapshot = deepcopy(original)
        result, game = self.run_fixture(initial_state=original, max_steps=1)
        self.assertEqual(original, snapshot)
        self.assertEqual(result.status, "COMPLETED")
        self.assertEqual(result.terminal_reason, "WALL_16")
        self.assertEqual(result.wall_remaining, 16)
        self.assertIsNone(result.winner)
        self.assertIsNone(result.win_source)
        self.assertEqual(result.rewards, (0, 0))
        self.assert_audit(result, game)

    def test_max_steps_does_not_fabricate_terminal(self):
        result = Simulator().run_normal_hand(
            wall=opening_wall(True), dice_total=7,
            agents=(FirstDiscardAgent("P8"), BaselineAgent()), max_steps=1)
        self.assertEqual(result.status, "MAX_STEPS")
        self.assertEqual(result.steps, 1)
        self.assertIsNone(result.winner)
        self.assertIsNone(result.terminal_reason)
        self.assertEqual(result.stop_reason, "max_steps")

    def test_special_config_is_unknown_and_strictly_boolean(self):
        for field in SimulatorConfig.__dataclass_fields__:
            if field.startswith("enable_") and field not in ("enable_added_kong", "enable_real_scoring"):
                simulator = Simulator(config=SimulatorConfig(**{field: True}))
                result = simulator.run_normal_hand(seed=1)
                self.assertEqual(result.status, "STOPPED_UNKNOWN")
                self.assertEqual(result.stop_reason, "unsupported_config")
                self.assertIn(field.removeprefix("enable_"), result.unresolved)
                self.assertEqual(result.steps, 0)
        with self.assertRaises(ValueError):
            SimulatorConfig(enable_youjin="false")
        with self.assertRaises(ValueError):
            Simulator(config=SimulatorConfig(normal_hand_mode=False)).run_normal_hand()

    def test_observed_special_situation_stops_with_reason(self):
        state = boundary_state()
        # Leave >16 in wall so set_state does not itself resolve a draw.
        state.special_states[0] = "TRIPLE_YOU"
        result = Simulator().run_normal_hand(initial_state=state)
        self.assertEqual(result.status, "STOPPED_UNKNOWN")
        self.assertEqual(result.unresolved, ("youjin_permissions",))
        self.assertEqual(result.steps, 0)
        self.assertEqual(result.unknown_evidence["rule_ids"], ["youjin_permissions"])
        self.assertEqual(result.unknown_evidence["state_hash"], result.state_hash)
        self.assertEqual(result.unknown_evidence["phase"], "NEED_DRAW")
        self.assertEqual(result.unknown_evidence["gold_tile"], state.gold_tile)
        state.special_states[0] = "NORMAL"
        # Three E already occur in our fixture; change the indicator, not inventory.
        # Sanjindao is optional, so simulation-only may take the confirmed
        # CONTINUE_PLAY branch instead of censoring the hand on timing.
        state.gold_tile = "E"
        result = Simulator().run_normal_hand(initial_state=state)
        self.assertNotIn("sanjindao_timing", result.unresolved)
        self.assertNotEqual(result.steps, 0)
        state = scenario("NEED_DRAW")
        for flower in env.FLOWERS:
            state.wall.remove(flower)
            state.flowers[0].append(flower)
        result = Simulator().run_normal_hand(initial_state=state, max_steps=1)
        self.assertNotIn("eight_flowers_special_win", result.unresolved)

    def test_real_scoring_chooses_maximum_fan_decomposition(self):
        hand = [
            "M1", "M1", "M1",
            "M2", "M2", "M2",
            "M3", "M3", "M3",
            "M4", "M4", "M4",
            "M5", "M5", "M5",
            "M6", "M6",
        ]
        state = scenario("HU_DECLARED", hand)
        state.pending_hu = {
            "winner": 0, "source": "self_draw", "winning_tile": "M6",
            "kong_kind": None, "discard_player": None, "river_index": None,
        }
        result = Simulator(
            config=SimulatorConfig(enable_real_scoring=True)
        ).run_normal_hand(
            initial_state=state, current_dealer_base=10
        )
        self.assertEqual(result.status, "COMPLETED")
        self.assertEqual(result.terminal_reason, "AUTO_ZIMO")
        metadata = result.events[-1]["action"]["metadata"]
        self.assertEqual(metadata["fan_selection_policy"], "MAX_TOTAL_FAN")
        self.assertEqual(
            metadata["winner_fan"], max(metadata["fan_candidate_fans"]))
        self.assertIsNone(result.unknown_evidence)

    def test_rules_unknown_and_dead_loop_are_recorded(self):
        state = scenario("AFTER_DRAW", hand=DEALER_HAND[:14] + ["N", "P6", "N"])
        # Ming/An kongs are confirmed unrobbable, so a concealed-kong opportunity
        # must no longer censor ordinary simulation as a rob_kong UNKNOWN.
        result = Simulator().run_normal_hand(initial_state=state)
        self.assertNotIn("rob_kong", result.unresolved)

        class LoopEnvironment(HuianEnvironment):
            def step(self, action):
                raise DeadLoopError("fixture repeated position")

        result = Simulator(LoopEnvironment).run_normal_hand(initial_state=boundary_state())
        self.assertEqual(result.status, "STOPPED_LOOP")
        self.assertEqual(result.stop_reason, "fixture repeated position")
        self.assertIsNone(result.terminal_reason)

    def test_decision_observer_gets_truth_copy_without_mutating_game(self):
        state = boundary_state()
        seen = []

        def observer(truth, observation, legal_actions):
            seen.append((truth.state_hash(), observation.seat, len(legal_actions)))
            truth.hands[observation.seat].clear()
            legal_actions.clear()

        result = Simulator().run_normal_hand(
            initial_state=state, max_steps=1, decision_observer=observer)
        self.assertEqual(result.status, "COMPLETED")
        self.assertEqual(result.terminal_reason, "WALL_16")
        self.assertTrue(seen)
        self.assertEqual(len(state.hands[0]), len(scenario("NEED_DRAW").hands[0]))

        with self.assertRaises(TypeError):
            Simulator().run_normal_hand(
                initial_state=boundary_state(), decision_observer=object())

    def test_illegal_agent_and_bad_inputs_are_errors(self):
        class BadAgent:
            def choose_action(self, state, legal_actions):
                return AgentDecision(env.Action(1, env.ActionType.HU), "Invalid fixture action")
        with self.assertRaises(ValueError):
            Simulator().run_normal_hand(initial_state=boundary_state(), agent=BadAgent())
        for limit in (0, -1, True):
            with self.assertRaises(ValueError):
                Simulator().run_normal_hand(max_steps=limit)
        bad_wall = opening_wall()
        bad_wall[-1] = "M1"  # A fifth M1 and a missing flower.
        with self.assertRaises(ValueError):
            Simulator().run_normal_hand(wall=bad_wall)
        state = boundary_state()
        state.reserved_tiles.extend(state.wall[15:])
        state.wall = state.wall[:15]
        with self.assertRaises(ValueError):
            Simulator().run_normal_hand(initial_state=state)

    def test_simulation_profile_cannot_be_used_as_real_outcome(self):
        real = HuianEnvironment()
        real.reset(seed=1)
        original = real.state.state_hash()
        with self.assertRaises(ValueError):
            real.begin_normal_hand(7)
        self.assertEqual(real.state.state_hash(), original)
        result, simulated = self.run_fixture(
            wall=opening_wall(), dice_total=7,
            agents=(FirstDiscardAgent("E"), BaselineAgent()), max_steps=2)
        self.assertEqual(result.status, "COMPLETED")
        with self.assertRaises(ValueError):
            real.set_state(simulated.state)
        self.assertEqual(real.state.state_hash(), original)
        with self.assertRaises(ValueError):
            real.finalize_simulation_only_outcome()

    def test_run_dispatches_only_explicit_profile(self):
        result = Simulator(config=SimulatorConfig()).run(seed=1, max_steps=1)
        self.assertTrue(result.simulation_only)
        self.assertNotEqual(result.phase, "OPENING_QIANGJIN_CHECK")
        self.assertFalse(Simulator().run(seed=1).simulation_only)

    def test_finished_fixture_cannot_masquerade_as_a_new_completed_hand(self):
        result, game = self.run_fixture(initial_state=boundary_state(), max_steps=1)
        self.assertEqual(result.status, "COMPLETED")
        with self.assertRaisesRegex(ValueError, "active mid-hand"):
            Simulator().run_normal_hand(initial_state=game.state)


if __name__ == "__main__":
    unittest.main()
