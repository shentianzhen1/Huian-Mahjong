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
    estimate_youjin_discard_potentials,
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
        self.assertGreaterEqual(result[0].future_entry_live_copies, 0)
        self.assertEqual(
            result[0].future_entry_types, len(result[0].enabling_draws))

    def test_shadow_agent_never_changes_v010_action(self):
        hand = YOUJIN_READY + ["N"]
        view = observation(hand)
        actions = discards(hand)
        expected = MeldAwareShantenAgent(
            seed=11, template_samples=32).choose_decision(view, actions)
        other = next(tile for tile in sorted(set(hand))
                     if tile != expected.action.tile)

        ties = (
            SimpleNamespace(
                discard=expected.action.tile, shanten=1,
                total_live_copies=10, effective_tiles=(1, 2)),
            SimpleNamespace(
                discard=other, shanten=1,
                total_live_copies=10, effective_tiles=(1, 2)),
        )
        potentials = (
            YoujinDiscardPotential(
                expected.action.tile, False, 2, 1, (("M9", 2),), 1),
            YoujinDiscardPotential(
                other, True, 8, 3,
                (("M1", 3), ("M2", 3), ("M3", 2)), 1),
        )
        agent = GoldYoujinShadowAgent(seed=11, template_samples=32)
        with patch(
                "workspace.ai.gold_youjin.best_offense_ties",
                return_value=ties), patch(
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
        self.assertEqual(record.future_live_delta, 6)


class GoldYoujinShadowSummaryTests(unittest.TestCase):
    def test_summary_counts_differentiated_shadow_changes(self):
        record = GoldYoujinShadowDiagnostic(
            decision_index=0,
            phase="AFTER_DRAW",
            gold_count=1,
            shanten=1,
            exact_offense_tie_count=2,
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
        self.assertEqual(result["exact_offense_tie_decisions"], 1)
        self.assertEqual(result["signal_differentiated_ties"], 1)
        self.assertEqual(result["shadow_would_change_v010"], 1)
        self.assertEqual(result["best_immediate_youjin_entries"], 1)
        self.assertEqual(result["mean_future_youjin_live_delta_on_change"], 5)
        self.assertEqual(result["changes_by_match_margin"], {"trailing": 1})


if __name__ == "__main__":
    unittest.main()
