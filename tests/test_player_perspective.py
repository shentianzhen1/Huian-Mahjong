from __future__ import annotations

from pathlib import Path
import unittest

from workspace.vision.player_perspective import (
    PlayerPerspectiveEvidence,
    PlayerPerspectiveManifest,
    load_player_perspective_manifest,
    resolve_player_perspective,
)


ROOT = Path(__file__).resolve().parents[1]
PERSPECTIVE = (
    ROOT / "references" / "vision" / "2026-09-22"
    / "player_perspective_v0_1.json"
)


class PlayerPerspectiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_player_perspective_manifest(PERSPECTIVE)

    def test_archived_sessions_lock_local_player_to_seat_zero(self):
        self.assertEqual(len(self.manifest.entries), 2)
        for entry in self.manifest.entries:
            self.assertEqual(entry.player_seat, 0)
            self.assertEqual(entry.status, "fixture_confirmed")
            self.assertTrue(entry.evidence_ref.startswith("tests/fixtures/"))

    def test_resolve_by_session_or_source_hash(self):
        entry = self.manifest.entries[0]
        by_session = resolve_player_perspective(
            manifest=self.manifest,
            source_session=entry.source_session,
        )
        by_hash = resolve_player_perspective(
            manifest=self.manifest,
            source_sha256=entry.source_sha256,
        )
        self.assertEqual(by_session.player_seat, 0)
        self.assertEqual(by_hash.player_seat, 0)
        self.assertTrue(by_session.resolved)
        self.assertTrue(by_hash.resolved)

    def test_matching_session_and_sha_resolve_the_same_entry(self):
        entry = self.manifest.entries[0]
        result = resolve_player_perspective(
            manifest=self.manifest,
            source_session=entry.source_session,
            source_sha256=entry.source_sha256,
        )
        self.assertTrue(result.resolved)
        self.assertEqual(result.player_seat, entry.player_seat)

    def test_mismatched_known_session_and_known_hash_fail_even_with_same_seat(self):
        first, second = self.manifest.entries
        self.assertEqual(first.player_seat, second.player_seat)
        result = resolve_player_perspective(
            manifest=self.manifest,
            source_session=first.source_session,
            source_sha256=second.source_sha256,
        )
        self.assertIsNone(result.player_seat)
        self.assertEqual(result.issues, ("player_source_identity_conflict",))

    def test_known_session_with_unknown_hash_does_not_silently_match(self):
        entry = self.manifest.entries[0]
        result = resolve_player_perspective(
            manifest=self.manifest,
            source_session=entry.source_session,
            source_sha256="a" * 64,
        )
        self.assertIsNone(result.player_seat)
        self.assertEqual(result.issues, ("player_source_identity_conflict",))

    def test_explicit_runtime_seat_cannot_override_archived_source_mismatch(self):
        first, second = self.manifest.entries
        result = resolve_player_perspective(
            manifest=self.manifest,
            source_session=first.source_session,
            source_sha256=second.source_sha256,
            explicit_player_seat=first.player_seat,
        )
        self.assertIsNone(result.player_seat)
        self.assertEqual(result.issues, ("player_source_identity_conflict",))

    def test_new_unarchived_source_pair_can_still_use_explicit_mapping(self):
        result = resolve_player_perspective(
            manifest=self.manifest,
            source_session="fresh_live_source",
            source_sha256="f" * 64,
            explicit_player_seat=1,
            explicit_evidence_ref="capture_profile:seat=1",
        )
        self.assertTrue(result.resolved)
        self.assertEqual(result.player_seat, 1)
        self.assertEqual(result.source, "explicit_runtime_config")

    def test_unknown_source_never_defaults_to_seat_zero(self):
        result = resolve_player_perspective(
            manifest=self.manifest,
            source_session="new_live_session",
        )
        self.assertIsNone(result.player_seat)
        self.assertEqual(result.issues, ("player_seat_unresolved",))

    def test_explicit_runtime_config_can_resolve_live_source(self):
        result = resolve_player_perspective(
            manifest=self.manifest,
            source_session="new_live_session",
            explicit_player_seat=0,
            explicit_evidence_ref="capture_profile:local_player_seat=0",
        )
        self.assertEqual(result.player_seat, 0)
        self.assertEqual(result.source, "explicit_runtime_config")
        self.assertTrue(result.resolved)

    def test_explicit_config_conflict_with_archived_evidence_fails_closed(self):
        entry = self.manifest.entries[0]
        result = resolve_player_perspective(
            manifest=self.manifest,
            source_session=entry.source_session,
            explicit_player_seat=1,
        )
        self.assertIsNone(result.player_seat)
        self.assertIn("player_seat_evidence_conflict", result.issues)

    def test_duplicate_session_mapping_is_rejected(self):
        seed = self.manifest.entries[0]
        duplicate = PlayerPerspectiveEvidence(
            perspective_id="duplicate",
            source_session=seed.source_session,
            source_sha256=None,
            player_seat=1,
            status="fixture_confirmed",
            evidence_ref="tests/fixtures/other.json",
        )
        with self.assertRaises(ValueError):
            PlayerPerspectiveManifest(
                entries=(*self.manifest.entries, duplicate)
            )



if __name__ == "__main__":
    unittest.main()
