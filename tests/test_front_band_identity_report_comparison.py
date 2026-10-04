import unittest
from copy import deepcopy
from workspace.vision.compare_front_band_identity_reports import compare


def packet():
    mode = dict(family_ranking={"top1_tile": "M9"}, lower_binary_ranking={"top1_tile": "WAN"},
        family_consensus="WAN", consensus_correct=True, expected_identity_scorable=True,
        false_wan_route=False, digit_ranking={"top1_tile": "M9"},
        routed_expected_identity_scorable=True, routed_identity_correct=True, qualified_identity=None)
    return dict(rows=[dict(query_id="q", set="controls", expected="M9", sha256="source", crop_sha256="crop",
                           modes={"1": deepcopy(mode), "2": deepcopy(mode)})])


class PairedReportComparisonTests(unittest.TestCase):
    def test_abstention_and_support_loss_remain_in_denominator(self):
        before = packet(); after = deepcopy(before)
        for mode in after["rows"][0]["modes"].values():
            mode.update(family_consensus="UNKNOWN", consensus_correct=None,
                        expected_identity_scorable=False, digit_ranking=None,
                        routed_expected_identity_scorable=None, routed_identity_correct=None)
        summary = compare(before, after)["summary"]["1"]["controls"]
        self.assertEqual(summary["query_faces"], 1)
        self.assertEqual(summary["family_regressions"], ["q"])
        self.assertEqual(summary["true_identity_support_losses"], ["q"])
        self.assertEqual(summary["digit_regressions"], ["q"])

    def test_changed_crop_or_source_cannot_be_paired(self):
        for field in ("sha256", "crop_sha256", "expected"):
            before = packet(); after = deepcopy(before)
            after["rows"][0][field] = "changed"
            with self.assertRaises(ValueError):
                compare(before, after)

    def test_dropped_query_is_not_silently_excluded(self):
        with self.assertRaises(ValueError):
            compare(packet(), {"rows": []})


if __name__ == "__main__":
    unittest.main()
