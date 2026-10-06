import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from workspace.vision.concealed_template_local_sha_scan import (
    build_scan_report,
    load_target_shas,
    scan_exact_sha_matches,
)


ROOT = Path(__file__).resolve().parents[1]
QUEUE = (
    ROOT
    / "references/vision/2026-10-01/"
    "concealed_template_lineage_recovery_queue_v0_1.json"
)


class ConcealedTemplateLocalShaScanTests(unittest.TestCase):
    def test_resolved_frozen_queue_has_no_scan_targets(self):
        frozen = json.loads(QUEUE.read_text(encoding="utf-8"))
        self.assertEqual(frozen["unresolved_source_count"], 0)
        self.assertEqual(frozen["items"], [])
        with self.assertRaisesRegex(ValueError, "no unresolved SHA256 targets"):
            load_target_shas(QUEUE)

    def test_scan_only_reports_exact_sha_matches_and_never_auto_binds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wanted = root / "source.bin"
            other = root / "other.bin"
            wanted.write_bytes(b"exact-source")
            other.write_bytes(b"different-source")
            target = hashlib.sha256(wanted.read_bytes()).hexdigest()
            absent = "f" * 64

            matches = scan_exact_sha_matches([root], {target, absent})
            report = build_scan_report(matches)

            self.assertEqual(matches[target], [str(wanted)])
            self.assertEqual(matches[absent], [])
            self.assertTrue(report["local_only"])
            self.assertTrue(report["exact_sha_only"])
            self.assertFalse(report["match_group_inference_allowed"])
            self.assertFalse(report["safe_to_auto_bind_match_group"])
            self.assertEqual(report["matched_target_count"], 1)
            self.assertEqual(report["unmatched_target_count"], 1)
            found = next(
                row for row in report["matches"]
                if row["source_sha256"] == target
            )
            self.assertEqual(
                found["status"],
                "EXACT_SHA_FOUND_NEEDS_MATCH_REVIEW",
            )


if __name__ == "__main__":
    unittest.main()
