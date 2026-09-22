from __future__ import annotations

from pathlib import Path
import unittest

from huian.evidence.timeline import (
    HandContext,
    HandSettlement,
    HandTimeline,
    TimelineEvent,
    load_timeline,
    render_markdown,
)


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = ROOT / "references" / "matches" / "match_evidence_002_double_you"
SAMPLE_JSON = SAMPLE_DIR / "hand_08_timeline.json"
SAMPLE_MD = SAMPLE_DIR / "hand_08_timeline.md"


class HandTimelineTests(unittest.TestCase):
    def test_real_archived_sample_validates_and_render_is_reproducible(self):
        timeline = load_timeline(SAMPLE_JSON)
        self.assertEqual(timeline.evidence_id, "match_evidence_002_double_you")
        self.assertEqual(timeline.hand_index, 8)
        self.assertEqual(timeline.settlement.win_type, "DOUBLE_YOU")
        self.assertEqual(timeline.settlement.net_score, 264)
        self.assertEqual(render_markdown(timeline), SAMPLE_MD.read_text(encoding="utf-8"))

    def test_unsorted_events_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "sorted by timestamp"):
            HandTimeline(
                evidence_id="test",
                hand_index=1,
                source_sha256=None,
                duration_seconds=10.0,
                geometry=None,
                context=HandContext(),
                events=(
                    TimelineEvent(5.0, "player", "DISCARD", "direct_observation"),
                    TimelineEvent(4.0, "player", "DRAW", "direct_observation"),
                ),
            )

    def test_event_past_source_duration_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "exceeds source duration"):
            HandTimeline(
                evidence_id="test",
                hand_index=1,
                source_sha256=None,
                duration_seconds=3.0,
                geometry=None,
                context=HandContext(),
                events=(
                    TimelineEvent(3.1, "system", "SETTLEMENT_PAGE", "direct_observation"),
                ),
            )

    def test_non_conserving_score_pair_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "conserving 2000"):
            HandSettlement(scores_after=(1001, 1000))

    def test_unknown_values_remain_explicit_in_markdown(self):
        timeline = HandTimeline(
            evidence_id="unknown_case",
            hand_index=1,
            source_sha256=None,
            duration_seconds=None,
            geometry=None,
            context=HandContext(),
            events=(
                TimelineEvent(
                    0.0,
                    "unknown",
                    "UNRESOLVED_NODE",
                    "unknown",
                    unknown_rules=("rule.pending",),
                ),
            ),
            settlement=HandSettlement(unknown_rules=("settlement.pending",)),
        )
        rendered = render_markdown(timeline)
        self.assertIn("UNKNOWN", rendered)
        self.assertIn("rule.pending", rendered)
        self.assertIn("settlement.pending", rendered)

    def test_observed_score_delta_must_match_recorded_net(self):
        with self.assertRaisesRegex(ValueError, "winner score delta"):
            HandSettlement(
                winner=0,
                net_score=20,
                scores_before=(1000, 1000),
                scores_after=(1010, 990),
            )


if __name__ == "__main__":
    unittest.main()
