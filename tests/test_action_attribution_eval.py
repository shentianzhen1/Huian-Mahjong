"""Synthetic contract tests; never report these numbers as real-video accuracy."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.vision.action_attribution_eval import (
    SCHEMA_VERSION,
    ActionPrediction,
    PredictionBatch,
    ReviewedSpan,
    TruthBatch,
    TruthEvent,
    evaluate_attribution,
    load_predictions,
    load_truth,
    prediction_from_action,
)
from workspace.vision.public_match_reconstruction import (
    EvidenceGrade,
    PublicActionKind,
    ReconstructedAction,
)


SHA_A = "a" * 64
SHA_B = "b" * 64


def span(*, epoch: int = 0, start: float = 0.0, end: float = 30.0) -> ReviewedSpan:
    return ReviewedSpan(
        stream_epoch=epoch,
        start_seconds=start,
        end_seconds=end,
        first_frame=int(start * 30),
        last_frame=int(end * 30),
        evidence_refs=("synthetic:reviewed-frames",),
    )


def event(
    t: float = 2.0,
    *,
    actor: str = "opponent",
    kind: str = "DISCARD",
    tile: str | None = "P5",
    turn_actor: str | None = "opponent",
    epoch: int = 0,
) -> TruthEvent:
    return TruthEvent(
        timestamp_seconds=t,
        stream_epoch=epoch,
        frame=int(t * 30),
        kind=kind,
        actor=actor,
        turn_actor=turn_actor,
        tile=tile,
        evidence_refs=(f"synthetic:frame:{int(t * 30)}",),
    )


def truth(
    events: tuple[TruthEvent, ...] | None = None,
    *,
    spans: tuple[ReviewedSpan, ...] | None = None,
    sha: str = SHA_A,
) -> TruthBatch:
    return TruthBatch(
        source_session="synthetic-session-a",
        source_sha256=sha,
        review_kind="synthetic_contract",
        truth_frozen=True,
        spans=spans if spans is not None else (span(),),
        events=events if events is not None else (event(),),
    )


def prediction(
    t: float = 2.1,
    *,
    actor: str = "opponent",
    kind: str = "DISCARD",
    tile: str | None = "P5",
    turn_actor: str | None = "opponent",
    epoch: int | None = 0,
    session: str | None = "synthetic-session-a",
    grade: str = "CORROBORATED",
    refs: tuple[str, ...] = ("synthetic:machine-frame:63",),
) -> ActionPrediction:
    return ActionPrediction(
        timestamp_seconds=t,
        source_session=session,
        stream_epoch=epoch,
        kind=kind,
        actor=actor,
        turn_actor=turn_actor,
        evidence_grade=grade,
        evidence_refs=refs,
        tile=tile,
    )


def batch(*actions: ActionPrediction, sha: str = SHA_A) -> PredictionBatch:
    return PredictionBatch(source_sha256=sha, actions=actions)


class AttributionEvaluationTests(unittest.TestCase):
    def test_exact_match_measures_actor_and_explicit_turn(self):
        result = evaluate_attribution(truth(), batch(prediction()))
        self.assertEqual(result["true_positives"], 1)
        self.assertEqual(result["false_positives"], 0)
        self.assertEqual(result["false_negatives"], 0)
        self.assertEqual(result["event_precision"], 1.0)
        self.assertEqual(result["event_recall"], 1.0)
        self.assertEqual(result["turn_accuracy_when_known"], 1.0)
        self.assertEqual(result["turn_coverage_on_labeled_aligned"], 1.0)
        self.assertFalse(result["formal_promotion_evidence"])
        self.assertFalse(result["safe_for_executor"])
        self.assertEqual(result["review_kind"], "synthetic_contract")

    def test_wrong_actor_is_aligned_misattribution_not_invisible_to_metrics(self):
        result = evaluate_attribution(
            truth(),
            batch(prediction(actor="player", turn_actor="opponent")),
        )
        self.assertEqual(result["aligned_events"], 1)
        self.assertEqual(result["wrong_actor"], 1)
        self.assertEqual(result["true_positives"], 0)
        self.assertEqual(result["false_positives"], 1)
        self.assertEqual(result["false_negatives"], 1)
        self.assertEqual(result["turn_correct"], 1)

    def test_wrong_turn_is_independent_from_action_actor(self):
        result = evaluate_attribution(
            truth(),
            batch(prediction(turn_actor="player")),
        )
        self.assertEqual(result["true_positives"], 1)
        self.assertEqual(result["wrong_actor"], 0)
        self.assertEqual(result["turn_wrong"], 1)
        self.assertEqual(result["turn_correct"], 0)
        self.assertEqual(result["turn_accuracy_when_known"], 0.0)

    def test_unsupported_turn_not_inferred_from_known_actor(self):
        result = evaluate_attribution(
            truth(),
            batch(prediction(turn_actor=None)),
        )
        self.assertEqual(result["true_positives"], 1)
        self.assertEqual(result["turn_unknown"], 1)
        self.assertEqual(result["turn_coverage_on_labeled_aligned"], 0.0)
        self.assertIsNone(result["turn_accuracy_when_known"])

    def test_unknown_action_abstains_and_truth_remains_missed(self):
        result = evaluate_attribution(
            truth(),
            batch(prediction(actor="unknown", kind="UNKNOWN_ACTION",
                             grade="UNKNOWN", tile=None, turn_actor=None)),
        )
        self.assertEqual(result["abstentions"], 1)
        self.assertEqual(result["true_positives"], 0)
        self.assertEqual(result["false_positives"], 0)
        self.assertEqual(result["false_negatives"], 1)
        self.assertEqual(result["truth_events_with_nearby_abstention_and_no_match"], 1)
        self.assertIsNone(result["event_precision"])
        self.assertEqual(result["event_recall"], 0.0)

    def test_unknown_grade_or_missing_evidence_does_not_gain_credit(self):
        result = evaluate_attribution(
            truth(),
            batch(
                prediction(t=2.0, grade="UNKNOWN"),
                prediction(t=2.1, refs=()),
            ),
        )
        self.assertEqual(result["abstentions"], 2)
        self.assertEqual(result["true_positives"], 0)
        self.assertEqual(result["false_negatives"], 1)

    def test_outside_reviewed_span_and_other_source_are_not_misreported(self):
        result = evaluate_attribution(
            truth(),
            batch(
                prediction(session="other-session"),
                prediction(epoch=1),
                prediction(epoch=None),
                prediction(t=50.0),
            ),
        )
        self.assertEqual(result["out_of_scope_prediction_indexes"], [0, 1, 2, 3])
        self.assertEqual(result["false_positives"], 0)
        self.assertEqual(result["false_negatives"], 1)

    def test_capture_sha_mismatch_fails_closed_even_for_same_session_alias(self):
        with self.assertRaisesRegex(ValueError, "source_sha256"):
            evaluate_attribution(truth(), batch(prediction(), sha=SHA_B))

    def test_one_to_one_alignment_flags_extra_duplicate_prediction(self):
        result = evaluate_attribution(
            truth(),
            batch(prediction(t=2.0), prediction(t=2.1)),
        )
        self.assertEqual(result["aligned_events"], 1)
        self.assertEqual(result["true_positives"], 1)
        self.assertEqual(result["extra_prediction_indexes"], [1])
        self.assertEqual(result["false_positives"], 1)
        self.assertEqual(result["event_precision"], 0.5)

    def test_wrong_kind_and_tile_are_both_audited(self):
        result = evaluate_attribution(
            truth(),
            batch(prediction(kind="PENG", tile="M9")),
        )
        self.assertEqual(result["aligned_events"], 1)
        self.assertEqual(result["wrong_kind"], 1)
        self.assertEqual(result["wrong_tile"], 1)
        self.assertEqual(result["true_positives"], 0)

    def test_predictions_in_labeled_no_action_time_are_false_positives(self):
        result = evaluate_attribution(
            truth(),
            batch(prediction(t=2.0), prediction(t=20.0)),
        )
        self.assertEqual(result["true_positives"], 1)
        self.assertEqual(result["false_positives"], 1)
        self.assertEqual(result["false_negatives"], 0)

    def test_epoch_isolation_even_with_identical_timestamp_tile_and_actor(self):
        reviewed = truth(
            (event(t=2.0), event(t=2.0, epoch=1)),
            spans=(span(), span(epoch=1)),
        )
        result = evaluate_attribution(reviewed, batch(prediction(t=2.0, epoch=1)))
        self.assertEqual(result["aligned_events"], 1)
        self.assertEqual(result["missed_truth_indexes"], [0])
        self.assertEqual(result["false_negatives"], 1)

    def test_empty_prediction_is_not_fake_perfect_precision(self):
        result = evaluate_attribution(truth(), batch())
        self.assertEqual(result["false_negatives"], 1)
        self.assertIsNone(result["event_precision"])
        self.assertEqual(result["event_recall"], 0.0)

    def test_nearest_timestamps_pair_without_using_actor_for_alignment(self):
        t = truth(
            (event(2.0, actor="opponent"), event(3.0, actor="player")),
        )
        p = batch(
            prediction(t=3.1, actor="opponent"),
            prediction(t=2.1, actor="player"),
        )
        result = evaluate_attribution(t, p)
        self.assertEqual(result["aligned_events"], 2)
        self.assertEqual(result["wrong_actor"], 2)
        self.assertEqual(result["true_positives"], 0)

    def test_rejects_nonfinite_times_and_invalid_schema(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            prediction(t=float("nan"))
        with self.assertRaisesRegex(ValueError, "finite"):
            evaluate_attribution(truth(), batch(), tolerance_seconds=float("inf"))
        with self.assertRaisesRegex(ValueError, "positive"):
            evaluate_attribution(truth(), batch(), tolerance_seconds=0)
        with self.assertRaisesRegex(ValueError, "schema"):
            TruthBatch(
                source_session="a", source_sha256=SHA_A,
                review_kind="synthetic_contract", truth_frozen=True,
                spans=(span(),), events=(event(),), schema_version="bogus",
            )

    def test_rejects_unfrozen_empty_or_overlapping_manual_reviews(self):
        with self.assertRaisesRegex(ValueError, "frozen"):
            TruthBatch(
                source_session="a", source_sha256=SHA_A,
                review_kind="synthetic_contract", truth_frozen=False,
                spans=(span(),), events=(event(),),
            )
        with self.assertRaisesRegex(ValueError, "interval"):
            truth(spans=(span(), span(start=15.0, end=40.0)))
        with self.assertRaisesRegex(ValueError, "events are required"):
            truth(events=())
        with self.assertRaisesRegex(ValueError, "exactly one reviewed"):
            truth(events=(event(t=90.0),))

    def test_converter_preserves_only_explicit_turn_and_capture_lineage(self):
        action = ReconstructedAction(
            timestamp_seconds=2.0,
            actor="player",
            kind=PublicActionKind.CHI,
            evidence_grade=EvidenceGrade.CORROBORATED,
            confidence=0.8,
            claimed_tile="P5",
            meld=("P3", "P4", "P5"),
            evidence_refs=("synthetic:frame:60",),
            details={"source_session": "synthetic-session-a", "stream_epoch": 2},
        )
        prediction_result = prediction_from_action(action)
        self.assertEqual(prediction_result.kind, "CHI")
        self.assertEqual(prediction_result.tile, "P5")
        self.assertEqual(prediction_result.source_session, "synthetic-session-a")
        self.assertEqual(prediction_result.stream_epoch, 2)
        self.assertIsNone(prediction_result.turn_actor)


class AttributionJsonIoTests(unittest.TestCase):
    def test_separate_truth_and_predictions_load_and_score(self):
        truth_payload = {
            "schema_version": SCHEMA_VERSION,
            "source_session": "synthetic-session-a",
            "source_sha256": SHA_A,
            "review_kind": "synthetic_contract",
            "truth_frozen": True,
            "reviewed_intervals": [{
                "stream_epoch": 0,
                "start_seconds": 0,
                "end_seconds": 30,
                "first_frame": 0,
                "last_frame": 900,
                "evidence_refs": ["synthetic:reviewed:0-900"],
            }],
            "events": [{
                "timestamp_seconds": 2,
                "stream_epoch": 0,
                "frame": 60,
                "kind": "DISCARD",
                "actor": "opponent",
                "turn_actor": "opponent",
                "tile": "P5",
                "evidence_refs": ["synthetic:frame:60"],
            }],
        }
        predicted_payload = {
            "schema_version": SCHEMA_VERSION,
            "source_sha256": SHA_A,
            "actions": [{
                "timestamp_seconds": 2.1,
                "source_session": "synthetic-session-a",
                "stream_epoch": 0,
                "kind": "DISCARD",
                "actor": "opponent",
                "turn_actor": None,
                "tile": "P5",
                "evidence_grade": "CORROBORATED",
                "evidence_refs": ["synthetic:prediction:63"],
            }],
        }
        with tempfile.TemporaryDirectory() as folder:
            truth_path = Path(folder) / "manual_truth.json"
            predictions_path = Path(folder) / "predictions.json"
            truth_path.write_text(json.dumps(truth_payload), encoding="utf-8")
            predictions_path.write_text(json.dumps(predicted_payload), encoding="utf-8")
            result = evaluate_attribution(
                load_truth(truth_path),
                load_predictions(predictions_path),
            )
        self.assertEqual(result["true_positives"], 1)
        self.assertEqual(result["turn_unknown"], 1)
        self.assertEqual(result["review_kind"], "synthetic_contract")
        self.assertFalse(result["formal_promotion_evidence"])

    def test_prediction_json_without_source_sha_does_not_load(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad_predictions.json"
            path.write_text(
                json.dumps({"schema_version": SCHEMA_VERSION, "actions": []}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "source_sha256"):
                load_predictions(path)


if __name__ == "__main__":
    unittest.main()
