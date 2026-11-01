import json
from pathlib import Path
import unittest

from workspace.vision.concealed_template_match_lineage import (
    canonicalize_match_group,
    load_concealed_template_lineage,
    qualify_concealed_template_labels,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = (
    ROOT
    / "references/vision/2026-10-01/"
    "concealed_template_match_lineage.development.json"
)
TRUTH_SEED = (
    ROOT
    / "references/vision/2026-10-07/"
    "whole_hand_truth_seed_20260926_first_hand_v0_1.json"
)
HAND234 = (
    ROOT
    / "references/vision/2026-10-02/"
    "issue69_hand234_source_segmentation_v0_1.json"
)
HARVEST = (
    ROOT
    / "references/vision/2026-10-03/"
    "existing_video_meld_face_harvest_spec_v0_1.json"
)


class Sep26OriginalMatchLineageTests(unittest.TestCase):
    def test_known_sep26_aliases_collapse_to_one_original_match(self):
        canonical = "reviewed_match_2026_09_26_eight_hand"
        aliases = {
            "reviewed_match_2026_09_26_first_hand",
            "reviewed_match_2026_09_26_hands_2_to_4",
            canonical,
        }
        self.assertEqual(
            {canonicalize_match_group(group) for group in aliases},
            {canonical},
        )

    def test_existing_first_hand_registry_entry_loads_as_canonical_eight_hand(self):
        registry = load_concealed_template_lineage(REGISTRY)
        first_hand_sha = (
            "fba5f67d244fb5bdc916f24707de288fef939a9444fa66bec21347e52bd64fc3"
        )
        self.assertEqual(
            registry[first_hand_sha].match_group,
            "reviewed_match_2026_09_26_eight_hand",
        )

    def test_any_sep26_query_alias_excludes_same_source_even_with_new_session_name(self):
        registry = load_concealed_template_lineage(REGISTRY)
        first_hand_sha = (
            "fba5f67d244fb5bdc916f24707de288fef939a9444fa66bec21347e52bd64fc3"
        )
        row = {
            "tile_id": "M6",
            "source_session": "invented_new_session_name",
            "sha256": first_hand_sha,
        }
        for query_group in (
            "reviewed_match_2026_09_26_first_hand",
            "reviewed_match_2026_09_26_hands_2_to_4",
            "reviewed_match_2026_09_26_eight_hand",
        ):
            with self.subTest(query_group=query_group):
                accepted, report = qualify_concealed_template_labels(
                    [row],
                    registry,
                    query_match_group=query_group,
                )
                self.assertEqual(accepted, [])
                self.assertEqual(
                    report["excluded_same_original_match_count"],
                    1,
                )
                self.assertFalse(
                    report["source_session_used_as_independence_signal"]
                )

    def test_frozen_sep26_evidence_aliases_resolve_to_one_match(self):
        truth_seed = json.loads(TRUTH_SEED.read_text(encoding="utf-8"))
        hand234 = json.loads(HAND234.read_text(encoding="utf-8"))
        harvest = json.loads(HARVEST.read_text(encoding="utf-8"))

        groups = {
            truth_seed["source_grouping"]["original_match_group"],
            hand234["source"]["original_match_group"],
            harvest["conservative_original_match_group"],
            *harvest["excluded_same_match_aliases"],
        }
        self.assertEqual(
            {canonicalize_match_group(group) for group in groups},
            {"reviewed_match_2026_09_26_eight_hand"},
        )
        self.assertFalse(
            truth_seed["source_grouping"]["source_session_is_independence_signal"]
        )


if __name__ == "__main__":
    unittest.main()
