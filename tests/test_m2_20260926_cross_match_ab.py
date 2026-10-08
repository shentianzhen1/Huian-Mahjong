import json
from pathlib import Path
import unittest

from workspace.vision.concealed_template_match_lineage import canonicalize_match_group


ROOT = Path(__file__).resolve().parents[1]
REPORT = (
    ROOT
    / "references/vision/2026-10-08/"
    "m2_20260926_cross_match_template_ab_v0_1.json"
)
STAGING = (
    ROOT
    / "references/vision/2026-10-08/"
    "reviewed_tile_intake_staging_20260926_m2.jsonl"
)


class M2Sep26CrossMatchABTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))
        cls.staging_rows = [
            json.loads(line)
            for line in STAGING.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_support_and_query_are_different_original_matches(self):
        support = canonicalize_match_group(
            self.report["support_source"]["original_match_group"]
        )
        query = canonicalize_match_group(
            self.report["held_out_query_match"]["original_match_group"]
        )
        self.assertNotEqual(support, query)
        self.assertTrue(
            self.report["held_out_query_match"][
                "whole_original_match_held_out_from_support"
            ]
        )

    def test_same_match_variants_never_create_extra_independent_support(self):
        source = self.report["support_source"]
        self.assertEqual(
            canonicalize_match_group(source["legacy_match_group_alias"]),
            canonicalize_match_group(source["original_match_group"]),
        )
        self.assertFalse(source["same_match_variants_count_as_independent_support"])
        self.assertEqual(len(source["same_original_match_byte_variants"]), 2)
        policy = self.report["provenance_policy"]
        self.assertFalse(policy["source_session_is_independence_evidence"])
        self.assertFalse(policy["adjacent_frames_are_independent_sources"])
        self.assertFalse(policy["same_match_video_chunks_are_independent_sources"])
        self.assertFalse(policy["same_match_reencodes_are_independent_sources"])

    def test_reviewed_m2_geometry_and_private_asset_hashes_are_frozen(self):
        source = self.report["support_source"]
        self.assertEqual(
            source["source_sha256"],
            "05ef070ea185e7c224126eadd527e77075f8b85e86ed49326d981ead81fb5738",
        )
        self.assertEqual(source["frame_index"], 148)
        self.assertTrue(source["decoded_frame_pixel_exact_verified"])
        self.assertEqual(
            [
                (
                    row["slot"],
                    row["bbox"],
                    row["tile_id"],
                    row["sample_id"],
                    row["asset_sha256"],
                    row["pixel_exact_from_decoded_source_frame"],
                )
                for row in source["reviewed_m2_slots"]
            ],
            [
                (
                    6,
                    [1050, 1113, 123, 164],
                    "M2",
                    "tile_509c0534c997767f",
                    "bf84e155ce8de5b67d6e0543a992f28ce09c68a8d4ba94a24dbf19cef37aac80",
                    True,
                ),
                (
                    7,
                    [1176, 1114, 123, 163],
                    "M2",
                    "tile_64f124eb6a342eab",
                    "6d36389dc52fc722afa4ea68913c54d6962304711f2687bcd568d57e80a51921",
                    True,
                ),
            ],
        )
        self.assertEqual(
            source["tile_only_asset_hash_status"],
            "VERIFIED_PRIVATE_PIXEL_EXACT",
        )
        self.assertFalse(source["binary_assets_committed"])
        self.assertFalse(source["final_labels_updated"])
        self.assertFalse(source["runtime_template_bank_updated"])

    def test_staging_rows_match_deterministic_reviewed_intake_contract(self):
        self.assertEqual(len(self.staging_rows), 2)
        self.assertEqual(
            [row["id"] for row in self.staging_rows],
            ["tile_509c0534c997767f", "tile_64f124eb6a342eab"],
        )
        self.assertEqual(
            {row["source_session"] for row in self.staging_rows},
            {"session_real_20260926_eight_hand"},
        )
        self.assertEqual(
            {row["sha256"] for row in self.staging_rows},
            {"05ef070ea185e7c224126eadd527e77075f8b85e86ed49326d981ead81fb5738"},
        )
        self.assertEqual(
            [row["asset_sha256"] for row in self.staging_rows],
            [
                "bf84e155ce8de5b67d6e0543a992f28ce09c68a8d4ba94a24dbf19cef37aac80",
                "6d36389dc52fc722afa4ea68913c54d6962304711f2687bcd568d57e80a51921",
            ],
        )
        self.assertTrue(all(row["approved"] for row in self.staging_rows))
        self.assertTrue(all(row["tile_id"] == "M2" for row in self.staging_rows))
        self.assertTrue(
            all(row["asset_role"] == "development_prototype_only" for row in self.staging_rows)
        )

    def test_candidate_fixes_all_three_held_out_m2_rankings_without_threshold_change(self):
        report = self.report
        queries = report["held_out_query_match"]["queries"]
        self.assertEqual(len(queries), 3)
        self.assertTrue(all(row["truth"] == "M2" for row in queries))
        self.assertTrue(all(row["baseline_winner"] == "M3" for row in queries))
        self.assertTrue(all(row["candidate_winner"] == "M2" for row in queries))
        self.assertTrue(all(row["candidate_score_approx"] >= 0.82 for row in queries))
        ab = report["ab_summary"]
        self.assertEqual(ab["baseline_correct_top1"], 0)
        self.assertEqual(ab["candidate_correct_top1"], 3)
        self.assertEqual(ab["runtime_identity_threshold"], 0.82)
        self.assertFalse(ab["threshold_changed"])
        self.assertTrue(ab["all_three_candidate_m2_scores_above_runtime_threshold"])

    def test_side_effect_remains_below_acceptance_gate(self):
        side = self.report["side_effect_audit"]
        self.assertEqual(side["new_raw_m3_to_m2_flip_count"], 1)
        self.assertLess(side["highest_new_flip_score_approx"], 0.82)
        self.assertTrue(side["highest_new_flip_below_runtime_threshold"])
        self.assertEqual(side["wrong_accepted_delta_at_0_82"], 0)

    def test_report_cannot_be_misread_as_runtime_or_agent_promotion(self):
        report = self.report
        self.assertFalse(report["runtime_changed"])
        self.assertEqual(report["runtime_identity_threshold"], 0.82)
        self.assertEqual(report["current_agent"], "MeldAwareShantenAgent V0.10")
        self.assertEqual(report["hint_alpha"], "internal_read_only")
        self.assertFalse(report["executor_enabled"])
        self.assertFalse(report["formal_promotion_evidence"])
        self.assertFalse(report["safe_for_runtime"])
        self.assertFalse(report["safe_for_hint_promotion"])
        self.assertFalse(report["safe_for_executor"])


if __name__ == "__main__":
    unittest.main()
