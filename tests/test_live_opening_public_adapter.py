from __future__ import annotations

from dataclasses import replace
import unittest

from huian._legacy import env
from workspace.vision.live_opening_fact import (
    LiveOpeningFact,
    LiveOpeningFactStatus,
)
from workspace.vision.live_opening_public_adapter import (
    gold_observation_from_live_opening_fact,
    open_gold_action_from_live_opening_fact,
)
from workspace.vision.public_match_reconstruction import (
    EvidenceGrade,
    ObservationKind,
    PublicActionKind,
)


def trusted_fact(*, gold_tile: str = "B") -> LiveOpeningFact:
    return LiveOpeningFact(
        timestamp_seconds=12.5,
        source_session="live-session",
        stream_epoch=3,
        status=LiveOpeningFactStatus.TRUSTED,
        gold_tile=gold_tile,
        gold_trusted=True,
        source_kind="VISIBLE_FINAL_GOLD_MULTIFRAME",
        state_tracker_ready=True,
        safe_for_environment_state=False,
        safe_for_executor=False,
        selection_inference_used=False,
        issues=(),
    )


class LiveOpeningPublicAdapterTests(unittest.TestCase):
    def test_trusted_visible_gold_becomes_existing_open_gold_action(self) -> None:
        fact = trusted_fact()

        observation = gold_observation_from_live_opening_fact(fact)
        action = open_gold_action_from_live_opening_fact(fact)

        self.assertIsNotNone(observation)
        assert observation is not None
        self.assertEqual(observation.kind, ObservationKind.GOLD)
        self.assertEqual(observation.actor, "system")
        self.assertEqual(observation.tile, "B")
        self.assertEqual(observation.confidence, 1.0)
        self.assertEqual(
            observation.details["confidence_semantics"],
            "trusted_gate_boolean_not_classifier_score",
        )
        self.assertFalse(observation.details["selection_inference_used"])

        self.assertIsNotNone(action)
        assert action is not None
        self.assertEqual(action.kind, PublicActionKind.OPEN_GOLD)
        self.assertEqual(action.evidence_grade, EvidenceGrade.DIRECT)
        self.assertEqual(action.actor, "system")
        self.assertEqual(action.tile, "B")
        self.assertEqual(action.details["source_session"], "live-session")
        self.assertEqual(action.details["stream_epoch"], 3)

    def test_unknown_fact_emits_no_public_gold_observation_or_action(self) -> None:
        fact = replace(
            trusted_fact(),
            status=LiveOpeningFactStatus.UNKNOWN,
            gold_tile=None,
            gold_trusted=False,
            source_kind="UNKNOWN",
            state_tracker_ready=False,
            issues=("live_gold_untrusted",),
        )

        self.assertIsNone(gold_observation_from_live_opening_fact(fact))
        self.assertIsNone(open_gold_action_from_live_opening_fact(fact))

    def test_inferred_or_privileged_fact_is_rejected_defensively(self) -> None:
        inferred = replace(trusted_fact(), selection_inference_used=True)
        environment_safe = replace(trusted_fact(), safe_for_environment_state=True)
        executor_safe = replace(trusted_fact(), safe_for_executor=True)

        for fact in (inferred, environment_safe, executor_safe):
            with self.subTest(fact=fact):
                self.assertIsNone(gold_observation_from_live_opening_fact(fact))
                self.assertIsNone(open_gold_action_from_live_opening_fact(fact))

    def test_flower_or_invalid_identity_cannot_enter_public_open_gold(self) -> None:
        flower = next(iter(env.FLOWERS))
        for tile in (flower, "NOT_A_TILE"):
            with self.subTest(tile=tile):
                fact = trusted_fact(gold_tile=tile)
                self.assertIsNone(gold_observation_from_live_opening_fact(fact))
                self.assertIsNone(open_gold_action_from_live_opening_fact(fact))

    def test_public_action_contains_no_hidden_selection_metadata(self) -> None:
        action = open_gold_action_from_live_opening_fact(trusted_fact())

        self.assertIsNotNone(action)
        assert action is not None
        forbidden = {
            "dice_total",
            "opening_wall_index",
            "wall_index",
            "random_seed",
            "rng_seed",
            "inferred_gold_tile",
        }
        self.assertTrue(forbidden.isdisjoint(action.details))
        self.assertFalse(action.details["selection_inference_used"])
        self.assertFalse(action.details["safe_for_environment_state"])
        self.assertFalse(action.details["safe_for_executor"])


if __name__ == "__main__":
    unittest.main()
