from __future__ import annotations

import unittest

from workspace.vision.private_video_chunking import (
    PrivateVideoChunkPlan,
    build_ffmpeg_stream_copy_command,
    chunk_record,
    plan_private_video_chunks,
)


class PrivateVideoChunkingTests(unittest.TestCase):
    def test_217_second_source_becomes_five_45_second_windows(self):
        plans = plan_private_video_chunks(217.098)
        self.assertEqual(len(plans), 5)
        self.assertEqual(plans[0].start_seconds, 0.0)
        self.assertEqual(plans[0].end_seconds, 45.0)
        self.assertAlmostEqual(plans[-1].start_seconds, 180.0)
        self.assertAlmostEqual(plans[-1].end_seconds, 217.098)
        self.assertFalse(plans[0].to_dict()["independent_match_group"])
        self.assertFalse(plans[0].to_dict()["safe_for_executor"])

    def test_command_uses_stream_copy_and_keeps_lineage_caveat_external(self):
        plan = PrivateVideoChunkPlan(2, 45.0, 90.0, 45.0)
        command = build_ffmpeg_stream_copy_command(
            "source.mp4", "chunk_02.mp4", plan
        )
        self.assertIn("-c", command)
        self.assertIn("copy", command)
        self.assertIn("-ss", command)
        self.assertIn("-t", command)
        self.assertEqual(command[-1], "chunk_02.mp4")

    def test_record_never_upgrades_chunk_to_independent_evidence(self):
        record = chunk_record(
            source_name="recording.mp4",
            source_sha256="a" * 64,
            match_group="reviewed_match_a",
            plan=PrivateVideoChunkPlan(1, 0.0, 45.0, 45.0),
            output_name="chunk_01.mp4",
            output_sha256="b" * 64,
            output_size_bytes=90 * 1024 * 1024,
        )
        self.assertTrue(record["within_transport_size_gate"])
        self.assertTrue(record["same_original_source"])
        self.assertFalse(record["independent_match_group"])
        self.assertTrue(record["requires_frame_lineage_verification"])
        self.assertFalse(record["formal_promotion_evidence"])
        self.assertFalse(record["safe_for_hint"])
        self.assertFalse(record["safe_for_executor"])

    def test_oversize_chunk_is_explicitly_flagged(self):
        record = chunk_record(
            source_name="recording.mp4",
            source_sha256="a" * 64,
            match_group="reviewed_match_a",
            plan=PrivateVideoChunkPlan(1, 0.0, 45.0, 45.0),
            output_name="chunk_01.mp4",
            output_size_bytes=96 * 1024 * 1024,
        )
        self.assertFalse(record["within_transport_size_gate"])

    def test_invalid_numeric_inputs_fail_closed(self):
        for value in (0, -1, float("inf"), True, "45"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    plan_private_video_chunks(value)


if __name__ == "__main__":
    unittest.main()
