import json
from pathlib import Path
import unittest

from workspace.vision.concealed_class_lineage_audit import (
    audit_class_lineage,
    load_labels,
)
from workspace.vision.concealed_template_match_lineage import (
    load_concealed_template_lineage,
)


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset/tiles_runtime_v0_2"
LINEAGE = (
    ROOT
    / "references/vision/2026-10-01/"
    "concealed_template_match_lineage.development.json"
)
EVIDENCE = (
    ROOT
    / "references/vision/2026-10-07/"
    "m6_concealed_template_lineage_audit_v0_1.json"
)
UNRESOLVED_M6_SHA = (
    "781bfe34c40993effb0bb76b5d576f9c3df400784bbd1ed8820dc0c8aacdba82"
)


class M6ConcealedTemplateLineageAuditTests(unittest.TestCase):
    def test_tracked_m6_evidence_matches_current_dataset_and_lineage(self):
        labels = load_labels(DATASET)
        report = audit_class_lineage(
            labels,
            load_concealed_template_lineage(LINEAGE),
        )
        m6 = next(row for row in report["classes"] if row["tile_id"] == "M6")
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))

        self.assertEqual(m6["ordinary_template_count"], 2)
        self.assertEqual(m6["distinct_source_session_count"], 2)
        self.assertEqual(m6["reviewed_original_match_group_count"], 1)
        self.assertEqual(
            m6["reviewed_original_match_groups"],
            ["reviewed_match_2026_09_19_eight_hand"],
        )
        self.assertEqual(m6["unresolved_source_sha_count"], 1)
        self.assertEqual(m6["unresolved_source_shas"], [UNRESOLVED_M6_SHA])

        self.assertEqual(
            evidence["ordinary_template_count"], m6["ordinary_template_count"]
        )
        self.assertEqual(
            evidence["ordinary_distinct_source_session_count"],
            m6["distinct_source_session_count"],
        )
        self.assertEqual(
            evidence["ordinary_reviewed_original_match_group_count"],
            m6["reviewed_original_match_group_count"],
        )
        self.assertEqual(
            evidence["ordinary_unresolved_source_shas"],
            m6["unresolved_source_shas"],
        )
        self.assertFalse(evidence["source_session_is_independent_match_evidence"])
        self.assertFalse(evidence["runtime_change_justified"])

    def test_gold_m6_asset_is_not_counted_as_ordinary_support(self):
        labels = load_labels(DATASET)
        gold_m6 = [
            row
            for row in labels
            if row.get("tile_id") == "M6"
            and row.get("gold_skin_only") is True
            and (row.get("approved") is True or row.get("status") == "approved")
        ]
        self.assertEqual(len(gold_m6), 1)
        self.assertEqual(
            gold_m6[0]["sha256"],
            "fba5f67d244fb5bdc916f24707de288fef939a9444fa66bec21347e52bd64fc3",
        )


if __name__ == "__main__":
    unittest.main()
