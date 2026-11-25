from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

from .evaluate_gold_identity import evaluate_gold_identity


def make_tile(path: Path, *, offset: int) -> None:
    image = Image.new("RGB", (60, 92), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((16 + offset, 22, 40 + offset, 70), fill="black")
    image.save(path)


class GoldIdentityEvaluationTests(unittest.TestCase):
    def test_holdout_and_gold_only_subset_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = []
            for session, offset in (("a", 0), ("b", 1), ("c", 2)):
                path = root / f"m6_{session}.png"
                make_tile(path, offset=offset)
                rows.append({
                    "image": path.name,
                    "bbox": [0, 0, 60, 92],
                    "tile_id": "M6",
                    "region": "hand_region",
                    "approved": True,
                    "status": "approved",
                    "source_session": f"session_{session}",
                    "source_id": f"src_{session}",
                    "source_frame": 0,
                    "slot": 0,
                    "sha256": session,
                    "gold_skin_only": session == "c",
                })
            (root / "labels.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )
            report = evaluate_gold_identity(root, confidence_threshold=0.0)
            self.assertEqual(report["distinct_source_groups"], 3)
            self.assertEqual(report["scorable_labels"], 3)
            self.assertEqual(report["gold_skin_only_subset"]["scorable_labels"], 1)
            self.assertEqual(report["template_scope"], "gold_identity")

    def test_tracked_real_gold_m6_clears_gate_without_false_accepts(self) -> None:
        root = Path(__file__).resolve().parents[3] / "dataset" / "tiles_runtime_v0_2"
        report = evaluate_gold_identity(root, confidence_threshold=0.82)
        gold_rows = [
            row for row in report["rows"]
            if row.get("gold_skin_only") and row["true_tile"] == "M6"
        ]
        self.assertEqual(len(gold_rows), 1)
        row = gold_rows[0]
        self.assertEqual(row["predicted_tile"], "M6")
        self.assertGreaterEqual(row["confidence"], 0.82)
        self.assertTrue(row["runtime_gate_accepted"])
        self.assertEqual(report["runtime_gate"]["accepted_accuracy"], 1.0)
        self.assertGreaterEqual(report["runtime_gate"]["accepted_labels"], 43)

    def test_single_session_true_class_is_unscorable_not_false_accuracy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = []
            for tile, session, offset in (
                ("M6", "a", 0),
                ("M6", "b", 1),
                ("M2", "c", 2),
            ):
                path = root / f"{tile}_{session}.png"
                make_tile(path, offset=offset)
                rows.append({
                    "image": path.name,
                    "bbox": [0, 0, 60, 92],
                    "tile_id": tile,
                    "region": "hand_region",
                    "approved": True,
                    "status": "approved",
                    "source_session": f"session_{session}",
                    "source_id": f"src_{session}",
                    "source_frame": 0,
                    "slot": 0,
                    "sha256": session,
                })
            (root / "labels.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )
            report = evaluate_gold_identity(root, confidence_threshold=0.82)
            self.assertEqual(report["scorable_labels"], 2)
            self.assertEqual(report["unscorable_labels"], 1)
            self.assertEqual(report["unscorable"][0]["tile_id"], "M2")


if __name__ == "__main__":
    unittest.main()
