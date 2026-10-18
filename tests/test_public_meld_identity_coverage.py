from __future__ import annotations

import unittest

from workspace.vision.public_identity_labels import (
    PublicIdentityLabel,
    PublicIdentityManifest,
    load_public_identity_manifest,
)
from workspace.vision.public_identity_shadow_v0_2 import (
    SourceGroup,
    load_development_sources,
)
from workspace.vision.public_meld_identity_coverage import (
    audit_public_meld_identity_coverage,
)


def _label(label_id: str, tile_id: str, session: str, sha: str) -> PublicIdentityLabel:
    return PublicIdentityLabel(
        label_id=label_id,
        source_calibration_sample_id=f"sample_{label_id}",
        source_session=session,
        source_sha256=sha,
        image_path=f"fixtures/{label_id}.jpg",
        image_sha256="f" * 64,
        frame_index=0,
        time_ms=0,
        region="public_meld",
        tile_id=tile_id,
        bbox=(0.0, 0.0, 0.5, 0.5),
        status="approved",
        annotator="test",
    )


class PublicMeldIdentityCoverageTests(unittest.TestCase):
    def test_same_match_sessions_count_once(self):
        a = "a" * 64
        b = "b" * 64
        c = "c" * 64
        manifest = PublicIdentityManifest(
            labels=(
                _label("p6_a1", "P6", "match_a_hand1", a),
                _label("p6_a2", "P6", "match_a_hand7", b),
                _label("p6_b", "P6", "match_b", c),
            ),
            excluded_from_formal_promotion=True,
            development_only_reason="test only",
        )
        sources = {
            "match_a_hand1": SourceGroup("match_a_hand1", a, "match_a"),
            "match_a_hand7": SourceGroup("match_a_hand7", b, "match_a"),
            "match_b": SourceGroup("match_b", c, "match_b"),
        }

        report = audit_public_meld_identity_coverage(manifest, sources)
        row = next(row for row in report["classes"] if row["tile_id"] == "P6")

        self.assertEqual(row["approved_label_count"], 3)
        self.assertEqual(row["source_session_count"], 3)
        self.assertEqual(row["independent_match_group_count"], 2)
        self.assertTrue(row["new_match_query_support"])
        self.assertFalse(row["strict_existing_match_leave_one_out_support"])

    def test_three_match_groups_enable_strict_leave_one_out(self):
        shas = ["1" * 64, "2" * 64, "3" * 64]
        manifest = PublicIdentityManifest(
            labels=tuple(
                _label(f"s4_{index}", "S4", f"session_{index}", sha)
                for index, sha in enumerate(shas)
            ),
            excluded_from_formal_promotion=True,
            development_only_reason="test only",
        )
        sources = {
            f"session_{index}": SourceGroup(
                f"session_{index}", sha, f"match_{index}"
            )
            for index, sha in enumerate(shas)
        }

        report = audit_public_meld_identity_coverage(manifest, sources)
        row = next(row for row in report["classes"] if row["tile_id"] == "S4")

        self.assertEqual(row["independent_match_group_count"], 3)
        self.assertTrue(row["new_match_query_support"])
        self.assertTrue(row["strict_existing_match_leave_one_out_support"])
        self.assertEqual(
            row["additional_independent_match_groups_needed_for_leave_one_out"], 0
        )

    def test_unregistered_or_sha_mismatched_source_fails_closed(self):
        sha = "a" * 64
        manifest = PublicIdentityManifest(
            labels=(_label("p1", "P1", "query", sha),),
            excluded_from_formal_promotion=True,
            development_only_reason="test only",
        )

        with self.assertRaisesRegex(ValueError, "source not registered"):
            audit_public_meld_identity_coverage(manifest, {})

        with self.assertRaisesRegex(ValueError, "source SHA mismatch"):
            audit_public_meld_identity_coverage(
                manifest,
                {"query": SourceGroup("query", "b" * 64, "match")},
            )

    def test_current_repository_has_cross_match_p6_and_s4_support(self):
        manifest = load_public_identity_manifest(
            "references/vision/2026-09-22/public_identity_labels_v0_1.json"
        )
        sources = load_development_sources(
            "references/vision/2026-09-24/"
            "public_identity_source_groups.development.json"
        )
        report = audit_public_meld_identity_coverage(manifest, sources)

        self.assertGreaterEqual(report["approved_public_meld_labels"], 21)
        self.assertGreaterEqual(report["distinct_public_meld_classes"], 17)
        self.assertGreaterEqual(report["distinct_independent_match_groups"], 4)
        self.assertIn("P6", report["new_match_query_supported_classes"])
        self.assertIn("S4", report["new_match_query_supported_classes"])
        self.assertFalse(report["changes_runtime_behavior"])
        self.assertFalse(report["formal_promotion_evidence"])
        self.assertFalse(report["safe_for_hint"])
        self.assertFalse(report["safe_for_executor"])


if __name__ == "__main__":
    unittest.main()
