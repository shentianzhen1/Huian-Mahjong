import unittest

from huian import (HuianEnvironment, HuianGameState, HuianRules, HuianRulesAdapter,
                   RulesConfig, UnknownRuleError, DeadLoopError)
from huian._legacy import env


HAND = ["M1", "M2", "M4", "M5", "M7", "M8", "P1", "P2",
        "P4", "S1", "S2", "S4", "E", "E", "E", "N"]


def scenario(phase="AFTER_DISCARD", hand=None, discard="M3"):
    state = HuianGameState(phase=phase, gold_tile="P9", special_states=["NORMAL", "NORMAL"])
    state.hands[0] = list(HAND if hand is None else hand)
    state.reserved_tiles = ["P9"]  # Explicit fixture accounting, not an opening rule.
    if phase == "AFTER_DISCARD":
        state.discards[1] = [discard]
        state.pending_discard = dict(player=1, tile=discard, river_index=0)
    remaining = env.full_wall()
    for tile in state.physical_tiles():
        remaining.remove(tile)
    for tile in remaining.copy():
        if tile in env.BASE_TILES and tile != "P9" and len(state.hands[1]) < 16:
            state.hands[1].append(tile)
            remaining.remove(tile)
    state.wall = remaining
    return state


def game(state, experimental=False, **kwargs):
    adapter = HuianRulesAdapter(HuianRules(RulesConfig(experimental_no_rob_kong=experimental)))
    result = HuianEnvironment(adapter, **kwargs)
    result.set_state(state)
    return result


def choose(instance, kind):
    return next(a for a in instance.action_report().known_actions if a.type == kind)


