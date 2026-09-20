import unittest

from workspace.ai import PublicRolloutDecisionDiagnostic
from workspace.simulator.rollout_diagnostics import summarize_rollout_diagnostics


def diagnostic(*, gate, changed, shanten=1, live_delta=0, type_delta=0,
               requested=24, completed=20, cutoffs=4, hand_index=3,
               margin=10):
    return PublicRolloutDecisionDiagnostic(
        decision_index=0,
        gate=gate,
        phase="AFTER_DRAW",
        baseline_action_type="DISCARD",
        baseline_tile="M1",
        chosen_action_type="DISCARD",
        chosen_tile="M2" if changed else "M1",
        changed_from_v010=changed,
        min_shanten=shanten,
        frontier_size=3,
        candidate_count=3,
        baseline_live_copies=12,
        baseline_effective_types=4,
        chosen_live_copies=12 + live_delta,
        chosen_effective_types=4 + type_delta,
        immediate_live_delta=live_delta,
        immediate_type_delta=type_delta,
        rollout_samples_requested=requested,
        rollout_samples_completed=completed,
        special_cutoffs=cutoffs,
        candidate_rollouts=(("M1", 1, completed, 1.0, 10.0),),
        wall_remaining=50,
        hand_index=hand_index,
        hands_remaining=8 - hand_index,
        score_margin_for_actor=margin,
        current_dealer_base=15,
    )


class RolloutDiagnosticSummaryTests(unittest.TestCase):
    def test_summary_reports_intervention_frequency_and_immediate_tradeoff(self):
        records = (
            {"seed": 1, "swapped": False,
             "diagnostic": diagnostic(
                 gate="searched_intervention", changed=True,
                 shanten=1, live_delta=-3, type_delta=-1, margin=20)},
            {"seed": 1, "swapped": False,
             "diagnostic": diagnostic(
                 gate="searched_same_as_v010", changed=False,
                 shanten=2, live_delta=0, type_delta=0, margin=-10)},
            {"seed": 1, "swapped": True,
             "diagnostic": diagnostic(
                 gate="gated_gold_in_hand", changed=False,
                 requested=0, completed=0, cutoffs=0)},
        )
        attempts = (
            {
                "status": "COMPLETED", "v014_score_delta": -30,
                "v014_deal_in_delta": 1, "unresolved": [],
            },
            {
                "status": "COMPLETED", "v014_score_delta": 10,
                "v014_deal_in_delta": 0, "unresolved": [],
            },
        )
        result = summarize_rollout_diagnostics(records, attempts=attempts)

        self.assertEqual(result["multi_discard_decisions"], 3)
        self.assertEqual(result["searched_decisions"], 2)
        self.assertEqual(result["interventions"], 1)
        self.assertEqual(result["intervention_rate_among_searched"], 0.5)
        self.assertEqual(
            result["gate_counts"]["gated_gold_in_hand"], 1)
        self.assertEqual(result["interventions_by_shanten"], {"1": 1})
        self.assertEqual(
            result["interventions_sacrificing_immediate_live"], 1)
        self.assertEqual(
            result["mean_immediate_live_delta_on_intervention"], -3)
        self.assertEqual(result["special_cutoff_rate"], 4 / 48)
        self.assertEqual(result["mean_v014_score_delta_per_match"], -10)
        self.assertEqual(result["mean_v014_deal_in_delta_per_match"], 0.5)
        self.assertEqual(len(result["intervention_examples"]), 1)

    def test_empty_summary_is_safe(self):
        result = summarize_rollout_diagnostics([], attempts=[])
        self.assertEqual(result["multi_discard_decisions"], 0)
        self.assertEqual(result["searched_decisions"], 0)
        self.assertEqual(result["interventions"], 0)
        self.assertEqual(result["intervention_rate_among_searched"], 0.0)
        self.assertEqual(result["special_cutoff_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
