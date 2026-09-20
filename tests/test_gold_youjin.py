import unittest
from types import SimpleNamespace
from unittest.mock import patch

from huian._legacy import env
from workspace.ai import (
    GoldYoujinShadowAgent,
    GoldYoujinShadowDiagnostic,
    MeldAwareShantenAgent,
    PlayerObservation,
    YoujinDiscardPotential,
    YoujinTenpaiCandidateAgent,
    YoujinTenpaiCandidateAgent,
    estimate_youjin_discard_potentials,
    youjin_meld_deficit,
)
from workspace.simulator.gold_youjin_shadow import summarize_gold_youjin_shadow


YOUJIN_READY = [
    "M1", "M2", "M3",
    "M4", "M5", "M6",
    "P1", "P2", "P3",
    "S1", "S2", "S3",
    "E", "E", "E",
    "P9",
]


def observation(hand, gold="P9"):
    return PlayerObservation(
        0, tuple(hand), gold, "AFTER_DRAW", 0, 40,
        ((), ()), ((), ()), ((), ()),
    )


def discards(hand):
    return [
        env.Action(0, env.ActionType.DISCARD, tile=tile)
        for tile in sorted(set(hand))
    ]


class GoldYoujinPotentialTests(unittest.TestCase):
    def test_confirmed_youjin_entry_is_detected_for_discard(self):
        view = observation(YOUJIN_READY + ["N"])
        result = estimate_youjin_discard_potentials(view, ("N",))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].discard, "N")
        self.assertTrue(result[0].immediate_entry)
        self.assertEqual(result[0].meld_deficit, 0)
        self.assertGreaterEqual(result[0].future_entry_live_copies, 0)
        self.assertEqual(
            result[0].future_entry_types, len(result[0].enabling_draws))

    def test_youjin_meld_deficit_zero_matches_confirmed_ready_shape(self):
        self.assertEqual(
            youjin_meld_deficit(YOUJIN_READY, "P9"), 0
        )

    def test_youjin_meld_deficit_detects_one_slot_gap(self):
        one_gap = list(YOUJIN_READY)
        one_gap.remove("M3")
        one_gap.append("N")
        self.assertEqual(
            youjin_meld_deficit(one_gap, "P9"), 1
        )

    def test_youjin_meld_deficit_requires_roaming_gold(self):
        no_gold = [tile for tile in YOUJIN_READY if tile != "P9"]
        no_gold.append("N")
        self.assertIsNone(youjin_meld_deficit(no_gold, "P9"))

    def test_shadow_agent_never_changes_v010_action(self):
        hand = YOUJIN_READY + ["N"]
        view = observation(hand)
        actions = discards(hand)
        expected = MeldAwareShantenAgent(
            seed=11, template_samples=32).choose_decision(view, actions)
        other = next(tile for tile in sorted(set(hand))
                     if tile != expected.action.tile)

        frontier = (
            SimpleNamespace(
                discard=expected.action.tile, shanten=1,
                total_live_copies=10, effective_tiles=(1, 2, 3)),
            SimpleNamespace(
                discard=other, shanten=1,
                total_live_copies=9, effective_tiles=(1, 2, 3)),
        )
        potentials = (
            YoujinDiscardPotential(
                expected.action.tile, False, 2, 1, (("M9", 2),), 1,
                meld_deficit=2),
            YoujinDiscardPotential(
                other, False, 3, 2,
                (("M1", 2), ("M2", 1)), 1,
                meld_deficit=1),
        )
        agent = GoldYoujinShadowAgent(seed=11, template_samples=32)
        with patch(
                "workspace.ai.gold_youjin.min_shanten_discards",
                return_value=frontier), patch(
                "workspace.ai.gold_youjin.estimate_youjin_discard_potentials",
                return_value=potentials):
            actual = agent.choose_decision(view, actions)

        self.assertEqual(actual.action, expected.action)
        self.assertIn("gold_youjin_shadow keeps V0.10 action", actual.reason)
        self.assertEqual(len(agent.gold_diagnostics), 1)
        record = agent.gold_diagnostics[0]
        self.assertTrue(record.would_change_v010)
        self.assertTrue(record.signal_differentiated)
        self.assertEqual(record.structural_choice_tile, other)
        self.assertEqual(record.meld_deficit_delta, -1)
        self.assertEqual(record.immediate_live_delta, -1)
        self.assertEqual(record.immediate_type_delta, 0)


    def test_shadow_preserves_v010_when_meld_deficit_is_equal(self):
        hand = YOUJIN_READY + ["N"]
        view = observation(hand)
        actions = discards(hand)
        expected = MeldAwareShantenAgent(
            seed=13, template_samples=32).choose_decision(view, actions)
        other = next(tile for tile in sorted(set(hand))
                     if tile != expected.action.tile)

        frontier = (
            SimpleNamespace(
                discard=expected.action.tile, shanten=1,
                total_live_copies=10, effective_tiles=(1, 2, 3)),
            SimpleNamespace(
                discard=other, shanten=1,
                total_live_copies=4, effective_tiles=(1,)),
        )
        potentials = (
            YoujinDiscardPotential(
                expected.action.tile, False, 0, 0, (), 1,
                meld_deficit=2),
            YoujinDiscardPotential(
                other, False, 0, 0, (), 1,
                meld_deficit=2),
        )
        agent = GoldYoujinShadowAgent(
            seed=13, template_samples=32, include_future=False)
        with patch(
                "workspace.ai.gold_youjin.min_shanten_discards",
                return_value=frontier), patch(
                "workspace.ai.gold_youjin.estimate_youjin_discard_potentials",
                return_value=potentials):
            actual = agent.choose_decision(view, actions)

        self.assertEqual(actual.action, expected.action)
        self.assertEqual(agent.gold_diagnostics[-1].structural_choice_tile,
                         expected.action.tile)
        self.assertFalse(agent.gold_diagnostics[-1].would_change_v010)

