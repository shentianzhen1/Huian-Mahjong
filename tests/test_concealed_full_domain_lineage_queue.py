import json
from pathlib import Path
import unittest

from workspace.vision.concealed_template_lineage_recovery import (
    build_concealed_identity_lineage_recovery_queue,
)
from workspace.vision.concealed_template_match_lineage import (
    load_concealed_template_lineage,
)


ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "dataset/tiles_runtime_v0_2/labels.jsonl"
LINEAGE = (
    ROOT
    / "references/vision/2026-10-01/"
    "concealed_template_match_lineage.development.json"
)
FROZEN = (
    ROOT
    / "references/vision/2026-10-07/"
    "concealed_full_domain_lineage_recovery_queue_v0_1.json"
)


class ConcealedFullDomainLineageQueueTests(unittest.TestCase):
    def test_full_runtime_domain_recovery_inventory_is_reproducible(self):
        labels = [
            json.loads(line)
            for line in LABELS.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        lineage = load_concealed_template_lineage(LINEAGE)
        generated = build_concealed_identity_lineage_recovery_queue(
            labels,
            lineage,
            target_classes=None,
        )
        frozen = json.loads(FROZEN.read_text(encoding="utf-8"))

        self.assertEqual(generated["items"], frozen["items"])
        self.assertEqual(
            generated["unresolved_source_count"],
            frozen["unresolved_source_count"],
        )
        self.assertEqual(
            generated["unresolved_label_count"],
            frozen["unresolved_label_count"],
        )
        self.assertEqual(frozen["unresolved_source_count"], 6)
        self.assertEqual(frozen["unresolved_label_count"], 78)
        self.assertEqual(frozen["exact_sha_lineage_qualified_label_count"], 62)
        self.assertEqual(frozen["exact_sha_lineage_qualified_class_count"], 28)
        self.assertEqual(
            frozen["strict_lineage_missing_classes"],
            ["M9", "P2", "S3", "S9", "SOUTH", "W"],
        )
        self.assertFalse(frozen["source_session_is_match_evidence"])
        self.assertFalse(frozen["safe_for_runtime"])
        self.assertFalse(frozen["safe_for_hint"])
        self.assertFalse(frozen["safe_for_executor"])


if __name__ == "__main__":
    unittest.main()
