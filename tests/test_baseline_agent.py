import unittest
from copy import deepcopy
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from unittest.mock import patch

from huian._legacy import env
from workspace.ai import (BaselineAgent, DangerAwareShantenAgent,
                          EfficiencyAgent, MatchAwareShantenAgent,
                          MatchObservationContext, PlayerObservation, ShantenAgent,
                          TenpaiRiskTieBreakAgent, best_offense_ties,
                          estimate_discard_danger, min_shanten_discards)
from test_huian_environment import scenario


def observation(hand, gold="P9"):
    return PlayerObservation(0, tuple(hand), gold, "AFTER_DRAW", 0, 40,
                             ((), ()), ((), ()), ((), ()))


def discards(hand):
    return [env.Action(0, env.ActionType.DISCARD, tile=tile) for tile in sorted(set(hand))]


class BaselineAgentTests(unittest.TestCase):
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