class YoujinTenpaiCandidateTests(unittest.TestCase):
    def test_v015b_changes_only_inside_narrow_tenpai_gate(self):
        hand = YOUJIN_READY + ["N"]
        view = observation(hand)
        actions = discards(hand)
        baseline = MeldAwareShantenAgent(
            seed=21, template_samples=32).choose_decision(view, actions)
        other = next(tile for tile in sorted(set(hand))
                     if tile != baseline.action.tile)

        frontier = (
            SimpleNamespace(
                discard=baseline.action.tile, shanten=0,
                total_live_copies=8, effective_tiles=(1, 2, 3)),
            SimpleNamespace(
                discard=other, shanten=0,
                total_live_copies=7, effective_tiles=(1, 2, 3)),
        )
        potentials = (
            YoujinDiscardPotential(
                baseline.action.tile, False, 0, 0, (), 1,
                meld_deficit=2),
            YoujinDiscardPotential(
                other, False, 0, 0, (), 1,
                meld_deficit=1),
        )
        agent = YoujinTenpaiCandidateAgent(seed=21, template_samples=32)
        with patch(
                "workspace.ai.gold_youjin.min_shanten_discards",
                return_value=frontier), patch(
                "workspace.ai.gold_youjin.estimate_youjin_discard_potentials",
                return_value=potentials):
            actual = agent.choose_decision(view, actions)

        self.assertEqual(actual.action.tile, other)
        self.assertIn("V0.15b experimental youjin_tenpai_candidate", actual.reason)

    def test_v015b_keeps_v010_when_live_loss_exceeds_one(self):
        hand = YOUJIN_READY + ["N"]
        view = observation(hand)
        actions = discards(hand)
        baseline = MeldAwareShantenAgent(
            seed=22, template_samples=32).choose_decision(view, actions)
        other = next(tile for tile in sorted(set(hand))
                     if tile != baseline.action.tile)

        frontier = (
            SimpleNamespace(
                discard=baseline.action.tile, shanten=0,
                total_live_copies=8, effective_tiles=(1, 2, 3)),
            SimpleNamespace(
                discard=other, shanten=0,
                total_live_copies=6, effective_tiles=(1, 2, 3)),
        )
        potentials = (
            YoujinDiscardPotential(
                baseline.action.tile, False, 0, 0, (), 1,
                meld_deficit=2),
            YoujinDiscardPotential(
                other, False, 0, 0, (), 1,
                meld_deficit=1),
        )
        agent = YoujinTenpaiCandidateAgent(seed=22, template_samples=32)
        with patch(
                "workspace.ai.gold_youjin.min_shanten_discards",
                return_value=frontier), patch(
                "workspace.ai.gold_youjin.estimate_youjin_discard_potentials",
                return_value=potentials):
            actual = agent.choose_decision(view, actions)

        self.assertEqual(actual.action, baseline.action)


class GoldYoujinShadowSummaryTests(unittest.TestCase):
    def test_summary_counts_differentiated_shadow_changes(self):
        record = GoldYoujinShadowDiagnostic(
            decision_index=0,
            phase="AFTER_DRAW",
            gold_count=1,
            shanten=1,
            min_shanten_frontier_size=3,
            baseline_tile="M1",
            structural_choice_tile="M2",
            would_change_v010=True,
            signal_differentiated=True,
            baseline_immediate_entry=False,
            best_immediate_entry=True,
            baseline_future_live_copies=2,
            best_future_live_copies=7,
            future_live_delta=5,
            baseline_future_types=1,
            best_future_types=3,
            future_type_delta=2,
            baseline_meld_deficit=2,
            best_meld_deficit=0,
            meld_deficit_delta=-2,
            baseline_live_copies=10,
            best_live_copies=9,
            immediate_live_delta=-1,
            baseline_effective_types=3,
            best_effective_types=3,
            immediate_type_delta=0,
            hand_index=5,
            score_margin_for_actor=-50,
            wall_remaining=40,
        )
        result = summarize_gold_youjin_shadow(
            ({"seed": 1, "swapped": False, "diagnostic": record},),
            attempts=({
                "status": "COMPLETED",
                "unresolved": [],
            },),
        )
        self.assertEqual(result["gold_discard_decisions"], 1)
        self.assertEqual(result["multi_candidate_min_shanten_decisions"], 1)
        self.assertEqual(result["signal_differentiated_frontiers"], 1)
        self.assertEqual(result["shadow_would_change_v010"], 1)
        self.assertEqual(result["best_immediate_youjin_entries"], 1)
        self.assertEqual(result["mean_future_youjin_live_delta_on_change"], 5)
        self.assertEqual(result["mean_meld_deficit_delta_on_change"], -2)
        self.assertEqual(result["mean_immediate_live_delta_on_change"], -1)
        self.assertEqual(result["changes_by_match_margin"], {"trailing": 1})


if __name__ == "__main__":
    unittest.main()
