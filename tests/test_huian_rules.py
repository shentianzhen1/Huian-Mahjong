import unittest
from copy import deepcopy

from huian import (HuContext, HuianRules, HuianRulesAdapter, KongKind, RulesConfig,
                   SanjindaoChoice, UnknownRuleError, WinSource)
from huian.rules import EvidenceStatus
from huian._legacy import env


HAND = ["M1", "M1", "M2", "M3", "M4", "M5", "M6", "M7",
        "P1", "P2", "P3", "S1", "S2", "S3", "E", "E", "E"]


class HuianRulesTests(unittest.TestCase):
    def setUp(self):
        self.rules = HuianRules()

    def test_normal_win_and_ting(self):
        self.assertTrue(self.rules.can_win(HAND))
        self.assertIn("E", [x["tile"] for x in self.rules.ting_tiles(HAND[:-1])])

    def test_hu_result_exposes_structure_without_fan(self):
        result = self.rules.analyze_hu(HAND)
        self.assertTrue(result.legal)
        self.assertEqual(result.win_source, WinSource.SELF_DRAW)
        self.assertTrue(result.decompositions)
        split = result.decompositions[0]
        self.assertEqual(len(split.pair), 2)
        self.assertEqual(len(split.groups), 5)
        self.assertEqual(split.gold_used, 0)
        self.assertFalse(hasattr(result, "fan"))

    def test_hu_result_marks_gold_positions_and_pinghu_room_gate(self):
        hand = HAND.copy()
        hand[4] = "P9"
        result = self.rules.analyze_hu(hand, gold_tile="P9")
        self.assertTrue(result.legal)
        self.assertTrue(any(split.gold_used == 1 for split in result.decompositions))
        self.assertFalse(self.rules.analyze_hu(
            hand, "P9", win_type="pinghu", winning_tile="E"
        ).legal)
        with self.assertRaises(ValueError):
            self.rules.analyze_hu(HAND, max_decompositions=0)

    def test_hu_result_truncation_is_detected_by_lookahead(self):
        complete = self.rules.analyze_hu(HAND, max_decompositions=64)
        limited = self.rules.analyze_hu(HAND, max_decompositions=1)
        self.assertEqual(len(limited.decompositions), 1)
        self.assertEqual(limited.may_be_truncated,
                         len(complete.decompositions) > 1)

    def test_single_and_double_gold_cannot_pinghu(self):
        for indices in ((4,), (0, 1)):
            hand = HAND.copy()
            for i in indices:
                hand[i] = "P9"
            self.assertTrue(self.rules.can_win(hand, "P9"))
            self.assertFalse(self.rules.can_win(
                hand, "P9", win_type="pinghu", winning_tile="E"
            ))

    def test_gold_cannot_be_consumed_by_chi(self):
        self.assertEqual(self.rules.meld_options(["M2", "M4"], "M3", "M2")["chi"], [])
        self.assertEqual(self.rules.meld_options(["M2", "M4"], "M3", "P9")["chi"],
                         [("M2", "M3", "M4")])

    def test_single_gold_pinghu_room_setting_and_ting(self):
        hand = HAND.copy()
        hand[4] = "P9"
        enabled = HuianRules(RulesConfig(single_gold_can_pinghu=True))
        self.assertFalse(self.rules.can_win(
            hand, "P9", win_type="pinghu", winning_tile="E"
        ))
        self.assertTrue(enabled.can_win(
            hand, "P9", win_type="pinghu", winning_tile="E"
        ))
        self.assertEqual(self.rules.ting_tiles(hand[:-1], "P9", win_type="pinghu"), [])
        waits = enabled.ting_tiles(hand[:-1], "P9", win_type="pinghu")
        self.assertIn("E", [entry["tile"] for entry in waits])
        contextual = enabled.ting_tiles(
            hand[:-1], "P9", win_context=HuContext(WinSource.DISCARD)
        )
        self.assertIn("E", [entry["tile"] for entry in contextual])
        hand[3] = "P9"
        self.assertFalse(enabled.can_win(
            hand, "P9", win_type="pinghu", winning_tile="E"
        ))

    def test_discard_source_requires_tile_and_discarded_gold_never_hu(self):
        enabled = HuianRules(RulesConfig(single_gold_can_pinghu=True))
        hand = HAND.copy()
        hand[4] = "P9"
        with self.assertRaises(ValueError):
            enabled.can_win(hand, "P9", win_type="pinghu")
        self.assertFalse(enabled.can_win(
            hand, "P9", win_context=HuContext(WinSource.DISCARD, "P9")
        ))

    def test_kong_tail_context_classifies_all_three_kong_kinds_as_gang_hu(self):
        for kind in KongKind:
            result = self.rules.analyze_hu(
                HAND, win_context=HuContext(WinSource.KONG_TAIL_DRAW, "E", kind)
            )
            self.assertTrue(result.legal)
            self.assertTrue(result.is_gang_hu)
            self.assertEqual(result.kong_kind, kind)
        with self.assertRaises(ValueError):
            HuContext(WinSource.KONG_TAIL_DRAW, "E")
        with self.assertRaises(ValueError):
            HuContext(WinSource.SELF_DRAW, "E", KongKind.MING_GANG)
        with self.assertRaises(ValueError):
            HuContext.from_draw_metadata({
                "source": "wall_tail", "kong_kind": "MING_GANG"
            })
        with self.assertRaises(ValueError):
            HuContext.from_draw_metadata({
                "source": "wall_head", "drawn_tile": "E", "kong_kind": "MING_GANG"
            })

    def test_sanjindao_is_shape_independent_and_optional(self):
        hand = ["P9", "P9", "P9", "M1"]
        result = self.rules.sanjindao_decision(hand, "P9")
        self.assertTrue(result.eligible)
        self.assertEqual(result.gold_count, 3)
        self.assertEqual(result.choices, (
            SanjindaoChoice.DECLARE_SANJINDAO,
            SanjindaoChoice.CONTINUE_PLAY,
        ))
        self.assertFalse(self.rules.sanjindao_decision(["P9"] * 2, "P9").eligible)

    def test_single_gold_setting_rejects_non_boolean(self):
        for invalid in (None, 0, 1, "false", "true"):
            with self.assertRaises(ValueError):
                RulesConfig(single_gold_can_pinghu=invalid)

    def test_discarded_gold_cannot_be_claimed_for_meld(self):
        result = self.rules.meld_options(["M2"] * 3, "M2", "M2")
        self.assertEqual(result, {"chi": [], "peng": False, "ming_gang": False})
        self.assertEqual(self.rules.concealed_kongs(["M2"] * 4, "M2"), ())

    def test_normal_melds(self):
        result = self.rules.meld_options(["M2"] * 3, "M2", "P9")
        self.assertTrue(result["peng"])
        self.assertTrue(result["ming_gang"])
        self.assertEqual(self.rules.concealed_kongs(["E"] * 4, "P9"), ("E",))

    def test_fifth_copy_and_flowers_rejected(self):
        for hand in (["M1"] * 5, ["F1"]):
            with self.assertRaises(ValueError):
                self.rules.can_win(hand)
        with self.assertRaises(ValueError):
            self.rules.meld_options(["M1"] * 4, "M1")

    def test_unknown_special_wins_are_not_false(self):
        for win_type in ("sanjindao", "youjin", "double_you", "triple_you", "qianggang"):
            with self.assertRaises(UnknownRuleError):
                self.rules.can_win(HAND, win_type=win_type)
        with self.assertRaises(UnknownRuleError):
            self.rules.can_win(["P9"] * 3 + ["M1"], "P9", win_type="pinghu",
                               winning_tile="M1")

    def test_visible_fifth_copy_rejected(self):
        with self.assertRaises(ValueError):
            self.rules.ting_tiles(["M1"] * 3, visible_tiles=["M1"] * 2)

    def test_fan_is_not_silently_aggregated(self):
        with self.assertRaises(UnknownRuleError):
            self.rules.calculate_fan(flowers=["F1", "F2", "F3", "F4"])


