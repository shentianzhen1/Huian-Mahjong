import unittest
from workspace.vision.evaluate_new_match_family_route_probe import (
    lower_family_consensus, wan_other_original_support,
)
from workspace.vision.public_identity_shadow_v0_2 import SourceGroup
from workspace.vision.public_meld_identity_sift import PublicMeldSiftBank, PublicMeldSiftTemplate


class OfflineFamilyConsensusTests(unittest.TestCase):
    def rank(self, tile, scores=None, margin=0.1):
        return dict(top1_tile=tile, margin=margin,
                    class_scores=scores if scores is not None else {"WAN": 0.2, "NON_WAN": 0.1})

    def test_whole_face_misroute_is_abstained_when_lower_feature_disagrees(self):
        self.assertEqual(lower_family_consensus(self.rank("M3"), self.rank("NON_WAN")), "UNKNOWN")
        self.assertEqual(lower_family_consensus(self.rank("N"), self.rank("WAN")), "UNKNOWN")

    def test_single_supported_binary_family_cannot_force_a_winner(self):
        self.assertEqual(lower_family_consensus(self.rank("M9"), self.rank("WAN", {"WAN": 0.2})), "UNKNOWN")

    def test_absent_or_tied_rank_abstains(self):
        for whole, lower in [(self.rank(None), self.rank("WAN")),
                             (self.rank("M9", margin=0), self.rank("WAN")),
                             (self.rank("M9"), self.rank("WAN", margin=0))]:
            self.assertEqual(lower_family_consensus(whole, lower), "UNKNOWN")

    def test_agreement_reports_only_family_not_identity(self):
        self.assertEqual(lower_family_consensus(self.rank("M4"), self.rank("WAN")), "WAN")
        self.assertEqual(lower_family_consensus(self.rank("S1"), self.rank("NON_WAN")), "NON_WAN")

    def test_support_excludes_query_match_exact_sha_and_duplicate_originals(self):
        def template(tile, group, sha):
            return PublicMeldSiftTemplate(tile, "template", sha, group, None)
        bank = PublicMeldSiftBank({"query": SourceGroup("query", "query_sha", "query_match")}, (
            template("M9", "query_match", "different_segment_sha"),
            template("M9", "other_alias", "query_sha"),
            template("M9", "other_match", "sha1"),
            template("M9", "other_match", "sha2"),
            template("M9", "third_match", "sha3"),
            template("P8", "third_match", "sha3"),
        ))
        support = wan_other_original_support(bank, "query", "query_sha")
        self.assertEqual(support["M9"], 2)
        self.assertEqual(support["M8"], 0)
        self.assertEqual(set(support), {f"M{i}" for i in range(1, 10)})
        with self.assertRaises(ValueError):
            wan_other_original_support(bank, "query", "wrong_sha")


if __name__ == "__main__":
    unittest.main()
