import json
from pathlib import Path
import unittest

from workspace.vision.concealed_template_lineage_recovery import (
    build_lineage_recovery_queue,
)
from workspace.vision.concealed_template_match_lineage import (
    load_concealed_template_lineage,
    qualify_concealed_template_labels,
    verify_lineage_evidence_paths,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = (
    ROOT
    / "references/vision/2026-10-01/"
    "concealed_template_match_lineage.development.json"
)
AUDIT = (
    ROOT
    / "references/vision/2026-10-01/"
    "concealed_template_lineage_audit_v0_1.json"
)
LABELS = ROOT / "dataset/tiles_runtime_v0_2/labels.jsonl"
RECOVERY_QUEUE = (
    ROOT
    / "references/vision/2026-10-01/"
    "concealed_template_lineage_recovery_queue_v0_1.json"
)
RECOVERY_AUDIT = (
    ROOT
    / "references/vision/2026-10-01/"
    "concealed_template_lineage_recovery_audit_v0_1.json"
)


def _approved_non_gold_hand_labels():
    rows = [
        json.loads(line)
        for line in LABELS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [
        row
        for row in rows
        if row.get("region") == "hand_region"
        and not row.get("gold_skin_only")
        and (
            row.get("status") == "approved"
            or row.get("approved") is True
        )
    ]


class ConcealedTemplateMatchLineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_concealed_template_lineage(REGISTRY)
        cls.audit = json.loads(AUDIT.read_text(encoding="utf-8"))

    def test_registry_is_exact_sha_and_evidence_paths_exist(self):
        self.assertEqual(len(self.registry), 12)
        self.assertEqual(verify_lineage_evidence_paths(self.registry, ROOT), [])

        old_match_shas = {
            "1560c1e04a632f07dc5f53947ba3080ed93ff927a7bd028a457f3415b0bc69a3",
            "1597ef429288ad50ce26340fcda580c17c735cf3875845c4c309db5652853b22",
            "cf1451e8cc18561d8c3d0250826f79eebcf71904aaf337c74edc41ba46c0f636",
            "5e6c590f060c085adaed07f01da9dfe2e83f37d99e3817e5ac4f1a8d1118086e",
            "02f7874493d224b290d7957c62b552e877ec7dacd3a712ee9fbdc3c81225e245",
            "d50f6722982adb0fdfe3ad8e0b9d1f4155defcfbefebd77e8f10cbc4d3b19a78",
            "4043cc011c1b12d1ade88afd98c30e77dca8b364b7d0b8c595b3ca16bcdb7757",
            "4333a11966bd364f3388b2bf3677900eed50faf6b0d6739cf9399e901de196fc",
        }
        self.assertEqual(
            {
                self.registry[sha].match_group
                for sha in old_match_shas
            },
            {"reviewed_match_2026_09_19_eight_hand"},
        )

    def test_source_session_name_never_substitutes_for_missing_sha_lineage(self):
        known_sha = (
            "1560c1e04a632f07dc5f53947ba3080ed93ff927a7bd028a457f3415b0bc69a3"
        )
        fake_sha = "a" * 64
        labels = [
            {
                "tile_id": "M2",
                "source_session": "same_session_name",
                "sha256": known_sha,
            },
            {
                "tile_id": "M1",
                "source_session": "same_session_name",
                "sha256": fake_sha,
            },
        ]
        accepted, report = qualify_concealed_template_labels(
            labels,
            self.registry,
            query_match_group="some_other_match",
        )
        self.assertEqual([row["tile_id"] for row in accepted], ["M2"])
        self.assertEqual(
            report["excluded_missing_original_match_lineage_count"],
            1,
        )
        self.assertFalse(
            report["source_session_used_as_independence_signal"]
        )

    def test_same_original_match_is_excluded_even_with_different_session_name(self):
        sha = "f24898ecee56803c09bead267150a590143c043941d3287f436ed6e89930f51d"
        accepted, report = qualify_concealed_template_labels(
            [
                {
                    "tile_id": "M1",
                    "source_session": "invented_different_session",
                    "sha256": sha,
                }
            ],
            self.registry,
            query_match_group="reviewed_recording_14",
        )
        self.assertEqual(accepted, [])
        self.assertEqual(report["excluded_same_original_match_count"], 1)

    def test_m1_m3_recovery_queue_is_reproducible_and_fail_closed(self):
        labels = [
            json.loads(line)
            for line in LABELS.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        generated = build_lineage_recovery_queue(
            labels,
            self.registry,
            target_classes={"M1", "M3"},
        )
        frozen = json.loads(
            RECOVERY_QUEUE.read_text(encoding="utf-8")
        )
        self.assertEqual(generated, frozen)
        self.assertEqual(generated["unresolved_source_count"], 4)
        self.assertEqual(generated["unresolved_label_count"], 8)
        self.assertFalse(generated["match_group_inference_allowed"])
        self.assertTrue(
            all(
                item["status"] == "UNKNOWN_ORIGINAL_MATCH"
                and item["session_name_is_not_evidence"]
                for item in generated["items"]
            )
        )

    def test_recovery_audit_preserves_all_unresolved_sources(self):
        recovery = json.loads(RECOVERY_QUEUE.read_text(encoding="utf-8"))
        audit = json.loads(RECOVERY_AUDIT.read_text(encoding="utf-8"))

        queued = {item["source_sha256"] for item in recovery["items"]}
        audited = {item["source_sha256"] for item in audit["items"]}
        self.assertEqual(audited, queued)
        self.assertEqual(audit["result"]["recovered_source_count"], 0)
        self.assertEqual(audit["result"]["unresolved_source_count"], 4)
        self.assertFalse(audit["result"]["m1_lineage_ready"])
        self.assertFalse(audit["result"]["m3_lineage_ready"])
        self.assertEqual(
            audit["result"]["mobilenet_m123_rerun_status"],
            "BLOCKED_BEFORE_MODEL_LOAD",
        )
        self.assertTrue(
            all(
                item["status"] == "UNKNOWN_ORIGINAL_MATCH"
                and item["recovered_match_group"] is None
                and item["exact_sha_match_in_reviewed_source_records"] is False
                for item in audit["items"]
            )
        )
        self.assertTrue(audit["policy"]["source_session_is_not_match_evidence"])
        self.assertFalse(audit["safe_for_runtime"])
        self.assertFalse(audit["safe_for_hint"])
        self.assertFalse(audit["safe_for_executor"])

    def test_frozen_audit_matches_current_runtime_labels(self):
        labels = _approved_non_gold_hand_labels()
        accepted, report = qualify_concealed_template_labels(
            labels,
            self.registry,
            query_match_group=self.audit["query_match_group"],
        )
        runtime = self.audit["runtime_dataset"]

        self.assertEqual(
            len(labels),
            runtime["approved_non_gold_hand_label_count"],
        )
        self.assertEqual(
            len(accepted),
            runtime["exact_sha_lineage_qualified_label_count"],
        )
        self.assertEqual(
            report["excluded_missing_original_match_lineage_count"],
            runtime["excluded_missing_original_match_lineage_count"],
        )
        self.assertEqual(
            report["excluded_same_original_match_count"],
            runtime["excluded_same_original_match_count"],
        )
        self.assertEqual(
            sorted({row["tile_id"] for row in accepted}),
            runtime["qualified_classes"],
        )
        self.assertEqual(
            sorted(
                {
                    row["_original_match_group"]
                    for row in accepted
                }
            ),
            runtime["qualified_original_match_groups"],
        )

        expected = set(
            self.audit["current_opponent_query"]["expected_tiles"]
        )
        qualified_classes = {row["tile_id"] for row in accepted}
        self.assertEqual(
            sorted(expected - qualified_classes),
            self.audit["current_opponent_query"][
                "missing_lineage_qualified_expected_classes"
            ],
        )
        self.assertFalse(self.audit["safe_for_runtime"])
        self.assertFalse(self.audit["safe_for_hint"])
        self.assertFalse(self.audit["safe_for_executor"])


if __name__ == "__main__":
    unittest.main()
