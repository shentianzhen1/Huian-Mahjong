import unittest
from types import SimpleNamespace

from workspace.simulator import run_paired_real_matches


def factory_a(seed=None):
    return object()


def factory_b(seed=None):
    return object()


class FakeResult:
    def __init__(self, *, scores=(1000, 1000), status="COMPLETED",
                 deal_ins=(0, 0), sources=None, unresolved=(), hands=8):
        self.status = status
        self.final_scores = tuple(scores)
        self.unresolved = tuple(unresolved)
        self.progress = SimpleNamespace(hand_index=hands)
        self._deal_ins = tuple(deal_ins)
        self.win_source_counts = dict(sources or {})

    @property
    def complete(self):
        return self.status == "COMPLETED"

    def deal_in_count_for(self, seat):
        return self._deal_ins[seat]


class PairedMatchEvaluationTests(unittest.TestCase):
    def test_agent_identity_follows_factory_across_swapped_seats(self):
        def runner(seed, *, agent_factories, **kwargs):
            original = agent_factories[0] is factory_a
            if original:
                return FakeResult(
                    scores=(1100, 900), deal_ins=(0, 2),
                    sources={"discard": 3, "self_draw": 2})
            return FakeResult(
                scores=(950, 1050), deal_ins=(1, 0),
                sources={"discard": 2})

        report = run_paired_real_matches(
            [7], agent_factories=(factory_a, factory_b), match_runner=runner)
        self.assertEqual(report.agent_names, ("factory_a", "factory_b"))
        self.assertEqual((report.total_pairs, report.completed_pairs), (1, 1))
        self.assertEqual(report.match_wins_by_agent, {"A": 2, "B": 0})
        self.assertEqual(report.ties, 0)
        self.assertEqual(report.average_final_score_by_agent, {"A": 1075.0, "B": 925.0})
        self.assertEqual(report.average_score_delta_a_minus_b, 150.0)
        self.assertEqual(report.paired_score_delta_mean, 150.0)
        self.assertIsNone(report.paired_score_delta_sd)
        self.assertIsNone(report.paired_score_delta_se)
        self.assertIsNone(report.paired_score_delta_ci95_low)
        self.assertIsNone(report.paired_score_delta_ci95_high)
        self.assertEqual(report.paired_deal_in_delta_mean, -1.5)
        self.assertEqual(report.deal_ins_by_agent, {"A": 0, "B": 3})
        self.assertEqual(report.average_deal_ins_per_match_by_agent, {"A": 0.0, "B": 1.5})
        self.assertEqual(report.win_source_counts, {"discard": 5, "self_draw": 2})
        self.assertEqual(len(report.per_match), 2)
        self.assertEqual(report.per_match[1].agent_scores, (1050, 950))
        self.assertEqual(report.per_match[1].deal_ins_by_agent, (0, 1))

    def test_incomplete_pair_is_counted_but_excluded_from_comparison(self):
        calls = 0

        def runner(seed, *, agent_factories, **kwargs):
            nonlocal calls
            calls += 1
            if agent_factories[0] is factory_a:
                return FakeResult(scores=(1050, 950), deal_ins=(0, 1))
            return FakeResult(
                status="STOPPED_UNKNOWN", scores=(1000, 1000), hands=3,
                unresolved=("QIANGJIN_SETTLEMENT_UNKNOWN",))

        report = run_paired_real_matches(
            [3], agent_factories=(factory_a, factory_b), match_runner=runner)
        self.assertEqual(calls, 2)
        self.assertEqual(report.completed_matches, 1)
        self.assertEqual(report.stopped_matches, 1)
        self.assertEqual(report.completed_pairs, 0)
        self.assertEqual(report.incomplete_pairs, 1)
        self.assertEqual(report.average_final_score_by_agent, {"A": None, "B": None})
        self.assertIsNone(report.average_score_delta_a_minus_b)
        self.assertIsNone(report.paired_score_delta_mean)
        self.assertIsNone(report.paired_score_delta_sd)
        self.assertIsNone(report.paired_score_delta_se)
        self.assertIsNone(report.paired_score_delta_ci95_low)
        self.assertIsNone(report.paired_score_delta_ci95_high)
        self.assertIsNone(report.paired_deal_in_delta_mean)
        self.assertEqual(report.deal_ins_by_agent, {"A": 0, "B": 0})
        self.assertEqual(report.unknown_reasons, {"QIANGJIN_SETTLEMENT_UNKNOWN": 1})

    def test_paired_uncertainty_uses_seed_pair_deltas(self):
        calls = {}

        def runner(seed, *, agent_factories, **kwargs):
            swapped = agent_factories[0] is factory_b
            key = (seed, swapped)
            calls[key] = calls.get(key, 0) + 1
            if seed == 1:
                return (FakeResult(scores=(1100, 900), deal_ins=(0, 2))
                        if not swapped else
                        FakeResult(scores=(950, 1050), deal_ins=(1, 0)))
            return (FakeResult(scores=(1000, 1000), deal_ins=(1, 1))
                    if not swapped else
                    FakeResult(scores=(900, 1100), deal_ins=(2, 0)))

        report = run_paired_real_matches(
            [1, 2], agent_factories=(factory_a, factory_b), match_runner=runner)
        # Pair 1 A-B deltas: +200, +100 -> pair mean +150.
        # Pair 2 A-B deltas: 0, +200 -> pair mean +100.
        # Overall paired mean = 125; sample SD = sqrt(1250) ~= 35.355.
        self.assertAlmostEqual(report.paired_score_delta_mean, 125.0)
        self.assertAlmostEqual(report.paired_score_delta_sd, 35.3553390593)
        self.assertAlmostEqual(report.paired_score_delta_se, 25.0)
        self.assertAlmostEqual(report.paired_score_delta_ci95_low, 76.0)
        self.assertAlmostEqual(report.paired_score_delta_ci95_high, 174.0)
        # Deal-in pair means: -1.5 and -1.0 -> overall -1.25.
        self.assertAlmostEqual(report.paired_deal_in_delta_mean, -1.25)

    def test_duplicate_seed_positions_remain_distinct_pairs(self):
        def runner(seed, *, agent_factories, **kwargs):
            return FakeResult(scores=(1010, 990))

        report = run_paired_real_matches(
            [5, 5], agent_factories=(factory_a, factory_b), match_runner=runner)
        self.assertEqual(report.total_pairs, 2)
        self.assertEqual(report.completed_pairs, 2)
        self.assertEqual([item.pair_index for item in report.per_match], [0, 0, 1, 1])

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            run_paired_real_matches([], agent_factories=(factory_a, factory_b))
        with self.assertRaises(ValueError):
            run_paired_real_matches([True], agent_factories=(factory_a, factory_b))
        with self.assertRaises(ValueError):
            run_paired_real_matches([1], agent_factories=(factory_a,))
        with self.assertRaises(ValueError):
            run_paired_real_matches(
                [1], agent_factories=(factory_a, factory_b), agent_names=("A", ""))

        def bad_runner(**kwargs):
            return FakeResult(status="MAX_STEPS")

        with self.assertRaises(ValueError):
            run_paired_real_matches(
                [1], agent_factories=(factory_a, factory_b), match_runner=bad_runner)


if __name__ == "__main__":
    unittest.main()
