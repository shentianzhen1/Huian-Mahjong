from pathlib import Path
import tempfile
import unittest

from workspace.vision.concealed_template_lineage_review import (
    validate_reviewed_bindings,
)


class ConcealedTemplateLineageReviewTests(unittest.TestCase):
    def test_requires_explicit_review_and_existing_text_evidence(self):
        sha = "a" * 64
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "review.json"
            evidence.write_text('{"reviewed": true}\n', encoding="utf-8")
            accepted, issues = validate_reviewed_bindings(
                [{
                    "source_sha256": sha,
                    "match_group": "reviewed_match_x",
                    "evidence_path": "review.json",
                    "reviewed": True,
                }],
                unresolved_shas={sha},
                repository_root=root,
            )
            self.assertEqual(issues, [])
            self.assertEqual(
                accepted,
                [{
                    "source_sha256": sha,
                    "match_group": "reviewed_match_x",
                    "evidence_path": "review.json",
                }],
            )

    def test_local_sha_hit_alone_cannot_bind_match_group(self):
        sha = "b" * 64
        with tempfile.TemporaryDirectory() as tmp:
            accepted, issues = validate_reviewed_bindings(
                [{
                    "source_sha256": sha,
                    "match_group": "guessed_from_filename",
                    "evidence_path": "missing.json",
                    "reviewed": False,
                }],
                unresolved_shas={sha},
                repository_root=tmp,
            )
            self.assertEqual(accepted, [])
            self.assertIn(f"{sha}:not_human_reviewed", issues)

    def test_rejects_sha_outside_frozen_queue(self):
        sha = "c" * 64
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "review.md").write_text("review", encoding="utf-8")
            accepted, issues = validate_reviewed_bindings(
                [{
                    "source_sha256": sha,
                    "match_group": "reviewed_match_x",
                    "evidence_path": "review.md",
                    "reviewed": True,
                }],
                unresolved_shas={"d" * 64},
                repository_root=root,
            )
            self.assertEqual(accepted, [])
            self.assertIn(f"{sha}:not_in_unresolved_queue", issues)

    def test_conflicting_binding_fails_closed(self):
        sha = "e" * 64
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "review.txt").write_text("review", encoding="utf-8")
            rows = [
                {
                    "source_sha256": sha,
                    "match_group": group,
                    "evidence_path": "review.txt",
                    "reviewed": True,
                }
                for group in ("match_a", "match_b")
            ]
            accepted, issues = validate_reviewed_bindings(
                rows,
                unresolved_shas={sha},
                repository_root=root,
            )
            self.assertEqual(accepted, [])
            self.assertIn(f"{sha}:conflicting_match_group", issues)


if __name__ == "__main__":
    unittest.main()
