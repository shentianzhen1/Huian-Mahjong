from __future__ import annotations

import unittest
from unittest.mock import patch

from PIL import Image

from .runtime_reader import _gold_identity_observations


class _GoldComponent:
    region_candidate = "gold"
    gold_skin = True
    pixel_bbox = (0, 0, 10, 10)


class _Geometry:
    def __init__(self, frame: int, *, trusted: bool = True) -> None:
        self.frame = frame
        self.geometry_untrusted = not trusted
        self.components = [_GoldComponent()]


class RuntimeGoldMultiframeReaderTests(unittest.TestCase):
    def test_each_burst_frame_is_classified_independently(self) -> None:
        images = [
            Image.new("RGB", (16, 16), (10, 0, 0)),
            Image.new("RGB", (16, 16), (20, 0, 0)),
            Image.new("RGB", (16, 16), (30, 0, 0)),
        ]
        geometries = [_Geometry(100), _Geometry(101), _Geometry(102)]
        identities = {10: "M5", 20: "P5", 30: "M5"}

        def classify(component, image, **_kwargs):
            tile_id = identities[image.getpixel((0, 0))[0]]
            return {
                "candidate_tile_id": tile_id,
                "tile_id": tile_id,
                "tile_confidence": 0.95,
                "identity_reason": "accepted",
            }

        with patch(
            "workspace.vision.tiles_runtime_v0_2.runtime_reader._classify_runtime_component",
            side_effect=classify,
        ) as classify_mock:
            observations = _gold_identity_observations(
                images,
                geometries,
                classifier=object(),
                covered_by_region={},
                cross_session={},
                confidence_threshold=0.82,
                gold_skin_covered=set(),
            )

        self.assertEqual(classify_mock.call_count, 3)
        self.assertEqual(
            [(item["frame"], item["tile_id"]) for item in observations],
            [(100, "M5"), (101, "P5"), (102, "M5")],
        )

    def test_untrusted_frame_stays_unknown_without_reusing_neighbor_identity(self) -> None:
        images = [Image.new("RGB", (16, 16), "white") for _ in range(3)]
        geometries = [_Geometry(200), _Geometry(201, trusted=False), _Geometry(202)]

        with patch(
            "workspace.vision.tiles_runtime_v0_2.runtime_reader._classify_runtime_component",
            return_value={
                "candidate_tile_id": "M5",
                "tile_id": "M5",
                "tile_confidence": 0.95,
                "identity_reason": "accepted",
            },
        ) as classify_mock:
            observations = _gold_identity_observations(
                images,
                geometries,
                classifier=object(),
                covered_by_region={},
                cross_session={},
                confidence_threshold=0.82,
                gold_skin_covered=set(),
            )

        self.assertEqual(classify_mock.call_count, 2)
        self.assertEqual(observations[1]["frame"], 201)
        self.assertEqual(observations[1]["tile_id"], "UNKNOWN")
        self.assertEqual(observations[1]["identity_reason"], "frame_geometry_untrusted")


if __name__ == "__main__":
    unittest.main()
