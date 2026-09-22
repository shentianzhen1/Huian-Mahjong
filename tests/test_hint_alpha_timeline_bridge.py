import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from huian.evidence.timeline import load_timeline, render_markdown
from workspace.hint_alpha import EvidenceSession
from workspace.hint_alpha.timeline_bridge import (
    build_timeline_draft,
    load_closed_session,
    write_timeline_draft,
)


class FakeImage:
    def save(self, path, format=None):
        path.write_bytes(b"fake-png")


class HintAlphaTimelineBridgeTests(unittest.TestCase):
    def _closed_session(self, root):
        session = EvidenceSession(root, metadata={"test": True}, session_id="bridge_case")
        session.mark(
            "PUBLIC_STATE",
            {
                "observation": {
                    "top_right_score": 1100,
                    "bottom_left_score": 900,
                    "hand_number": 3,
                    "remaining_tiles": 72,
                    "issues": [],
                    "safe_for_executor": False,
                }
            },
            source={"sequence": 10, "monotonic": 100.0},
        )
        session.mark_unknown(
            ("settlement.gang_hu",),
            source={"sequence": 11, "monotonic": 101.0},
        )
        frame = session.save_frame(
            FakeImage(),
            "settlement_page",
            source={"sequence": 12, "monotonic": 102.0},
        )
        session.mark(
            "SETTLEMENT_PAGE",
            {"frame": str(frame.relative_to(session.path))},
            source={"sequence": 12, "monotonic": 102.0},
        )
        session.close("test")
        return session

    def test_machine_values_remain_unknown_review_details(self):
        with TemporaryDirectory() as root:
            session = self._closed_session(root)
            timeline = build_timeline_draft(session.path, hand_index=3)

            self.assertEqual(timeline.hand_index, 3)
            self.assertIsNone(timeline.context.initial_scores)
            self.assertIsNone(timeline.context.gold_tile)
            self.assertEqual(timeline.settlement.evidence_level, "unknown")
            self.assertIsNone(timeline.settlement.net_score)
            self.assertTrue(timeline.events)
            self.assertTrue(
                all(event.evidence_level == "unknown" for event in timeline.events)
            )

            public = next(
                event
                for event in timeline.events
                if event.kind == "HINT_ALPHA_PUBLIC_STATE"
            )
            observed = public.details["payload"]["observation"]
            self.assertEqual(
                (observed["top_right_score"], observed["bottom_left_score"]),
                (1100, 900),
            )
            self.assertTrue(public.details["requires_human_review"])
            self.assertFalse(
                any(
                    event.evidence_level in {
                        "direct_observation",
                        "player_confirmed",
                        "derived_from_confirmed",
                    }
                    for event in timeline.events
                )
            )

    def test_unknown_rule_ids_and_settlement_candidate_are_preserved(self):
        with TemporaryDirectory() as root:
            session = self._closed_session(root)
            timeline = build_timeline_draft(session.path, hand_index=3)
            unknown = next(event for event in timeline.events if event.kind == "UNKNOWN_RULE")
            self.assertEqual(unknown.unknown_rules, ("settlement.gang_hu",))

            settlement = next(
                event
                for event in timeline.events
                if event.kind == "SETTLEMENT_PAGE_CANDIDATE"
            )
            self.assertEqual(settlement.screen_evidence, "frames/00004_settlement_page.png")
            self.assertEqual(settlement.evidence_level, "unknown")

    def test_export_round_trip_is_canonical_and_deterministic(self):
        with TemporaryDirectory() as root:
            session = self._closed_session(root)
            json_path, md_path = write_timeline_draft(
                session.path,
                hand_index=3,
                source_sha256="a" * 64,
                source_label="reviewed local recording candidate",
            )
            loaded = load_timeline(json_path)
            self.assertEqual(loaded.source_sha256, "a" * 64)
            self.assertEqual(render_markdown(loaded), md_path.read_text(encoding="utf-8"))
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertIn("requires_human_review", payload["context"]["room_options"])

    def test_live_session_is_rejected_until_closed(self):
        with TemporaryDirectory() as root:
            session = EvidenceSession(root, session_id="live")
            session.mark("RULE_EVIDENCE", {"frame": "frames/a.png"})
            with self.assertRaisesRegex(ValueError, "completion.json"):
                load_closed_session(session.path)
            session.close("test")

    def test_reviewer_must_choose_a_range_with_reviewable_events(self):
        with TemporaryDirectory() as root:
            session = self._closed_session(root)
            with self.assertRaisesRegex(ValueError, "no reviewable"):
                build_timeline_draft(
                    session.path,
                    hand_index=3,
                    start_seq=1,
                    end_seq=1,
                )

    def test_bridge_does_not_infer_hand_index_from_public_state(self):
        with TemporaryDirectory() as root:
            session = self._closed_session(root)
            with self.assertRaisesRegex(ValueError, "hand_index"):
                build_timeline_draft(session.path, hand_index=0)


if __name__ == "__main__":
    unittest.main()
