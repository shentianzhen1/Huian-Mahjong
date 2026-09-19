import unittest
from copy import deepcopy
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from unittest.mock import patch

from huian._legacy import env
from workspace.ai import (CURRENT_AGENT_NAME, CURRENT_AGENT_VERSION,
                          CurrentAgent, BaselineAgent, DangerAwareShantenAgent,
                          EfficiencyAgent, MatchAwareShantenAgent,
                          MatchObservationContext, MeldAwareShantenAgent,
                          OneShantenTwoPlyRiskAgent, PlayerObservation,
                          ScoreAwareMeldAgent, ShantenAgent,
                          TenpaiLossTieBreakAgent, TenpaiRiskLossTieBreakAgent,
                          TenpaiRiskTieBreakAgent, TwoPlyShantenRiskAgent,
                          best_offense_ties,
                          estimate_discard_danger, min_shanten_discards)
from test_huian_environment import scenario


def observation(hand, gold="P9"):
    return PlayerObservation(0, tuple(hand), gold, "AFTER_DRAW", 0, 40,
                             ((), ()), ((), ()), ((), ()))


def discards(hand):
    return [env.Action(0, env.ActionType.DISCARD, tile=tile) for tile in sorted(set(hand))]


class BaselineAgentTests(unittest.TestCase):
    def test_v011_uses_known_score_only_inside_exact_tenpai_offense_tie(self):
        context = MatchObservationContext(
            scores=(1000, 1000), hand_index=2, hands_remaining=6,
            dealer=0, current_dealer_base=20, consecutive_dealer_hands=2,
        )
        view = PlayerObservation(
            0, ("M1", "M2"), "P9", "AFTER_DRAW", 0, 40,
            ((), ()), ((), ()), ((), ()), context,
        )
        actions = discards(list(view.hand))
        ties = (
            SimpleNamespace(
                discard="M1", shanten=0, total_live_copies=4,
                effective_tile_types=("B",),
                effective_tiles=(object(),),
            ),
            SimpleNamespace(
                discard="M2", shanten=0, total_live_copies=4,
                effective_tile_types=("R",),
                effective_tiles=(object(),),
            ),
        )

        def fake_value(hand, **kwargs):
            discarded = "M2" if tuple(hand) == ("M1",) else "M1"
            weighted = 160 if discarded == "M1" else 120
            return SimpleNamespace(
                total_live_copies=4,
                weighted_net_points=weighted,
                mean_net_points_if_win=weighted / 4,
                current_dealer_base=20,
            )

        with patch(
                "workspace.ai.baseline.best_offense_ties",
                return_value=ties), patch(
                "workspace.ai.baseline.evaluate_tenpai_ordinary_value",
                side_effect=fake_value):
            decision = ScoreAwareMeldAgent(
                seed=7, template_samples=32).choose_decision(view, actions)

        self.assertEqual(decision.action.tile, "M1")
        self.assertIn("score_aware_meld_v0.11", decision.reason)
        self.assertIn("not full EV", decision.reason)

    def test_v011_falls_back_to_v010_without_match_context(self):
        hand = (
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["B", "N"]
        )
        view = PlayerObservation(
            0, tuple(hand), "P9", "AFTER_DRAW", 0, 40,
            ((), ()), ((), ()), ((), ()), None,
        )
        actions = discards(hand)
        expected = MeldAwareShantenAgent(
            seed=9, template_samples=32).choose_decision(view, actions)
        with patch(
                "workspace.ai.baseline.evaluate_tenpai_ordinary_value"
        ) as mocked:
            actual = ScoreAwareMeldAgent(
                seed=9, template_samples=32).choose_decision(view, actions)
        self.assertEqual(actual.action, expected.action)
        mocked.assert_not_called()

    def test_current_agent_points_to_promoted_v0_10(self):
        self.assertIs(CurrentAgent, MeldAwareShantenAgent)
        self.assertEqual(CURRENT_AGENT_VERSION, "v0.10")
        self.assertEqual(CURRENT_AGENT_NAME, "MeldAwareShantenAgent")
        agent = CurrentAgent(seed=7)
        self.assertEqual(agent.template_samples, 32)
        self.assertIsInstance(agent, TenpaiRiskTieBreakAgent)

    def test_hu_first_with_reason_and_unchanged_action(self):
        actions = discards(["M1"]) + [env.Action(0, env.ActionType.HU, metadata={"source": "self_draw"})]
        original = deepcopy(actions)
        decision = BaselineAgent().choose_action(observation(["M1"]), actions)
        self.assertEqual(decision.action.type, env.ActionType.HU)
        self.assertTrue(decision.reason)
        self.assertEqual(actions, original)
        self.assertIs(decision.action, actions[-1])

    def test_preserves_gold_pairs_and_connections(self):
        for hand, isolated in (
            (["P9", "M1", "M1", "S3", "S4", "W"], "W"),
            (["P9", "M1", "M1", "S3", "S5", "N"], "N"),
            (["P9", "M2", "M2"], "M2"),
        ):
            decision = BaselineAgent().choose_decision(observation(hand), discards(hand))
            self.assertEqual(decision.action.tile, isolated)
            self.assertIn("lowest retention", decision.reason)

    def test_tie_break_is_independent_of_action_list_order(self):
        hand = ["W", "E", "N"]
        actions = discards(hand)
        first = BaselineAgent().choose_action(observation(hand), actions)
        self.assertEqual(first, BaselineAgent().choose_action(observation(hand), actions[::-1]))

    def test_pass_over_optional_claim_and_required_draw(self):
        actions = [env.Action(0, env.ActionType.CHI, tiles=("M1", "M2", "M3")),
                   env.Action(0, env.ActionType.PASS)]
        self.assertEqual(BaselineAgent().choose_action(observation([]), actions).action, actions[1])
        draw = env.Action(0, env.ActionType.DRAW, metadata={"source": "wall_head"})
        self.assertEqual(BaselineAgent().choose_action(observation([]), [draw]).action, draw)
        with self.assertRaises(ValueError):
            BaselineAgent().choose_action(observation([]), [])

    def test_efficiency_agent_prefers_preserving_live_connected_side(self):
        hand = ["M1", "M2", "M8", "M9"]
        view = PlayerObservation(
            0, tuple(hand), "P9", "AFTER_DRAW", 0, 40,
            (("M3", "M3", "M3", "M3"), ()),
            ((), ()), ((), ()),
        )
        decision = EfficiencyAgent().choose_decision(view, discards(hand))
        self.assertIn(decision.action.tile, ("M1", "M2"))
        self.assertIn("efficiency_v0.2", decision.reason)

    def test_efficiency_agent_uses_only_public_observation_and_keeps_hu_priority(self):
        view = observation(["M1", "M2", "E"])
        actions = discards(list(view.hand)) + [
            env.Action(0, env.ActionType.HU, metadata={"source": "self_draw"})
        ]
        decision = EfficiencyAgent().choose_decision(view, actions)
        self.assertEqual(decision.action.type, env.ActionType.HU)
        diagnostics = EfficiencyAgent.discard_diagnostics(view, "E")
        self.assertIn("weighted_gain", diagnostics)
        self.assertIn("live_improving_copies", diagnostics)

    def test_shanten_agent_prefers_live_wait_over_dead_wait(self):
        hand = (
            ["M1"] * 3
            + ["P1"] * 3
            + ["S1"] * 3
            + ["E"] * 3
            + ["R"] * 3
            + ["B", "N"]
        )
        view = PlayerObservation(
            0, tuple(hand), "P9", "AFTER_DRAW", 0, 40,
            (("N", "N", "N"), ()),
            ((), ()), ((), ()),
        )
        decision = ShantenAgent().choose_decision(view, discards(hand))
        self.assertEqual(decision.action.tile, "N")
        self.assertIn("shanten_v0.1", decision.reason)
        self.assertIn("live=7", decision.reason)
        self.assertIn("effective=[P9,B]", decision.reason)

    def test_shanten_agent_keeps_hu_and_pass_priorities(self):
        view = observation(["M1"])
        hu = env.Action(0, env.ActionType.HU, metadata={"source": "self_draw"})
        self.assertEqual(
            ShantenAgent().choose_decision(view, discards(["M1"]) + [hu]).action,
            hu,
        )
        claim = [
            env.Action(0, env.ActionType.CHI, tiles=("M1", "M2", "M3")),
            env.Action(0, env.ActionType.PASS),
        ]
        self.assertEqual(
            ShantenAgent().choose_decision(observation([]), claim).action,
            claim[1],
        )

    def test_public_danger_estimate_uses_only_exposure_not_safe_tile_rules(self):
        view = PlayerObservation(
            0, ("M1", "M1", "P1"), "P9", "AFTER_DRAW", 0, 40,
            ((), ("M1",)),
            ((), ()),
            ((), ()),
        )
        info = estimate_discard_danger(view, "M1")
        self.assertEqual(info.own_copies, 2)
        self.assertEqual(info.public_copies, 1)
        self.assertEqual(info.unseen_copies, 1)
        self.assertEqual(info.risk_units, 1)
        self.assertEqual(info.opponent_discard_copies, 1)
        self.assertFalse(info.is_probability)
        with self.assertRaises(ValueError):
            estimate_discard_danger(view, "S9")

    def test_public_danger_rejects_impossible_fifth_copy(self):
        view = PlayerObservation(
            0, ("M1", "M1"), "P9", "AFTER_DRAW", 0, 40,
            (("M1",), ("M1", "M1")),
            ((), ()),
            ((), ()),
        )
        with self.assertRaises(ValueError):
            estimate_discard_danger(view, "M1")

    def test_danger_aware_agent_never_leaves_minimum_shanten_frontier(self):
        hand = (
            ["M1"] * 3
            + ["P1"] * 3
            + ["S1"] * 3
            + ["E"] * 3
            + ["R"] * 3
            + ["B", "N"]
        )
        view = PlayerObservation(
            0, tuple(hand), "P9", "AFTER_DRAW", 0, 40,
            (("N",), ()), ((), ()), ((), ()),
        )
        agent = DangerAwareShantenAgent(danger_weight=1.0)
        decision = agent.choose_decision(view, discards(hand))
        frontier = min_shanten_discards(
            hand, gold_tile="P9",
            visible_tiles=ShantenAgent._public_tiles(view),
            allowed_discards=tuple(sorted(set(hand))),
        )
        min_shanten = frontier[0].shanten
        selected = next(item for item in frontier if item.discard == decision.action.tile)
        self.assertEqual(selected.shanten, min_shanten)
        self.assertIn("danger_shanten_v0.4", decision.reason)
        self.assertIn("risk_units=", decision.reason)
        self.assertIn("not a probability", decision.reason)

    def test_zero_danger_weight_reproduces_shanten_v0_3_choice(self):
        hand = (
            ["M1"] * 3
            + ["P1"] * 3
            + ["S1"] * 3
            + ["E"] * 3
            + ["R"] * 3
            + ["B", "N"]
        )
        view = PlayerObservation(
            0, tuple(hand), "P9", "AFTER_DRAW", 0, 40,
            (("N",), ()), ((), ()), ((), ()),
        )
        actions = discards(hand)
        old = ShantenAgent().choose_decision(view, actions)
        new = DangerAwareShantenAgent(danger_weight=0).choose_decision(view, actions)
        self.assertEqual(new.action, old.action)

    def test_danger_aware_agent_validates_weight_and_keeps_hu_priority(self):
        with self.assertRaises(ValueError):
            DangerAwareShantenAgent(danger_weight=-0.1)
        with self.assertRaises(ValueError):
            DangerAwareShantenAgent(danger_weight=True)
        view = observation(["M1"])
        hu = env.Action(0, env.ActionType.HU, metadata={"source": "self_draw"})
        decision = DangerAwareShantenAgent().choose_decision(
            view, discards(["M1"]) + [hu])
        self.assertIs(decision.action, hu)

    def test_v06_preserves_v03_when_no_exact_offense_tie(self):
        hand = (
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["B", "N"]
        )
        view = PlayerObservation(
            0, tuple(hand), "P9", "AFTER_DRAW", 0, 40,
            (("N", "N"), ()), ((), ()), ((), ()),
        )
        actions = discards(hand)
        expected = ShantenAgent().choose_decision(view, actions)
        with patch(
                "workspace.ai.baseline.estimate_tenpai_wait_risk_scores"
        ) as mocked:
            actual = TenpaiRiskTieBreakAgent(
                seed=7, template_samples=32).choose_decision(view, actions)
        self.assertEqual(actual.action, expected.action)
        mocked.assert_not_called()
        self.assertIn("preserve V0.3 choice", actual.reason)

    def test_v06_uses_relative_risk_only_inside_exact_offense_tie(self):
        hand = (
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["B", "N"]
        )
        view = observation(hand)
        ties = best_offense_ties(
            hand, gold_tile=view.gold_tile,
            visible_tiles=ShantenAgent._public_tiles(view),
            allowed_discards=tuple(sorted(set(hand))),
        )
        self.assertEqual({item.discard for item in ties}, {"B", "N"})

        def fake_risk(_observation, candidates, *, samples, seed):
            self.assertEqual(set(candidates), {"B", "N"})
            self.assertEqual(samples, 32)
            return tuple(
                SimpleNamespace(
                    tile=tile, risk_score=0.1 if tile == "N" else 0.9,
                    templates_used=samples)
                for tile in candidates
            )

        with patch(
                "workspace.ai.baseline.estimate_tenpai_wait_risk_scores",
                side_effect=fake_risk):
            decision = TenpaiRiskTieBreakAgent(
                seed=11, template_samples=32).choose_decision(
                    view, discards(hand))
        self.assertEqual(decision.action.tile, "N")
        self.assertIn("exact offense tie", decision.reason)
        self.assertIn("not a probability", decision.reason)

    def test_v06_preserves_v03_order_when_exact_tie_contains_gold(self):
        hand = (
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["B", "N"]
        )
        view = observation(hand, gold="B")
        actions = discards(hand)
        fake_ties = (
            SimpleNamespace(
                discard="N", shanten=0, total_live_copies=3,
                effective_tiles=(object(),)),
            SimpleNamespace(
                discard="B", shanten=0, total_live_copies=3,
                effective_tiles=(object(),)),
        )
        with patch(
                "workspace.ai.baseline.best_offense_ties",
                return_value=fake_ties), patch(
                "workspace.ai.baseline.estimate_tenpai_wait_risk_scores"
        ) as mocked:
            actual = TenpaiRiskTieBreakAgent(
                seed=5, template_samples=32).choose_decision(view, actions)
        self.assertEqual(actual.action.tile, "N")
        mocked.assert_not_called()
        self.assertIn("includes gold", actual.reason)

    def test_v06_falls_back_to_v03_if_tenpai_templates_unavailable(self):
        hand = (
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["B", "N"]
        )
        view = observation(hand)
        actions = discards(hand)
        expected = ShantenAgent().choose_decision(view, actions)
        with patch(
                "workspace.ai.baseline.estimate_tenpai_wait_risk_scores",
                side_effect=RuntimeError("no templates")):
            actual = TenpaiRiskTieBreakAgent(
                seed=5, template_samples=32).choose_decision(view, actions)
        self.assertEqual(actual.action, expected.action)
        self.assertIn("templates unavailable", actual.reason)

    def test_v07_uses_confirmed_loss_only_inside_exact_offense_tie(self):
        hand = (
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["B", "N"]
        )
        context = MatchObservationContext(
            scores=(1000, 1000), hand_index=2, hands_remaining=6,
            dealer=0, current_dealer_base=20, consecutive_dealer_hands=3)
        base_view = observation(hand)
        view = PlayerObservation(
            base_view.seat, base_view.hand, base_view.gold_tile,
            base_view.phase, base_view.dealer, base_view.wall_remaining,
            base_view.discards, base_view.flowers, base_view.melds, context)

        def fake_loss(_observation, candidates, *, samples, seed):
            return tuple(
                SimpleNamespace(
                    tile=tile,
                    loss_index=5.0 if tile == "N" else 20.0,
                    risk_score=0.4 if tile == "N" else 0.2,
                    mean_loss_if_hit=12.5 if tile == "N" else 100.0,
                    templates_used=samples,
                    complete=True,
                )
                for tile in candidates
            )

        with patch(
                "workspace.ai.baseline.estimate_tenpai_wait_loss_scores",
                side_effect=fake_loss), patch(
                "workspace.ai.baseline.estimate_tenpai_wait_risk_scores"
        ) as fallback:
            decision = TenpaiLossTieBreakAgent(
                seed=13, template_samples=32).choose_decision(
                    view, discards(hand))
        self.assertEqual(decision.action.tile, "N")
        fallback.assert_not_called()
        self.assertIn("conditional_loss_index=5.000", decision.reason)
        self.assertIn("not absolute EV", decision.reason)

    def test_v07_preserves_v06_boundary_when_no_exact_offense_tie(self):
        hand = (
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["B", "N"]
        )
        view = PlayerObservation(
            0, tuple(hand), "P9", "AFTER_DRAW", 0, 40,
            (("N", "N"), ()), ((), ()), ((), ()),
            MatchObservationContext(
                scores=(1000, 1000), hand_index=2, hands_remaining=6,
                dealer=0, current_dealer_base=20,
                consecutive_dealer_hands=3),
        )
        expected = ShantenAgent().choose_decision(view, discards(hand))
        with patch(
                "workspace.ai.baseline.estimate_tenpai_wait_loss_scores"
        ) as loss_model:
            actual = TenpaiLossTieBreakAgent(
                seed=7, template_samples=32).choose_decision(
                    view, discards(hand))
        self.assertEqual(actual.action, expected.action)
        loss_model.assert_not_called()
        self.assertIn("no exact offense tie", actual.reason)

    def test_v07_falls_back_to_v06_if_score_evidence_is_incomplete(self):
        hand = (
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["B", "N"]
        )
        base_view = observation(hand)
        context = MatchObservationContext(
            scores=(1000, 1000), hand_index=2, hands_remaining=6,
            dealer=0, current_dealer_base=20, consecutive_dealer_hands=3)
        view = PlayerObservation(
            base_view.seat, base_view.hand, base_view.gold_tile,
            base_view.phase, base_view.dealer, base_view.wall_remaining,
            base_view.discards, base_view.flowers, base_view.melds, context)

        def incomplete_loss(_observation, candidates, *, samples, seed):
            return tuple(
                SimpleNamespace(tile=tile, complete=False)
                for tile in candidates
            )

        def fake_risk(_observation, candidates, *, samples, seed):
            return tuple(
                SimpleNamespace(
                    tile=tile, risk_score=0.1 if tile == "N" else 0.9,
                    templates_used=samples)
                for tile in candidates
            )

        with patch(
                "workspace.ai.baseline.estimate_tenpai_wait_loss_scores",
                side_effect=incomplete_loss), patch(
                "workspace.ai.baseline.estimate_tenpai_wait_risk_scores",
                side_effect=fake_risk):
            decision = TenpaiLossTieBreakAgent(
                seed=17, template_samples=32).choose_decision(
                    view, discards(hand))
        self.assertEqual(decision.action.tile, "N")
        self.assertIn("ordinary score evidence incomplete", decision.reason)
        self.assertIn("fallback=v0.6_relative_risk", decision.reason)

    def test_v07b_keeps_v06_risk_ahead_of_loss(self):
        hand = (
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["B", "N"]
        )
        base_view = observation(hand)
        context = MatchObservationContext(
            scores=(1000, 1000), hand_index=2, hands_remaining=6,
            dealer=0, current_dealer_base=20, consecutive_dealer_hands=3)
        view = PlayerObservation(
            base_view.seat, base_view.hand, base_view.gold_tile,
            base_view.phase, base_view.dealer, base_view.wall_remaining,
            base_view.discards, base_view.flowers, base_view.melds, context)

        def fake_loss(_observation, candidates, *, samples, seed):
            return tuple(
                SimpleNamespace(
                    tile=tile,
                    # N is cheaper if hit but has twice the V0.6 relative risk.
                    loss_index=4.0 if tile == "N" else 8.0,
                    risk_score=0.4 if tile == "N" else 0.2,
                    mean_loss_if_hit=10.0 if tile == "N" else 40.0,
                    templates_used=samples,
                    complete=True,
                )
                for tile in candidates
            )

        with patch(
                "workspace.ai.baseline.estimate_tenpai_wait_loss_scores",
                side_effect=fake_loss):
            decision = TenpaiRiskLossTieBreakAgent(
                seed=19, template_samples=32).choose_decision(
                    view, discards(hand))
        self.assertEqual(decision.action.tile, "B")
        self.assertIn("tenpai_risk_loss_tiebreak_v0.7b", decision.reason)

    def test_v07b_uses_loss_only_when_relative_risk_is_tied(self):
        hand = (
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["B", "N"]
        )
        base_view = observation(hand)
        context = MatchObservationContext(
            scores=(1000, 1000), hand_index=2, hands_remaining=6,
            dealer=0, current_dealer_base=20, consecutive_dealer_hands=3)
        view = PlayerObservation(
            base_view.seat, base_view.hand, base_view.gold_tile,
            base_view.phase, base_view.dealer, base_view.wall_remaining,
            base_view.discards, base_view.flowers, base_view.melds, context)

        def fake_loss(_observation, candidates, *, samples, seed):
            return tuple(
                SimpleNamespace(
                    tile=tile,
                    loss_index=5.0 if tile == "N" else 9.0,
                    risk_score=0.25,
                    mean_loss_if_hit=20.0 if tile == "N" else 36.0,
                    templates_used=samples,
                    complete=True,
                )
                for tile in candidates
            )

        with patch(
                "workspace.ai.baseline.estimate_tenpai_wait_loss_scores",
                side_effect=fake_loss):
            decision = TenpaiRiskLossTieBreakAgent(
                seed=23, template_samples=32).choose_decision(
                    view, discards(hand))
        self.assertEqual(decision.action.tile, "N")
        self.assertIn("conditional_loss_index=5.000", decision.reason)

    def test_v07a_policy_label_is_auditable(self):
        self.assertEqual(
            TenpaiLossTieBreakAgent()._policy_label(),
            "tenpai_loss_tiebreak_v0.7a")

    def test_v08_two_ply_resolves_exact_offense_tie_before_risk(self):
        hand = (
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["B", "N"]
        )
        view = observation(hand)

        def fake_two_ply(_hand, candidates, **kwargs):
            return tuple(
                SimpleNamespace(
                    discard=tile,
                    weighted_post_shanten=10 if tile == "N" else 20,
                    terminal_win_copies=0,
                    weighted_post_live_copies=100,
                    weighted_post_effective_types=50,
                    expected_post_shanten=(10 if tile == "N" else 20) / 100,
                    expected_post_live_copies=1.0,
                    expected_post_effective_types=0.5,
                )
                for tile in candidates
            )

        with patch(
                "workspace.ai.baseline.analyze_two_ply_offense",
                side_effect=fake_two_ply), patch(
                "workspace.ai.baseline.estimate_tenpai_wait_risk_scores"
        ) as risk_model:
            decision = TwoPlyShantenRiskAgent(
                seed=29, template_samples=32).choose_decision(
                    view, discards(hand))
        self.assertEqual(decision.action.tile, "N")
        risk_model.assert_not_called()
        self.assertIn("deterministic two-ply", decision.reason)

    def test_v08_uses_v06_risk_only_after_two_ply_tie(self):
        hand = (
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["B", "N"]
        )
        view = observation(hand)

        def tied_two_ply(_hand, candidates, **kwargs):
            return tuple(
                SimpleNamespace(
                    discard=tile,
                    weighted_post_shanten=10,
                    terminal_win_copies=0,
                    weighted_post_live_copies=100,
                    weighted_post_effective_types=50,
                    expected_post_shanten=0.1,
                    expected_post_live_copies=1.0,
                    expected_post_effective_types=0.5,
                )
                for tile in candidates
            )

        def fake_risk(_observation, candidates, *, samples, seed):
            return tuple(
                SimpleNamespace(
                    tile=tile,
                    risk_score=0.1 if tile == "B" else 0.4,
                    templates_used=samples,
                )
                for tile in candidates
            )

        with patch(
                "workspace.ai.baseline.analyze_two_ply_offense",
                side_effect=tied_two_ply), patch(
                "workspace.ai.baseline.estimate_tenpai_wait_risk_scores",
                side_effect=fake_risk):
            decision = TwoPlyShantenRiskAgent(
                seed=31, template_samples=32).choose_decision(
                    view, discards(hand))
        self.assertEqual(decision.action.tile, "B")
        self.assertIn("two-ply offense still tied", decision.reason)
        self.assertIn("relative_risk=0.100", decision.reason)

    def test_v08_preserves_v03_when_no_exact_offense_tie(self):
        hand = (
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["B", "N"]
        )
        view = PlayerObservation(
            0, tuple(hand), "P9", "AFTER_DRAW", 0, 40,
            (("N", "N"), ()), ((), ()), ((), ()),
        )
        expected = ShantenAgent().choose_decision(view, discards(hand))
        with patch(
                "workspace.ai.baseline.analyze_two_ply_offense"
        ) as lookahead:
            actual = TwoPlyShantenRiskAgent(
                seed=7, template_samples=32).choose_decision(
                    view, discards(hand))
        self.assertEqual(actual.action, expected.action)
        lookahead.assert_not_called()

    def test_v09_uses_two_ply_at_one_shanten_exact_tie(self):
        hand = (
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["B", "N"]
        )
        view = observation(hand)
        ties = tuple(
            SimpleNamespace(
                discard=tile, shanten=1, total_live_copies=20,
                effective_tiles=(1, 2, 3))
            for tile in ("B", "N")
        )

        def fake_two_ply(_hand, candidates, **kwargs):
            return tuple(
                SimpleNamespace(
                    discard=tile,
                    weighted_post_shanten=10 if tile == "N" else 20,
                    terminal_win_copies=0,
                    weighted_post_live_copies=100,
                    weighted_post_effective_types=50,
                    expected_post_shanten=(10 if tile == "N" else 20) / 100,
                    expected_post_live_copies=1.0,
                    expected_post_effective_types=0.5,
                )
                for tile in candidates
            )

        with patch(
                "workspace.ai.baseline.best_offense_ties",
                return_value=ties), patch(
                "workspace.ai.baseline.analyze_two_ply_offense",
                side_effect=fake_two_ply), patch(
                "workspace.ai.baseline.estimate_tenpai_wait_risk_scores"
        ) as risk_model:
            decision = OneShantenTwoPlyRiskAgent(
                seed=37, template_samples=32).choose_decision(
                    view, discards(hand))
        self.assertEqual(decision.action.tile, "N")
        risk_model.assert_not_called()
        self.assertIn("one_shanten_two_ply_v0.9", decision.reason)
        self.assertIn("deterministic two-ply", decision.reason)

    def test_v09_gates_two_ply_off_outside_one_shanten(self):
        hand = (
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["B", "N"]
        )
        view = observation(hand)

        def fake_risk(_observation, candidates, *, samples, seed):
            return tuple(
                SimpleNamespace(
                    tile=tile,
                    risk_score=0.1 if tile == "B" else 0.5,
                    templates_used=samples)
                for tile in candidates
            )

        for shanten in (0, 2, 3, 4):
            ties = tuple(
                SimpleNamespace(
                    discard=tile, shanten=shanten, total_live_copies=20,
                    effective_tiles=(1, 2, 3))
                for tile in ("B", "N")
            )
            with self.subTest(shanten=shanten), patch(
                    "workspace.ai.baseline.best_offense_ties",
                    return_value=ties), patch(
                    "workspace.ai.baseline.analyze_two_ply_offense"
            ) as lookahead, patch(
                    "workspace.ai.baseline.estimate_tenpai_wait_risk_scores",
                    side_effect=fake_risk):
                decision = OneShantenTwoPlyRiskAgent(
                    seed=41, template_samples=32).choose_decision(
                        view, discards(hand))
            self.assertEqual(decision.action.tile, "B")
            lookahead.assert_not_called()
            self.assertIn(
                f"gated_off_at_shanten={shanten}", decision.reason)

    def test_v10_claims_only_for_strict_post_discard_offense_gain(self):
        hand = (
            "M1","M2","M4","M5","M6","M7","M8","M9",
            "P1","P2","P3","S1","S2","S3","E","E",
        )
        view = PlayerObservation(
            0, hand, "P9", "AFTER_DISCARD", 0, 60,
            ((), ("M3",)), ((), ()), ((), ()),
        )
        claim = env.Action(
            0, env.ActionType.CHI, tile="M3", tiles=("M1","M2","M3"))
        actions = [claim, env.Action(0, env.ActionType.PASS)]

        pass_state = SimpleNamespace(
            shanten=2, total_live_copies=20, effective_tiles=(1, 2, 3))
        projected = SimpleNamespace(
            discard="E", shanten=1, total_live_copies=12,
            effective_tiles=(1, 2))

        captured = {}
        def fake_best(post_claim, **kwargs):
            captured["hand"] = tuple(post_claim)
            captured.update(kwargs)
            return projected

        with patch(
                "workspace.ai.baseline.analyze_effective_tiles",
                return_value=pass_state), patch(
                "workspace.ai.baseline.best_discard",
                side_effect=fake_best):
            decision = MeldAwareShantenAgent(seed=5).choose_decision(
                view, actions)

        self.assertEqual(decision.action, claim)
        self.assertIn("strict offense gain", decision.reason)
        self.assertEqual(len(captured["hand"]), 14)
        self.assertNotIn("M1", captured["hand"])
        self.assertNotIn("M2", captured["hand"])
        self.assertEqual(captured["open_melds"], 1)
        visible = captured["visible_tiles"]
        self.assertEqual(visible.count("M3"), 1)
        self.assertEqual(visible.count("M1"), 1)
        self.assertEqual(visible.count("M2"), 1)

    def test_v10_passes_when_claim_does_not_strictly_improve_offense(self):
        hand = (
            "M1","M2","M4","M5","M6","M7","M8","M9",
            "P1","P2","P3","S1","S2","S3","E","E",
        )
        view = PlayerObservation(
            0, hand, "P9", "AFTER_DISCARD", 0, 60,
            ((), ("M3",)), ((), ()), ((), ()),
        )
        claim = env.Action(
            0, env.ActionType.CHI, tile="M3", tiles=("M1","M2","M3"))
        passed = env.Action(0, env.ActionType.PASS)
        pass_state = SimpleNamespace(
            shanten=1, total_live_copies=20, effective_tiles=(1, 2, 3))
        projected = SimpleNamespace(
            discard="E", shanten=1, total_live_copies=20,
            effective_tiles=(1, 2, 3))

        with patch(
                "workspace.ai.baseline.analyze_effective_tiles",
                return_value=pass_state), patch(
                "workspace.ai.baseline.best_discard",
                return_value=projected):
            decision = MeldAwareShantenAgent(seed=7).choose_decision(
                view, [claim, passed])
        self.assertEqual(decision.action, passed)
        self.assertIn("no strict Chi/Peng offense gain", decision.reason)

    def test_v10_gold_in_hand_guard_preserves_pass_without_projection(self):
        hand = (
            "M1","M2","M4","M5","M6","M7","M8","M9",
            "P1","P2","P3","S1","S2","S3","E","E",
        )
        view = PlayerObservation(
            0, hand, "M9", "AFTER_DISCARD", 0, 60,
            ((), ("M3",)), ((), ()), ((), ()),
        )
        claim = env.Action(
            0, env.ActionType.CHI, tile="M3", tiles=("M1","M2","M3"))
        passed = env.Action(0, env.ActionType.PASS)
        with patch(
                "workspace.ai.baseline.analyze_effective_tiles"
        ) as pass_eval, patch(
                "workspace.ai.baseline.best_discard"
        ) as claim_eval:
            decision = MeldAwareShantenAgent(seed=11).choose_decision(
                view, [claim, passed])
        self.assertEqual(decision.action, passed)
        self.assertIn("gold-in-hand guard", decision.reason)
        pass_eval.assert_not_called()
        claim_eval.assert_not_called()

    def test_v10_selects_best_of_multiple_claims(self):
        hand = (
            "M1","M2","M4","M5","M6","M7","M8","M9",
            "P1","P2","P3","S1","S2","S3","E","E",
        )
        view = PlayerObservation(
            0, hand, "P9", "AFTER_DISCARD", 0, 60,
            ((), ("M3",)), ((), ()), ((), ()),
        )
        chi12 = env.Action(
            0, env.ActionType.CHI, tile="M3", tiles=("M1","M2","M3"))
        chi45 = env.Action(
            0, env.ActionType.CHI, tile="M3", tiles=("M3","M4","M5"))
        passed = env.Action(0, env.ActionType.PASS)
        pass_state = SimpleNamespace(
            shanten=3, total_live_copies=25, effective_tiles=(1, 2, 3))

        def fake_best(post_claim, **kwargs):
            if "M1" not in post_claim and "M2" not in post_claim:
                return SimpleNamespace(
                    discard="E", shanten=2, total_live_copies=14,
                    effective_tiles=(1, 2))
            return SimpleNamespace(
                discard="E", shanten=1, total_live_copies=10,
                effective_tiles=(1,))

        with patch(
                "workspace.ai.baseline.analyze_effective_tiles",
                return_value=pass_state), patch(
                "workspace.ai.baseline.best_discard",
                side_effect=fake_best):
            decision = MeldAwareShantenAgent(seed=13).choose_decision(
                view, [chi12, chi45, passed])
        self.assertEqual(decision.action, chi45)

    def test_v06_validates_sampling_configuration(self):
        for value in (0, -1, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                TenpaiRiskTieBreakAgent(template_samples=value)
        with self.assertRaises(ValueError):
            TenpaiRiskTieBreakAgent(seed=True)

    def test_match_aware_v05_risk_gate_uses_only_late_lead(self):
        agent = MatchAwareShantenAgent(late_lead_weight=0.25, late_hands=3)
        base = dict(
            dealer=0, current_dealer_base=20, consecutive_dealer_hands=3)

        early = MatchObservationContext(
            scores=(1100, 900), hand_index=4, hands_remaining=4, **base)
        late_lead = MatchObservationContext(
            scores=(1100, 900), hand_index=5, hands_remaining=3, **base)
        late_tied = MatchObservationContext(
            scores=(1000, 1000), hand_index=5, hands_remaining=3, **base)
        late_behind = MatchObservationContext(
            scores=(900, 1100), hand_index=5, hands_remaining=3, **base)

        hand = ("M1",)
        for context, expected in (
                (early, 0.0),
                (late_lead, 0.25),
                (late_tied, 0.0),
                (late_behind, 0.0)):
            view = PlayerObservation(
                0, hand, "P9", "AFTER_DRAW", 0, 40,
                ((), ()), ((), ()), ((), ()), context)
            self.assertEqual(agent._danger_weight_for(view), expected)
        no_context = observation(["M1"])
        self.assertEqual(agent._danger_weight_for(no_context), 0.0)

        seat1_lead = MatchObservationContext(
            scores=(900, 1100), hand_index=5, hands_remaining=3, **base)
        seat1_view = PlayerObservation(
            1, hand, "P9", "AFTER_DRAW", 0, 40,
            ((), ()), ((), ()), ((), ()), seat1_lead)
        self.assertEqual(agent._danger_weight_for(seat1_view), 0.25)

    def test_match_aware_v05_validates_late_window(self):
        for value in (0, 9, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                MatchAwareShantenAgent(late_hands=value)

    def test_match_context_is_public_immutable_and_seat_relative(self):
        context = MatchObservationContext(
            scores=(1120, 880),
            hand_index=5,
            hands_remaining=3,
            dealer=0,
            current_dealer_base=25,
            consecutive_dealer_hands=4,
        )
        self.assertEqual(context.margin, 240)
        self.assertEqual(context.margin_for(0), 240)
        self.assertEqual(context.margin_for(1), -240)
        with self.assertRaises(ValueError):
            context.margin_for(2)
        with self.assertRaises(ValueError):
            MatchObservationContext((1000, 1000), 5, 2, 0, 10, 1)

        state = scenario()
        view = PlayerObservation.from_state(state, match_context=context)
        self.assertIs(view.match_context, context)
        self.assertFalse(hasattr(view, "hands"))
        self.assertFalse(hasattr(view, "wall"))
        with self.assertRaises(FrozenInstanceError):
            context.scores = (1000, 1000)

    def test_observation_has_only_private_hand_and_public_immutable_fields(self):
        state = scenario()
        view = PlayerObservation.from_state(state)
        self.assertEqual(view.hand, tuple(state.hands[0]))
        self.assertFalse(hasattr(view, "hands"))
        self.assertFalse(hasattr(view, "wall"))
        self.assertFalse(hasattr(view, "reserved_tiles"))
        before = deepcopy(view)
        state.hands[0].clear()
        state.discards[1].append("E")
        self.assertEqual(view, before)
        with self.assertRaises(FrozenInstanceError):
            view.gold_tile = "E"


if __name__ == "__main__":
    unittest.main()
