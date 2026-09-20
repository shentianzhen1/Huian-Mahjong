import unittest
from types import SimpleNamespace
from unittest.mock import patch

from huian._legacy import env
from workspace.ai import (
    ConstrainedGoldYoujinAgent,
    AgentDecision,
    ConstrainedGoldYoujinAgent,
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


class ConstrainedGoldYoujinAgentTests(unittest.TestCase):
    def test_v015_can_trade_one_live_copy_for_immediate_youjin_without_type_loss(self):
        hand = YOUJIN_READY + ["N"]
        view = observation(hand)
        actions = discards(hand)
        baseline = MeldAwareShantenAgent(
            seed=21, template_samples=32).choose_decision(view, actions)
        other = next(tile for tile in sorted(set(hand))
                     if tile not in (baseline.action.tile, "P9"))

        frontier = (
            SimpleNamespace(
                discard=baseline.action.tile, shanten=1,
                total_live_copies=10, effective_tiles=(1, 2, 3)),
            SimpleNamespace(
                discard=other, shanten=1,
                total_live_copies=9, effective_tiles=(1, 2, 3)),
        )
        potentials = (
            YoujinDiscardPotential(
                baseline.action.tile, False, 2, 1, (("M9", 2),), 1),
            YoujinDiscardPotential(
                other, True, 3, 1, (("M9", 3),), 1),
        )
        agent = ConstrainedGoldYoujinAgent(seed=21)
        with patch(
                "workspace.ai.gold_youjin.min_shanten_discards",
                return_value=frontier), patch(
                "workspace.ai.gold_youjin.estimate_youjin_discard_potentials",
                return_value=potentials):
            actual = agent.choose_decision(view, actions)

        self.assertEqual(actual.action.tile, other)
        self.assertIn("constrained_gold_youjin_v0.15_candidate", actual.reason)
        self.assertEqual(len(agent.v015_diagnostics), 1)
        diag = agent.v015_diagnostics[0]
        self.assertTrue(diag.changed_from_v010)
        self.assertEqual(diag.reason_gate, "immediate_youjin_entry")
        self.assertEqual(diag.immediate_live_delta, -1)
        self.assertEqual(diag.immediate_type_delta, 0)

    def test_v015_refuses_two_live_copy_loss(self):
        hand = YOUJIN_READY + ["N"]
        view = observation(hand)
        actions = discards(hand)
        baseline = MeldAwareShantenAgent(
            seed=22, template_samples=32).choose_decision(view, actions)
        other = next(tile for tile in sorted(set(hand))
                     if tile not in (baseline.action.tile, "P9"))

        frontier = (
            SimpleNamespace(
                discard=baseline.action.tile, shanten=1,
                total_live_copies=10, effective_tiles=(1, 2, 3)),
            SimpleNamespace(
                discard=other, shanten=1,
                total_live_copies=8, effective_tiles=(1, 2, 3)),
        )
        baseline_only = (
            YoujinDiscardPotential(
                baseline.action.tile, False, 0, 0, (), 1),
        )
        with patch(
                "workspace.ai.gold_youjin.min_shanten_discards",
                return_value=frontier), patch(
                "workspace.ai.gold_youjin.estimate_youjin_discard_potentials",
                return_value=baseline_only) as estimate:
            actual = ConstrainedGoldYoujinAgent(
                seed=22, max_live_loss=1).choose_decision(view, actions)

        self.assertEqual(actual.action, baseline.action)
        estimate.assert_called_once()
        called_tiles = estimate.call_args.args[1]
        self.assertNotIn(other, called_tiles)

    def test_v015_future_signal_requires_material_live_and_type_gain(self):
        hand = YOUJIN_READY + ["N"]
        view = observation(hand)
        actions = discards(hand)
        baseline = MeldAwareShantenAgent(
            seed=23, template_samples=32).choose_decision(view, actions)
        other = next(tile for tile in sorted(set(hand))
                     if tile not in (baseline.action.tile, "P9"))

        frontier = (
            SimpleNamespace(
                discard=baseline.action.tile, shanten=2,
                total_live_copies=12, effective_tiles=(1, 2, 3, 4)),
            SimpleNamespace(
                discard=other, shanten=2,
                total_live_copies=12, effective_tiles=(1, 2, 3, 4)),
        )
        weak = (
            YoujinDiscardPotential(
                baseline.action.tile, False, 2, 1, (("M9", 2),), 1),
            YoujinDiscardPotential(
                other, False, 5, 2, (("M7", 2), ("M8", 3)), 1),
        )
        agent = ConstrainedGoldYoujinAgent(
            seed=23, min_future_live_gain=4, min_future_type_gain=1)
        with patch(
                "workspace.ai.gold_youjin.min_shanten_discards",
                return_value=frontier), patch(
                "workspace.ai.gold_youjin.estimate_youjin_discard_potentials",
                return_value=weak):
            actual = agent.choose_decision(view, actions)
        self.assertEqual(actual.action, baseline.action)
        self.assertEqual(agent.v015_diagnostics[0].reason_gate,
                         "no_material_youjin_gain")


class ConstrainedGoldYoujinAgentTests(unittest.TestCase):
    def _run_candidate(
            self, *, baseline_tile="N", candidate_tile="E",
            baseline_live=10, candidate_live=9,
            baseline_types=3, candidate_types=3,
            baseline_potential=None, candidate_potential=None):
        hand = YOUJIN_READY + ["N"]
        view = observation(hand)
        actions = discards(hand)
        baseline = AgentDecision(
            env.Action(0, env.ActionType.DISCARD, tile=baseline_tile),
            "v0.10 baseline",
        )
        frontier = (
            SimpleNamespace(
                discard=baseline_tile,
                shanten=1,
                total_live_copies=baseline_live,
                effective_tiles=tuple(range(baseline_types)),
            ),
            SimpleNamespace(
                discard=candidate_tile,
                shanten=1,
                total_live_copies=candidate_live,
                effective_tiles=tuple(range(candidate_types)),
            ),
        )
        if baseline_potential is None:
            baseline_potential = YoujinDiscardPotential(
                baseline_tile, False, 0, 0, (), 1)
        if candidate_potential is None:
            candidate_potential = YoujinDiscardPotential(
                candidate_tile, True, 0, 0, (), 1)

        agent = ConstrainedGoldYoujinAgent(seed=17, template_samples=32)
        with patch.object(
                MeldAwareShantenAgent, "choose_decision",
                return_value=baseline), patch(
                "workspace.ai.gold_youjin.min_shanten_discards",
                return_value=frontier), patch(
                "workspace.ai.gold_youjin.estimate_youjin_discard_potentials",
                return_value=(baseline_potential, candidate_potential)):
            actual = agent.choose_decision(view, actions)
        return agent, actual, baseline

    def test_immediate_youjin_may_trade_at_most_one_live_copy(self):
        agent, actual, baseline = self._run_candidate(
            baseline_live=10, candidate_live=9,
            baseline_types=3, candidate_types=3,
        )
        self.assertNotEqual(actual.action, baseline.action)
        self.assertEqual(actual.action.tile, "E")
        self.assertIn("immediate_youjin_entry", actual.reason)
        record = agent.v015_diagnostics[-1]
        self.assertTrue(record.changed_from_v010)
        self.assertEqual(record.immediate_live_delta, -1)
        self.assertEqual(record.immediate_type_delta, 0)

    def test_candidate_cannot_trade_two_live_copies_for_youjin(self):
        agent, actual, baseline = self._run_candidate(
            baseline_live=10, candidate_live=8,
            baseline_types=3, candidate_types=3,
        )
        self.assertEqual(actual.action, baseline.action)
        self.assertTrue(all(
            not record.changed_from_v010 for record in agent.v015_diagnostics
        ))

    def test_candidate_cannot_reduce_effective_tile_types(self):
        agent, actual, baseline = self._run_candidate(
            baseline_live=10, candidate_live=10,
            baseline_types=3, candidate_types=2,
        )
        self.assertEqual(actual.action, baseline.action)
        self.assertTrue(all(
            not record.changed_from_v010 for record in agent.v015_diagnostics
        ))

    def test_material_future_youjin_gain_can_override_without_immediate_entry(self):
        baseline_potential = YoujinDiscardPotential(
            "N", False, 2, 1, (("M9", 2),), 1)
        candidate_potential = YoujinDiscardPotential(
            "E", False, 7, 3,
            (("M1", 3), ("M2", 2), ("M3", 2)), 1)
        agent, actual, baseline = self._run_candidate(
            baseline_live=10,
            candidate_live=10,
            baseline_types=3,
            candidate_types=3,
            baseline_potential=baseline_potential,
            candidate_potential=candidate_potential,
        )
        self.assertNotEqual(actual.action, baseline.action)
        self.assertEqual(actual.action.tile, "E")
        self.assertIn("future_youjin_gain", actual.reason)
        record = agent.v015_diagnostics[-1]
        self.assertEqual(record.future_live_delta, 5)
        self.assertEqual(record.future_type_delta, 2)

    def test_small_future_gain_does_not_override(self):
        baseline_potential = YoujinDiscardPotential(
            "N", False, 2, 1, (("M9", 2),), 1)
        candidate_potential = YoujinDiscardPotential(
            "E", False, 5, 2, (("M1", 3), ("M2", 2)), 1)
        agent, actual, baseline = self._run_candidate(
            baseline_potential=baseline_potential,
            candidate_potential=candidate_potential,
        )
        self.assertEqual(actual.action, baseline.action)
        self.assertEqual(
            agent.v015_diagnostics[-1].reason_gate,
            "no_material_youjin_gain",
        )


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