class SettlementTests(unittest.TestCase):
    def setUp(self):
        self.rules = HuianRules(RulesConfig("current_dealer_plus_winner_v1"))

    def test_screenshot_a_and_b(self):
        # Transcribed from RULE_STATUS.md; source PNGs are under references/settlement_examples.
        for base, fan, multiplier, expected in ((10, 12, 2, 44), (15, 7, 4, 88)):
            for winner in (0, 1):
                result = self.rules.settle(winner=winner, current_dealer_base=base,
                                           winner_fan=fan, multiplier=multiplier)
                self.assertEqual(result.rewards[winner], expected)
                self.assertEqual(sum(result.rewards), 0)
                self.assertEqual(result.status, EvidenceStatus.HIGH_CONFIDENCE)

    def test_explicit_hypothesis_and_multiplier_required(self):
        kwargs = dict(winner=0, current_dealer_base=10, winner_fan=12)
        with self.assertRaises(UnknownRuleError):
            HuianRules().settle(**kwargs, multiplier=2)
        with self.assertRaises(UnknownRuleError):
            self.rules.settle(**kwargs)

    def test_invalid_inputs(self):
        for value in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                self.rules.settle(winner=0, current_dealer_base=10,
                                  winner_fan=value, multiplier=2)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = HuianRulesAdapter()

    def post_claim(self):
        state = env.GameState(gold_tile="P9", phase="AFTER_CHI")
        state.hands[0] = HAND[:2] + HAND[5:]
        state.melds[0] = [env.Meld("CHI", ["M2", "M3", "M4"], 1)]
        return state

    def test_discard_only_after_chi_or_peng(self):
        for phase in ("AFTER_CHI", "AFTER_PENG"):
            state = self.post_claim()
            state.phase = phase
            if phase == "AFTER_PENG":
                state.melds[0] = [env.Meld("PENG", ["P8"] * 3, 1)]
            actions = self.adapter.legal_actions(state)
            self.assertTrue(actions)
            self.assertTrue(all(a.type == env.ActionType.DISCARD for a in actions))

    def test_legal_step_rollback_clone(self):
        game = env.QuanzhouEnvironment(self.adapter)
        game.set_state(self.post_claim())
        original = game.state.state_hash()
        token = game.checkpoint()
        clone = game.clone()
        action = game.legal_actions()[0]
        game.step(action)
        self.assertEqual(clone.state.state_hash(), original)
        game.rollback(token)
        self.assertEqual(game.state.state_hash(), original)

    def test_illegal_step_does_not_mutate(self):
        game = env.QuanzhouEnvironment(self.adapter)
        game.set_state(self.post_claim())
        before = deepcopy(game.state.canonical_dict())
        with self.assertRaises(ValueError):
            game.step(env.Action(0, env.ActionType.DRAW))
        self.assertEqual(game.state.canonical_dict(), before)
        self.assertEqual(game.events, [])

    def test_unsupported_phases_block_instead_of_looping(self):
        for phase in ("READY", "AFTER_DRAW", "AFTER_DISCARD", "PASS", "YOUJIN"):
            state = self.post_claim()
            state.phase = phase
            with self.assertRaises(UnknownRuleError):
                self.adapter.legal_actions(state)

    def test_gold_state_blocks_partial_action_set(self):
        state = self.post_claim()
        state.hands[0][0] = "P9"
        with self.assertRaises(UnknownRuleError):
            self.adapter.legal_actions(state)

    def test_global_fifth_copy_and_non_zero_sum_rejected(self):
        state = self.post_claim()
        state.wall = ["E"] * 2
        with self.assertRaises(ValueError):
            self.adapter.validate_state(state)
        state = self.post_claim()
        state.rewards = [44, 0]
        with self.assertRaises(ValueError):
            self.adapter.reward(state)

    def test_fixed_seed_wall_reproducibility(self):
        a, b = env.QuanzhouEnvironment(self.adapter), env.QuanzhouEnvironment(self.adapter)
        self.assertEqual(a.reset(seed=42).state_hash(), b.reset(seed=42).state_hash())
        self.assertEqual(len(a.state.wall), 144)

    def test_negative_wall_count_rejected(self):
        state = self.post_claim()
        state.wall_remaining = lambda: -1
        with self.assertRaises(ValueError):
            self.adapter.validate_state(state)

    def test_invalid_meld_rejected(self):
        state = self.post_claim()
        state.melds[0][0].tiles = ["M2", "M3", "M5"]
        with self.assertRaises(ValueError):
            self.adapter.legal_actions(state)

    def test_legacy_action_identity(self):
        from qzenv import Action, ActionType
        self.assertTrue(self.adapter.is_legal(self.post_claim(), Action(0, ActionType.DISCARD, "M1")))


if __name__ == "__main__":
    unittest.main()
