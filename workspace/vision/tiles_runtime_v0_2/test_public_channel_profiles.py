from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image

from workspace.vision.public_channel_profiles import (
    audit_detection,
    load_channel_manifest,
)
from workspace.vision.public_detector_calibration import load_manifest
from workspace.vision.public_tile_detector import (
    detect_public_tile_geometry,
    target_coverage,
)


ROOT = Path(__file__).resolve().parents[3]
DETECTOR_MANIFEST = (
    ROOT
    / "references"
    / "vision"
    / "2026-09-22"
    / "public_detector_calibration_v0_1.json"
)
CHANNEL_MANIFEST = (
    ROOT
    / "references"
    / "vision"
    / "2026-09-22"
    / "public_channel_profiles_v0_1.json"
)


TARGET_PROFILE = {
    "66fe_opponent_discard_p1_035s": "central_action_focus_dev",
    "66fe_opponent_discard_s9_080s": "central_action_focus_dev",
    "b389_opponent_discard_m4_033s": "central_action_focus_dev",
    "b389_opponent_discard_p7_055s": "central_action_focus_dev",
    "66fe_opponent_discard_n_085s": "upper_public_single_dev",
    "66fe_player_peng_p1_040s": "player_exposed_group_dev",
    "66fe_player_added_kong_p1_070s": "player_exposed_group_dev",
    "66fe_player_chi_s789_082s": "player_exposed_group_dev",
    "b389_player_chi_m456_035s": "player_exposed_group_dev",
    "b389_player_chi_p678_057s": "player_exposed_group_dev",
}


class PublicChannelProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.detector_manifest = load_manifest(DETECTOR_MANIFEST)
        cls.channel_manifest = load_channel_manifest(CHANNEL_MANIFEST)
        cls.samples = {
            sample.sample_id: sample
            for sample in cls.detector_manifest.samples
        }

    def _detection(self, sample_id: str):
        sample = self.samples[sample_id]
        image = Image.open(ROOT / sample.image_path).convert("RGB")
        return detect_public_tile_geometry(
            image,
            frame=sample.frame_index,
            session=sample.source_session,
        )

    def test_profiles_are_development_only_and_evidence_ids_exist(self):
        manifest = self.channel_manifest
        self.assertTrue(manifest.excluded_from_formal_promotion)
        self.assertEqual(
            {profile.name for profile in manifest.profiles},
            {
                "central_action_focus_dev",
                "upper_public_single_dev",
                "player_exposed_group_dev",
            },
        )
        sample_ids = set(self.samples)
        for profile in manifest.profiles:
            self.assertTrue(profile.development_only)
            self.assertTrue(set(profile.evidence_sample_ids) <= sample_ids)

    def test_all_ten_reviewed_detector_targets_survive_channel_filtering(self):
        failures = []
        for sample_id, profile_name in TARGET_PROFILE.items():
            sample = self.samples[sample_id]
            assert sample.bbox is not None
            detection = self._detection(sample_id)
            profile = self.channel_manifest.profile(profile_name)
            audit = audit_detection(detection, profile)
            best = max(
                (
                    target_coverage(candidate.normalized_bbox, sample.bbox)
                    for candidate in audit.selected
                ),
                default=0.0,
            )
            threshold = 0.75 if sample.target == "discard" else 0.90
            if best < threshold:
                failures.append(
                    (
                        sample_id,
                        profile_name,
                        round(best, 6),
                        len(audit.selected),
                    )
                )
        self.assertEqual(failures, [])

    def test_channel_filter_reduces_candidate_load_on_all_locked_context_frames(self):
        raw_total = 0
        selected_total = 0
        per_profile_max = {
            "central_action_focus_dev": 0,
            "upper_public_single_dev": 0,
            "player_exposed_group_dev": 0,
        }

        for sample in self.detector_manifest.samples:
            image = Image.open(ROOT / sample.image_path).convert("RGB")
            detection = detect_public_tile_geometry(
                image,
                frame=sample.frame_index,
                session=sample.source_session,
            )
            raw_total += len(detection.candidates)
            for profile in self.channel_manifest.profiles:
                audit = audit_detection(detection, profile)
                count = len(audit.selected)
                selected_total += count
                per_profile_max[profile.name] = max(
                    per_profile_max[profile.name],
                    count,
                )

        self.assertGreater(raw_total, 0)
        self.assertLessEqual(
            selected_total,
            raw_total * 0.15,
            (raw_total, selected_total),
        )
        self.assertLessEqual(
            per_profile_max["central_action_focus_dev"],
            1,
        )
        self.assertLessEqual(
            per_profile_max["upper_public_single_dev"],
            1,
        )
        self.assertLessEqual(
            per_profile_max["player_exposed_group_dev"],
            2,
        )

    def test_central_focus_is_not_discard_specific(self):
        profile = self.channel_manifest.profile("central_action_focus_dev")
        self.assertEqual(profile.actor_policy, "external")
        self.assertEqual(profile.action_policy, "external")

        for sample_id in (
            "66fe_player_hand_fourth_p1_069s",
            "b389_player_hand_winning_m5_065s",
        ):
            sample = self.samples[sample_id]
            self.assertEqual(sample.target, "hand_reference")
            audit = audit_detection(self._detection(sample_id), profile)
            self.assertEqual(
                len(audit.selected),
                1,
                sample_id,
            )

    def test_upper_public_single_is_not_discard_specific(self):
        profile = self.channel_manifest.profile("upper_public_single_dev")
        self.assertEqual(profile.actor_policy, "external")
        self.assertEqual(profile.action_policy, "external")

        sample = self.samples["66fe_player_hand_after_s1_084s"]
        self.assertEqual(sample.target, "hand_reference")
        audit = audit_detection(
            self._detection(sample.sample_id),
            profile,
        )
        self.assertEqual(len(audit.selected), 1)

    def test_player_exposed_group_channel_keeps_action_external(self):
        profile = self.channel_manifest.profile("player_exposed_group_dev")
        self.assertEqual(profile.actor_policy, "player")
        self.assertEqual(profile.action_policy, "external")
        channel = profile.to_candidate_channel()
        self.assertEqual(channel.name, profile.name)
        self.assertEqual(channel.geometry_kinds, ("bottom_group",))


if __name__ == "__main__":
    unittest.main()
