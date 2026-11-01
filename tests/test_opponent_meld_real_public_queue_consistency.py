import json
from pathlib import Path
import unittest

from workspace.vision.opponent_meld_real_public_eligibility import run

ROOT = Path(__file__).resolve().parents[1]
QUEUE = (
    ROOT / "references/vision/2026-10-01/"
    "opponent_public_meld_review_queue_v0_1.json"
)


class OpponentMeldRealPublicQueueConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.eligibility = run(ROOT)["queries"]
        cls.queue = json.loads(QUEUE.read_text(encoding="utf-8"))["items"]

    def _item(self, review_id):
        return next(row for row in self.queue if row["review_id"] == review_id)

    def test_s456_queue_matches_eligibility_gate(self):
        item = self._item("opp_meld_0926_hand1_s456")
        gate = self.eligibility["s456"]
        self.assertEqual(
            item["real_public_probe"]["eligible"],
            gate["real_public_probe_eligible"],
        )
        self.assertEqual(item["real_public_probe"]["status"], gate["status"])
        self.assertEqual(
            item["real_public_probe"]["identity_runtime_status"],
            "UNKNOWN",
        )

    def test_m123_queue_matches_eligibility_gate(self):
        item = self._item("opp_meld_14_m123")
        gate = self.eligibility["m123"]
        self.assertEqual(
            item["real_public_probe"]["eligible"],
            gate["real_public_probe_eligible"],
        )
        self.assertEqual(item["real_public_probe"]["status"], gate["status"])

    def test_s123_queue_matches_cross_match_reference_gate(self):
        item = self._item("opp_meld_0926_hand1_s123")
        self.assertFalse(item["real_public_probe"]["eligible"])
        gate = self.eligibility["s123"]
        self.assertEqual(
            item["real_public_probe"]["eligible"],
            gate["real_public_probe_eligible"],
        )
        self.assertEqual(item["real_public_probe"]["status"], gate["status"])
        self.assertEqual(item["crop_status"], "CLASSIFIER_READY")
        self.assertEqual(
            item["real_public_probe"]["missing_tiles"],
            ["S1"],
        )


if __name__ == "__main__":
    unittest.main()
