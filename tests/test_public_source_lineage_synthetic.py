"""Synthetic-only #69 source lineage checks; no original video hashes or coordinates."""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from workspace.vision.public_source_lineage import (
    compare_sources, development_lineage_report, load_lineage, verify_local_source,
)


def row(session: str, payload: bytes, group: str) -> dict:
    return {
        "source_session": session,
        "source_sha256": hashlib.sha256(payload).hexdigest(),
        "match_group": group,
        "capture_mode": "in_app_replay",
        "review_exposure": "previously_inspected",
        "development_only": True,
        "excluded_from_formal_promotion": True,
    }


class SyntheticSourceLineageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rows = [
            row("first_hand", b"synthetic hand one", "match_one"),
            row("second_hand", b"synthetic hand two", "match_one"),
            row("other_match", b"synthetic other match", "match_two"),
        ]
        self.registry = self.root / "registry.json"
        self.write()

    def write(self):
        self.registry.write_text(json.dumps({
            "schema_version": "public_source_lineage_v0_1",
            "sources": self.rows,
        }), encoding="utf-8")

    def test_same_match_different_clips_not_independent(self):
        d = load_lineage(self.registry)
        result = compare_sources(d["first_hand"], d["second_hand"])
        self.assertTrue(result["different_video_bytes"])
        self.assertFalse(result["different_recorded_match"])
        self.assertFalse(result["formal_promotion_eligible"])

    def test_separate_development_match_not_blind_holdout(self):
        d = load_lineage(self.registry)
        result = compare_sources(d["first_hand"], d["other_match"])
        self.assertTrue(result["different_recorded_match"])
        self.assertFalse(result["formal_promotion_eligible"])
        report = development_lineage_report(self.registry)
        self.assertEqual(report["clips"], 3)
        self.assertEqual(report["distinct_recorded_matches"], 2)
        self.assertEqual(report["formal_promotion_eligible_clips"], 0)
        self.assertFalse(report["safe_for_executor"])

    def test_hash_verification_fails_closed(self):
        source = load_lineage(self.registry)["first_hand"]
        file = self.root / "fake.mp4"
        file.write_bytes(b"synthetic hand one")
        verify_local_source(file, source)
        file.write_bytes(b"mutated fake input")
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            verify_local_source(file, source)

    def test_conflicting_group_and_unsafe_promotion_rejected(self):
        self.rows[1]["source_sha256"] = self.rows[0]["source_sha256"]
        self.rows[1]["match_group"] = "conflicting_match"
        self.write()
        with self.assertRaisesRegex(ValueError, "conflicting match groups"):
            load_lineage(self.registry)
        original = load_lineage(self._fresh_registry())["first_hand"]
        with self.assertRaisesRegex(ValueError, "cannot certify promotion"):
            replace(original, excluded_from_formal_promotion=False)

    def _fresh_registry(self):
        self.rows = [
            row("first_hand", b"synthetic hand one", "match_one"),
            row("second_hand", b"synthetic hand two", "match_one"),
            row("other_match", b"synthetic other match", "match_two"),
        ]
        self.write()
        return self.registry

    def test_reject_duplicate_session_and_invalid_digest(self):
        self.rows.append(dict(self.rows[0]))
        self.write()
        with self.assertRaisesRegex(ValueError, "duplicate source session"):
            load_lineage(self.registry)
        self.rows.pop()
        self.rows[0]["source_sha256"] = "invalid"
        self.write()
        with self.assertRaisesRegex(ValueError, "exact SHA256"):
            load_lineage(self.registry)


if __name__ == "__main__":
    unittest.main()
