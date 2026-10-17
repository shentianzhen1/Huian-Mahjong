import copy
import json
from pathlib import Path
import unittest

from workspace.vision.issue69_kong_development_candidate import (
    build_hand1_candidate_from_repository,
    build_kong_development_candidate,
    candidate_to_ledger_event,
)

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class Issue69KongDevelopmentCandidateTests(unittest.TestCase):
    def setUp(self):
        self.hand = load(
            "references/vision/2026-10-01/"
            "issue69_hand1_p6_ming_gang_hand_count_v0_1.json"
        )
        self.structure = load(
            "references/vision/2026-10-01/"
            "issue69_hand1_p6_ming_gang_structure_v0_1.json"
        )
        self.identity = load(
            "references/vision/2026-10-01/"
            "issue69_hand1_p6_public_meld_sift_result_v0_1.json"
        )

    def test_real_hand1_evidence_forms_development_p6_ming_gang_candidate(self):
        out = build_hand1_candidate_from_repository(ROOT)
        self.assertEqual(out["status"], "DEVELOPMENT_MING_GANG_CANDIDATE")
        self.assertEqual(out["action_candidate"], "MING_GANG")
        self.assertEqual(out["tile_candidate"], "P6")
        self.assertEqual(out["structure_evidence"]["hand_before"], 16)
        self.assertEqual(out["structure_evidence"]["hand_after"], 13)
        self.assertEqual(out["structure_evidence"]["removed_count"], 3)
        self.assertEqual(out["structure_evidence"]["stacked_votes"], 5)
        self.assertEqual(out["identity_evidence"]["winner_other_match_groups"], 2)
        self.assertAlmostEqual(out["identity_evidence"]["margin"], 0.12319498)
        self.assertFalse(out["claimed_discard_directly_observed"])
        self.assertTrue(out["claimed_discard_identity_directly_observed"])
        self.assertTrue(out["claimed_discard_display_directly_observed"])
        self.assertFalse(out["river_growth_directly_observed"])
        self.assertEqual(
            out["claimed_discard_display_evidence"]["tile_candidate"],
            "P6",
        )
        self.assertEqual(
            out["claimed_discard_display_evidence"]["valid_frame_votes"],
            6,
        )
        self.assertFalse(out["machine_confirmed"])
        self.assertFalse(out["runtime_eligible"])
        self.assertFalse(out["safe_for_runtime"])
        self.assertFalse(out["safe_for_hint"])
        self.assertFalse(out["safe_for_executor"])

    def test_real_candidate_projects_to_non_runtime_ledger_event(self):
        candidate = build_hand1_candidate_from_repository(ROOT)
        event = candidate_to_ledger_event(
            candidate,
            clip_timestamp_seconds=11.9333333333,
            hand_number=1,
            total_hands=8,
        )
        self.assertEqual(event["hand_number"], 1)
        self.assertEqual(event["kind"], "MING_GANG")
        self.assertEqual(event["tile"], "P6")
        self.assertEqual(event["evidence_level"], "development_candidate")
        self.assertFalse(event["claimed_discard_directly_observed"])
        self.assertTrue(event["claimed_discard_identity_directly_observed"])
        self.assertTrue(event["claimed_discard_display_directly_observed"])
        self.assertFalse(event["river_growth_directly_observed"])
        self.assertEqual(
            event["evidence"]["claimed_discard_display"]["tile_candidate"],
            "P6",
        )
        self.assertFalse(event["machine_confirmed"])
        self.assertFalse(event["runtime_action"])
        self.assertFalse(event["safe_for_runtime"])
        self.assertFalse(event["safe_for_executor"])

    def test_versioned_hand1_ledger_matches_generated_candidate(self):
        candidate = build_hand1_candidate_from_repository(ROOT)
        generated = candidate_to_ledger_event(
            candidate,
            clip_timestamp_seconds=11.9333333333,
            hand_number=1,
            total_hands=8,
        )
        ledger = load(
            "references/vision/2026-10-01/"
            "issue69_hand1_development_action_ledger_v0_1.json"
        )
        event = ledger["events"][0]
        self.assertEqual(event["kind"], generated["kind"])
        self.assertEqual(event["tile"], generated["tile"])
        self.assertEqual(
            event["evidence_level"],
            generated["evidence_level"],
        )
        self.assertEqual(
            event["clip_timestamp_seconds"],
            generated["clip_timestamp_seconds"],
        )
        self.assertEqual(
            event["candidate_status"],
            generated["candidate_status"],
        )
        self.assertEqual(
            event["claimed_discard_directly_observed"],
            generated["claimed_discard_directly_observed"],
        )
        self.assertEqual(event["runtime_action"], generated["runtime_action"])
        self.assertEqual(
            event["claimed_discard_identity_directly_observed"],
            generated["claimed_discard_identity_directly_observed"],
        )
        self.assertEqual(
            event["claimed_discard_display_directly_observed"],
            generated["claimed_discard_display_directly_observed"],
        )
        self.assertEqual(
            event["river_growth_directly_observed"],
            generated["river_growth_directly_observed"],
        )
        self.assertEqual(
            event["evidence"]["claimed_discard_display"],
            generated["evidence"]["claimed_discard_display"],
        )
        self.assertFalse(ledger["formal_promotion_evidence"])
        self.assertFalse(ledger["safe_for_runtime"])
        self.assertFalse(ledger["safe_for_executor"])

    def test_cross_source_identity_fails_closed(self):
        identity = copy.deepcopy(self.identity)
        identity["source"]["sha256"] = "0" * 64
        out = build_kong_development_candidate(
            self.hand, self.structure, identity
        )
        self.assertEqual(out["status"], "UNKNOWN")
        self.assertEqual(out["reason"], "source_sha_mismatch")

    def test_wrong_hand_delta_fails_closed(self):
        hand = copy.deepcopy(self.hand)
        hand["claim_count_review"]["after_count"] = 14
        hand["claim_count_review"]["removed_count"] = 2
        out = build_kong_development_candidate(
            hand, self.structure, self.identity
        )
        self.assertEqual(out["status"], "UNKNOWN")
        self.assertEqual(out["reason"], "hand_count_gate_not_satisfied")

    def test_claimed_display_and_meld_identity_conflict_fails_closed(self):
        identity = copy.deepcopy(self.identity)
        identity["ranking"]["top1_tile"] = "S4"
        claimed = load(
            "references/vision/2026-10-02/"
            "issue69_hand1_claimed_discard_p6_display_v0_1.json"
        )
        out = build_kong_development_candidate(
            self.hand, self.structure, identity, claimed
        )
        self.assertEqual(out["status"], "UNKNOWN")
        self.assertEqual(out["reason"], "claimed_discard_identity_conflict")

    def test_insufficient_cross_match_identity_support_fails_closed(self):
        identity = copy.deepcopy(self.identity)
        identity["ranking"]["winner_other_match_groups"] = 1
        out = build_kong_development_candidate(
            self.hand, self.structure, identity
        )
        self.assertEqual(out["status"], "UNKNOWN")
        self.assertEqual(
            out["reason"],
            "public_meld_identity_not_source_disjoint",
        )


if __name__ == "__main__":
    unittest.main()
