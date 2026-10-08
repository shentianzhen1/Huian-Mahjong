import unittest
from workspace.vision.issue69_text_timeline import render_reconstructed_timeline


class Issue69TextTimelineTests(unittest.TestCase):
    def test_renders_confirmed_and_unknown_without_guessing(self):
        report = {
            "schema_version": "issue69_temporal_reconstruction_v0_1",
            "actions": [
                {"timestamp_seconds":47.0,"actor":"opponent","kind":"DISCARD",
                 "tile":"P6","meld":[],"unknown_reasons":[]},
                {"timestamp_seconds":47.5,"actor":"player","kind":"MING_GANG",
                 "tile":None,"meld":["P6","P6","P6","P6"],"unknown_reasons":[]},
                {"timestamp_seconds":59.0,"actor":"player","kind":"UNKNOWN_ACTION",
                 "tile":None,"meld":[],"unknown_reasons":["missing_hand_delta"]},
            ],
        }
        rows = render_reconstructed_timeline(report, hand_number=1)
        self.assertEqual(rows[0], "第1/8局 47.00s 对手打出六筒")
        self.assertEqual(rows[1], "47.50s 我方明杠（六筒 六筒 六筒 六筒）")
        self.assertIn("未确认动作", rows[2])
        self.assertIn("missing_hand_delta", rows[2])


if __name__ == "__main__":
    unittest.main()
