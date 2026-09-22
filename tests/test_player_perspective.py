from __future__ import annotations

import json
from pathlib import Path
import unittest

from PIL import Image

from workspace.vision.dealer_marker_detector import detect_dealer_marker
from workspace.vision.hand_context_assembler import assemble_hand_context
from workspace.vision.player_perspective import (
    PlayerPerspectiveEvidence,
    PlayerPerspectiveManifest,
    load_player_perspective_manifest,
    resolve_player_perspective,
)
from workspace.vision.public_match_reconstruction import ObservationKind, RawObservation
from workspace.vision.tiles_v0_1.public_state import PublicStateObservation


ROOT = Path(__file__).resolve().parents[1]
PERSPECTIVE = (
    ROOT / "references" / "vision" / "2026-09-22"
    / "player_perspective_v0_1.json"
)


def public_state(hand: int, top: int, bottom: int) -> PublicStateObservation:
    return PublicStateObservation(
        top_right_score=top,
        bottom_left_score=bottom,
        hand_number=hand,
        remaining_tiles=100,
        score_votes=3,
        hand_votes=3,
        remaining_votes=3,
        issues=(),
        safe_for_executor=False,
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

    def test_66fe_perspective_plus_marker_maps_opponent_dealer_to_seat_one(self):
        perspective = resolve_player_perspective(
            manifest=self.manifest,
            source_session="66fe863f_youjin100",
        )
        self.assertEqual(perspective.player_seat, 0)

        image = Image.open(
            ROOT
            / "references/gameplay/2026-09-15/66fe863f_youjin100"
            / "peng_offer_p1_035000ms.jpg"
        ).convert("RGB")
        marker = detect_dealer_marker(
            image,
            frame=1015,
            session="66fe863f_youjin100",
        )
        self.assertEqual(marker.actor, "opponent")
        dealer = marker.to_dealer_evidence(
            timestamp_seconds=35.0,
            player_seat=perspective.player_seat,
        )
        self.assertEqual(dealer.dealer_seat, 1)

        context = assemble_hand_context(
            public_state(5, 900, 1100),
            player_seat=perspective.player_seat,
            dealer_evidence=(dealer, dealer),
            gold_observations=(
                RawObservation(
                    35.1, "system", ObservationKind.GOLD,
                    tile="M1", evidence_refs=("fixture:gold",)
                ),
                RawObservation(
                    35.2, "system", ObservationKind.GOLD,
                    tile="M1", evidence_refs=("fixture:gold2",)
                ),
            ),
        )
        self.assertEqual(context.context.player_seat, 0)
        self.assertEqual(context.context.dealer, 1)
        self.assertEqual(context.context.initial_scores, (1100, 900))

    def test_b389_perspective_plus_marker_maps_player_dealer_to_seat_zero(self):
        perspective = resolve_player_perspective(
            manifest=self.manifest,
            source_session="b3892b34_zimo68",
        )
        image = Image.open(
            ROOT
            / "references/gameplay/2026-09-15/b3892b34_zimo68"
            / "chi_m4_offer_033000ms.jpg"
        ).convert("RGB")
        marker = detect_dealer_marker(
            image,
            frame=957,
            session="b3892b34_zimo68",
        )
        self.assertEqual(marker.actor, "player")
        dealer = marker.to_dealer_evidence(
            timestamp_seconds=33.0,
            player_seat=perspective.player_seat,
        )
        self.assertEqual(dealer.dealer_seat, 0)


if __name__ == "__main__":
    unittest.main()