class EnvironmentTests(unittest.TestCase):
    def test_chi_transfers_river_tile_and_requires_discard(self):
        instance = game(scenario())
        self.assertIn(env.Action(0, env.ActionType.PASS), instance.legal_actions())
        before = sorted(instance.state.physical_tiles())
        state, event = instance.step(choose(instance, env.ActionType.CHI))
        self.assertEqual(state.discards[1], [])
        self.assertIsNone(state.pending_discard)
        self.assertEqual(state.melds[0][0].tiles, ["M1", "M2", "M3"])
        self.assertEqual(len(state.hands[0]), 14)
        self.assertEqual(state.phase, "AFTER_CHI")
        self.assertEqual(sorted(state.physical_tiles()), before)
        self.assertTrue(all(a.type == env.ActionType.DISCARD for a in instance.legal_actions()))
        after, _ = instance.step(instance.legal_actions()[0])
        self.assertEqual(after.phase, "AFTER_DISCARD")
        self.assertEqual(after.current_player, 1)
        self.assertEqual(len(after.hands[0]), 13)
        self.assertEqual(event["after_hash"], state.state_hash())

    def test_peng_transfers_only_latest_river_copy(self):
        # Move another physical E from wall into the earlier river position.
        # HAND has three E, so use a two-E hand to leave one spare copy.
        state = scenario(hand=HAND[:-2] + ["P6", "N"], discard="E")
        state.wall.remove("E")
        state.discards[1].insert(0, "E")
        state.pending_discard["river_index"] = 1
        instance = game(state)
        after, _ = instance.step(choose(instance, env.ActionType.PENG))
        self.assertEqual(after.discards[1], ["E"])
        self.assertEqual(after.melds[0][0].tiles, ["E"] * 3)
        self.assertEqual(after.phase, "AFTER_PENG")

    def test_ming_and_an_kong_tail_draw_explicit_experiment(self):
        for kind in (env.ActionType.MING_GANG, env.ActionType.AN_GANG):
            if kind == env.ActionType.MING_GANG:
                state = scenario(discard="E")
            else:
                state = scenario("AFTER_DRAW", HAND + ["E"])
            state.wall.remove("P8")
            state.wall.append("P8")
            instance = game(state, experimental=True)
            after, event = instance.step(choose(instance, kind))
            self.assertEqual(len(after.hands[0]), 13)
            self.assertEqual(after.phase, "AFTER_" + kind.value)
            self.assertTrue(event["rules_config"]["experimental_no_rob_kong"])
            action = instance.legal_actions()[0]
            self.assertEqual(action.metadata, {"source": "tail"})
            final, _ = instance.step(action)
            self.assertEqual(final.hands[0][-1], "P8")
            self.assertEqual(len(final.wall), len(state.wall) - 1)
            self.assertEqual(len(final.hands[0]), 14)
            self.assertEqual(final.phase, "AFTER_DRAW")

    def test_default_kong_scope_blocks_declaration(self):
        instance = game(scenario(discard="E"))
        self.assertIn("rob_kong", instance.action_report().unresolved)
        before = instance.state.state_hash()
        with self.assertRaises(UnknownRuleError):
            instance.step(env.Action(0, env.ActionType.MING_GANG, tile="E", tiles=("E",) * 4))
        self.assertEqual(instance.state.state_hash(), before)

    def test_resolved_kong_tail_draw_needs_no_experimental_override(self):
        experimental = game(scenario(discard="E"), experimental=True)
        experimental.step(choose(experimental, env.ActionType.MING_GANG))
        # External verified scenario begins AFTER kong response resolution.
        instance = game(experimental.state)
        self.assertEqual(instance.legal_actions()[0].metadata, {"source": "tail"})
        instance.step(instance.legal_actions()[0])

    def test_tail_flower_stops_without_guessing_replacement(self):
        instance = game(scenario(discard="E"), experimental=True)
        instance.step(choose(instance, env.ActionType.MING_GANG))
        after, _ = instance.step(instance.legal_actions()[0])  # Full-wall order ends with F8.
        self.assertEqual(after.hands[0][-1], "F8")
        self.assertEqual(after.phase, "NEED_FLOWER_REPLACE")
        before = after.state_hash()
        with self.assertRaises(UnknownRuleError):
            instance.legal_actions()
        self.assertEqual(instance.state.state_hash(), before)

    def test_head_draw_and_wrong_source_rejected(self):
        instance = game(scenario("NEED_DRAW"))
        expected = instance.state.wall[0]
        before = instance.state.state_hash()
        with self.assertRaises(ValueError):
            instance.step(env.Action(0, env.ActionType.DRAW, metadata={"source": "tail"}))
        self.assertEqual(instance.state.state_hash(), before)
        after, _ = instance.step(instance.legal_actions()[0])
        self.assertEqual(after.hands[0][-1], expected)

    def test_atomic_post_validation_failure(self):
        class Broken(HuianEnvironment):
            @staticmethod
            def _apply(state, action):
                HuianEnvironment._apply(state, action)
                state.wall.pop()  # Inject tile loss AFTER mutation.
        instance = Broken()
        instance.set_state(scenario("NEED_DRAW"))
        token = instance.checkpoint()
        before = instance.state.state_hash()
        with self.assertRaises(ValueError):
            instance.step(instance.legal_actions()[0])
        self.assertEqual(instance.state.state_hash(), before)
        self.assertEqual(instance.events, [])
        self.assertEqual(instance.rollback(token).state_hash(), before)

    def test_set_state_failure_preserves_existing_history(self):
        instance = game(scenario("NEED_DRAW"))
        instance.step(instance.legal_actions()[0])
        before, events = instance.state.state_hash(), instance.events
        invalid = instance.state
        invalid.wall.append("M1")
        with self.assertRaises(ValueError):
            instance.set_state(invalid)
        self.assertEqual(instance.state.state_hash(), before)
        self.assertEqual(instance.events, events)

    def test_missing_tile_bad_pending_and_hand_size_rejected(self):
        for mutate in (
            lambda s: s.wall.pop(),
            lambda s: s.pending_discard.update(tile="P9"),
            lambda s: s.pending_discard.update(player=0),
            lambda s: s.pending_discard.update(river_index=-1),
            lambda s: s.wall.append(s.hands[0].pop()),
            lambda s: s.special_states.clear(),
        ):
            state = scenario()
            mutate(state)
            with self.assertRaises(ValueError):
                game(state)

    def test_gold_and_special_history_block_claims(self):
        for special in ("UNKNOWN", "YOUJIN", "DOUBLE_YOU", "TRIPLE_YOU"):
            state = scenario()
            state.special_states[1] = special
            instance = game(state)
            self.assertFalse(instance.action_report().known_actions)
            with self.assertRaises(UnknownRuleError):
                instance.legal_actions()

    def test_gold_in_acting_hand_blocks_without_using_wildcard_in_chi(self):
        state = scenario(hand=["P9"] + HAND[1:])
        instance = game(state)
        self.assertFalse(instance.action_report().known_actions)
        with self.assertRaises(UnknownRuleError):
            instance.legal_actions()

    def test_fifth_copy_rejected_even_when_total_remains_144(self):
        state = scenario()
        replacement = next(i for i, tile in enumerate(state.wall) if tile != "E")
        state.wall[replacement] = "E"
        self.assertEqual(len(state.physical_tiles()), 144)
        with self.assertRaises(ValueError):
            game(state)

    def test_ordinary_win_is_explicitly_blocked_pending_settlement(self):
        hand = ["M1", "M1", "M2", "M3", "M4", "M5", "M6", "M7",
                "P1", "P2", "P3", "S1", "S2", "S3", "E", "E", "E"]
        instance = game(scenario("AFTER_DRAW", hand))
        self.assertFalse(instance.action_report().known_actions)
        self.assertIn("win_declaration_and_settlement", instance.action_report().unresolved)

    def test_pass_known_and_startup_remains_unknown(self):
        instance = game(scenario())
        instance.step(env.Action(0, env.ActionType.PASS))
        self.assertEqual(instance.state.phase, "NEED_DRAW")
        instance.reset(seed=42)
        with self.assertRaises(UnknownRuleError):
            instance.legal_actions()

    def test_boundary_import_and_invalid_short_wall(self):
        for count in (0, 15, 16):
            state = scenario("NEED_DRAW")
            state.reserved_tiles.extend(state.wall[count:])
            state.wall = state.wall[:count]
            if count < 16:
                with self.assertRaises(ValueError):
                    game(state)
            else:
                instance = game(state)
                self.assertTrue(instance.is_terminal())
                self.assertEqual(instance.get_reward(), [0, 0])
                self.assertEqual(instance.state.wall_remaining(), 16)

    def test_no_legality_bypass_and_no_caller_mutation(self):
        instance = game(scenario("NEED_DRAW"))
        action = instance.legal_actions()[0]
        with self.assertRaises(ValueError):
            instance.step(action, strict=False)
        result, event = instance.step(action)
        expected = instance.state.state_hash()
        result.wall.clear()
        action.metadata["source"] = "tail"
        event["action"]["metadata"]["source"] = "tail"
        instance.events.clear()
        self.assertEqual(instance.state.state_hash(), expected)
        self.assertEqual(instance.events[0]["action"]["metadata"]["source"], "head")

    def test_seed_clone_rollback_and_replayed_actions(self):
        a, b = HuianEnvironment(), HuianEnvironment()
        self.assertEqual(a.reset(seed=71).state_hash(), b.reset(seed=71).state_hash())
        a.set_state(scenario())
        token = a.checkpoint()
        b = a.clone()
        action = choose(a, env.ActionType.CHI)
        a.step(action)
        action2 = a.legal_actions()[0]
        a.step(action2)
        for event in a.events:
            b.step(env.Action.from_dict(event["action"]))
        self.assertEqual(a.events, b.events)
        a.rollback(token)
        a.step(action)
        a.step(action2)
        self.assertEqual(a.events, b.events)
        with self.assertRaises(ValueError):
            a.rollback(token)
        fresh = a.checkpoint()
        a.reset(seed=1)
        a.checkpoint()
        with self.assertRaises(ValueError):
            a.rollback(fresh)

    def test_loop_detection_ignores_turn_counter(self):
        class NoProgress(HuianEnvironment):
            @staticmethod
            def _apply(state, action):
                pass
        instance = NoProgress()
        instance.set_state(scenario("NEED_DRAW"))
        before = instance.state.state_hash()
        with self.assertRaises(DeadLoopError):
            instance.step(instance.legal_actions()[0])
        self.assertEqual(instance.state.state_hash(), before)
        self.assertEqual(instance.events, [])

    def test_step_limit_and_zero_sum_terminal(self):
        instance = game(scenario(), max_steps=1)
        instance.step(choose(instance, env.ActionType.CHI))
        with self.assertRaises(DeadLoopError):
            instance.step(instance.legal_actions()[0])
        self.assertFalse(instance.is_terminal())
        state = instance.state
        state.phase, state.terminal, state.rewards = "TERMINAL", True, [44, -44]
        terminal = game(state)
        self.assertEqual(terminal.legal_actions(), [])
        self.assertEqual(terminal.get_reward(), [44, -44])
        state.rewards = [44, 0]
        with self.assertRaises(ValueError):
            terminal.set_state(state)


if __name__ == "__main__":
    unittest.main()
