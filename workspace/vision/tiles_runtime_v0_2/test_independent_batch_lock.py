from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from workspace.vision.tiles_runtime_v0_2.independent_batch_lock import (
    build_lock,
)


def source_hash(index: int) -> str:
    return f"{index:064x}"


class IndependentBatchLockTests(unittest.TestCase):
    def fresh_sources(self, count=8):
        return {
            source_hash(index): Path(f"/private/local/video_{index}.mp4")
            for index in range(1, count + 1)
        }

    def test_locks_eight_fresh_sources_without_paths_or_model_truth(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "incoming"
            dataset = Path(temp) / "dataset"
            output = Path(temp) / "locked"

            with (
                patch(
                    "workspace.vision.tiles_runtime_v0_2.independent_batch_lock.locate_sources",
                    return_value=self.fresh_sources(),
                ),
                patch(
                    "workspace.vision.tiles_runtime_v0_2.independent_batch_lock._known_source_tokens",
                    return_value=set(),
                ),
                patch(
                    "workspace.vision.tiles_runtime_v0_2.independent_batch_lock._video_metadata",
                    return_value=(1108, 690, 1000),
                ),
            ):
                lock = build_lock(root, dataset, output)

            self.assertEqual(lock["selected_session_count"], 8)
            self.assertEqual(lock["selected_frame_count"], 24)
            self.assertTrue(lock["independent_batch"])
            self.assertTrue(lock["holdout_locked_before_evaluation"])
            self.assertFalse(lock["tuning_after_lock"])
            self.assertFalse(lock["safe_for_executor"])

            batch_dir = output / lock["batch_id"]
            lock_text = (batch_dir / "batch_lock.json").read_text(encoding="utf-8")
            self.assertNotIn("/private/local", lock_text)
            self.assertNotIn("video_", lock_text)

            truth_rows = [
                json.loads(line)
                for line in (
                    batch_dir / "geometry_truth.blank.jsonl"
                ).read_text(encoding="utf-8").splitlines()
                if line
            ]
            self.assertEqual(len(truth_rows), 24)
            self.assertTrue(all(row["manual_truth_required"] for row in truth_rows))
            self.assertTrue(all(row["components"] is None for row in truth_rows))
            self.assertTrue(all(row["frame_state"] is None for row in truth_rows))
            self.assertTrue(all(not row["approved"] for row in truth_rows))

            bundle = json.loads(
                (batch_dir / "promotion_bundle.blank.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(bundle["provenance"]["source_sessions"], 8)
            self.assertIsNone(bundle["geometry"]["component_precision"])
            self.assertIsNone(bundle["tile_identity"]["accepted_accuracy"])
            self.assertFalse(bundle["policy"]["safe_for_executor"])

    def test_known_sources_are_excluded_before_lock(self):
        sources = self.fresh_sources()
        known = {source_hash(1)}
        with TemporaryDirectory() as temp, (
            patch(
                "workspace.vision.tiles_runtime_v0_2.independent_batch_lock.locate_sources",
                return_value=sources,
            ),
            patch(
                "workspace.vision.tiles_runtime_v0_2.independent_batch_lock._known_source_tokens",
                return_value=known,
            ),
            patch(
                "workspace.vision.tiles_runtime_v0_2.independent_batch_lock._video_metadata",
                return_value=(1108, 690, 1000),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "found 7"):
                build_lock(
                    Path(temp) / "incoming",
                    Path(temp) / "dataset",
                    Path(temp) / "locked",
                )

    def test_short_recordings_do_not_count_toward_promotion_batch(self):
        sources = self.fresh_sources()
        calls = {"n": 0}

        def metadata(_path):
            calls["n"] += 1
            if calls["n"] == 1:
                return 1108, 690, 119
            return 1108, 690, 1000

        with TemporaryDirectory() as temp, (
            patch(
                "workspace.vision.tiles_runtime_v0_2.independent_batch_lock.locate_sources",
                return_value=sources,
            ),
            patch(
                "workspace.vision.tiles_runtime_v0_2.independent_batch_lock._known_source_tokens",
                return_value=set(),
            ),
            patch(
                "workspace.vision.tiles_runtime_v0_2.independent_batch_lock._video_metadata",
                side_effect=metadata,
            ),
        ):
            with self.assertRaisesRegex(ValueError, "found 7"):
                build_lock(
                    Path(temp) / "incoming",
                    Path(temp) / "dataset",
                    Path(temp) / "locked",
                )

    def test_existing_batch_artifacts_are_never_overwritten(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "incoming"
            dataset = Path(temp) / "dataset"
            output = Path(temp) / "locked"
            patches = (
                patch(
                    "workspace.vision.tiles_runtime_v0_2.independent_batch_lock.locate_sources",
                    return_value=self.fresh_sources(),
                ),
                patch(
                    "workspace.vision.tiles_runtime_v0_2.independent_batch_lock._known_source_tokens",
                    return_value=set(),
                ),
                patch(
                    "workspace.vision.tiles_runtime_v0_2.independent_batch_lock._video_metadata",
                    return_value=(1108, 690, 1000),
                ),
            )
            with patches[0], patches[1], patches[2]:
                first = build_lock(root, dataset, output)

            with (
                patch(
                    "workspace.vision.tiles_runtime_v0_2.independent_batch_lock.locate_sources",
                    return_value=self.fresh_sources(),
                ),
                patch(
                    "workspace.vision.tiles_runtime_v0_2.independent_batch_lock._known_source_tokens",
                    return_value=set(),
                ),
                patch(
                    "workspace.vision.tiles_runtime_v0_2.independent_batch_lock._video_metadata",
                    return_value=(1108, 690, 1000),
                ),
            ):
                with self.assertRaises((FileExistsError, FileExistsError)):
                    build_lock(root, dataset, output)

            self.assertTrue((output / first["batch_id"] / "batch_lock.json").is_file())

    def test_cannot_reduce_source_count_below_frozen_promotion_minimum(self):
        with TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "at least 8"):
                build_lock(
                    Path(temp) / "incoming",
                    Path(temp) / "dataset",
                    Path(temp) / "locked",
                    source_count=7,
                )


if __name__ == "__main__":
    unittest.main()
