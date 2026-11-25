import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from workspace.vision.concealed_template_local_sha_scan import (
    DEFAULT_QUEUE,
    build_scan_report,
    load_target_shas,
    resolve_scan_roots,
    scan_exact_sha_matches,
)


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_QUEUE = (
    ROOT
    / "references/vision/2026-10-01/"
    "concealed_template_lineage_recovery_queue_v0_1.json"
)
CURRENT_QUEUE = ROOT / DEFAULT_QUEUE


class ConcealedTemplateLocalShaScanTests(unittest.TestCase):
    def test_default_queue_targets_current_full_concealed_domain(self):
        self.assertEqual(
            DEFAULT_QUEUE.as_posix(),
            "references/vision/2026-10-07/"
            "concealed_full_domain_lineage_recovery_queue_v0_1.json",
        )
        targets = load_target_shas(CURRENT_QUEUE)
        self.assertEqual(len(targets), 6)
        self.assertIn(
            "5e02f7d0458be0a923231d87921b5506ce4e15d1412bb560d59b5e61f7eb2c39",
            targets,
        )

    def test_resolved_historical_queue_has_no_scan_targets(self):
        frozen = json.loads(HISTORICAL_QUEUE.read_text(encoding="utf-8"))
        self.assertEqual(frozen["unresolved_source_count"], 0)
        self.assertEqual(frozen["items"], [])
        with self.assertRaisesRegex(ValueError, "no unresolved SHA256 targets"):
            load_target_shas(HISTORICAL_QUEUE)

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
            self.assertTrue(report["match_group_review_required"])
            found = next(
                row for row in report["matches"]
                if row["source_sha256"] == target
            )
            self.assertEqual(
                found["status"],
                "EXACT_SHA_FOUND_NEEDS_MATCH_REVIEW",
            )

    def test_defaults_use_historical_roots_in_priority_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            capture = project / "data" / "capture_validation"
            private = project / "data" / "issue69_private"
            references = project / "references"
            capture.mkdir(parents=True)
            references.mkdir(parents=True)

            roots, missing, used_defaults = resolve_scan_roots(
                [], project_root=project
            )

            self.assertTrue(used_defaults)
            self.assertEqual(roots, [capture, references])
            self.assertEqual(missing, [private])

    def test_default_mode_refuses_to_broaden_when_history_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(
                FileNotFoundError, "historical default scan roots"
            ):
                resolve_scan_roots([], project_root=tmp)

    def test_exact_scan_accepts_arbitrary_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "old-static-source.weird"
            payload = b"anonymous historical concealed source"
            source.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()

            matches = scan_exact_sha_matches([root], {digest})

            self.assertEqual(matches[digest], [str(source)])

    def test_explicit_roots_never_fall_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            explicit = Path(tmp) / "custom"
            roots, missing, used_defaults = resolve_scan_roots([explicit])
            self.assertEqual(roots, [explicit])
            self.assertEqual(missing, [])
            self.assertFalse(used_defaults)


if __name__ == "__main__":
    unittest.main()
