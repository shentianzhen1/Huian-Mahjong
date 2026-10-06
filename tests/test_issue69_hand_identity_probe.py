import unittest
from pathlib import Path
from unittest.mock import patch

from workspace.vision.issue69_hand_identity_probe import run


class Issue69HandIdentityProbeTests(unittest.TestCase):
    @patch("workspace.vision.issue69_hand_identity_probe.sha256", return_value="a"*64)
    @patch("workspace.vision.issue69_hand_identity_probe._burst")
    def test_requires_both_bursts_fully_identity_qualified(self, burst, _digest):
        burst.side_effect=[
            {"frames":[1,2,3],"concealed_tile_count":16,"geometry_untrusted":False,
             "all_concealed_tile_ids_trusted":True,"tiles":["P6"]*16,
             "minimum_identity_confidence":.90,"identity_reasons":["accepted"]*16},
            {"frames":[4,5,6],"concealed_tile_count":13,"geometry_untrusted":False,
             "all_concealed_tile_ids_trusted":True,"tiles":["P6"]*13,
             "minimum_identity_confidence":.83,"identity_reasons":["accepted"]*13},
        ]
        out=run(Path("private.mp4"),expected_sha256="a"*64,before_start=1,after_start=4,
                dataset="d",session="s",frames=3,threshold=.82)
        self.assertTrue(out["identity_delta_gate_eligible"])
        self.assertFalse(out["safe_for_runtime"])
        self.assertFalse(out["safe_for_executor"])

    @patch("workspace.vision.issue69_hand_identity_probe.sha256", return_value="a"*64)
    @patch("workspace.vision.issue69_hand_identity_probe._burst")
    def test_one_unknown_burst_blocks_identity_delta(self, burst, _digest):
        base={"frames":[1,2,3],"concealed_tile_count":16,"geometry_untrusted":False,
              "all_concealed_tile_ids_trusted":True,"tiles":["P6"]*16,
              "minimum_identity_confidence":.90,"identity_reasons":["accepted"]*16}
        blocked={**base,"all_concealed_tile_ids_trusted":False,
                 "minimum_identity_confidence":.81}
        burst.side_effect=[base,blocked]
        out=run(Path("private.mp4"),expected_sha256="a"*64,before_start=1,after_start=4,
                dataset="d",session="s",frames=3,threshold=.82)
        self.assertFalse(out["identity_delta_gate_eligible"])

    @patch("workspace.vision.issue69_hand_identity_probe.sha256", return_value="b"*64)
    def test_wrong_source_sha_fails_before_decoding(self, _digest):
        with self.assertRaisesRegex(ValueError,"SHA256"):
            run(Path("private.mp4"),expected_sha256="a"*64,before_start=1,after_start=4,
                dataset="d",session="s")


if __name__=="__main__": unittest.main()
