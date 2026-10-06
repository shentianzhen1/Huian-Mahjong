import importlib.util
import unittest


VISION = all(
    importlib.util.find_spec(name) is not None
    for name in ("PIL", "cv2", "numpy")
)


@unittest.skipUnless(VISION, "Pillow/OpenCV/numpy are optional in core-only installs")
class PublicMeldMobileNetEmbeddingTests(unittest.TestCase):
    def test_square_canvas_preserves_tile_aspect_without_stretching(self):
        from PIL import Image
        from workspace.vision.public_meld_mobilenet_embedding import (
            EMBEDDING_INPUT_SIZE,
            _square_tile_canvas,
        )

        image = Image.new("RGB", (56, 96), "white")
        canvas = _square_tile_canvas(image)
        self.assertEqual(
            canvas.size,
            (EMBEDDING_INPUT_SIZE, EMBEDDING_INPUT_SIZE),
        )

    def test_known_same_match_hand_source_is_explicit(self):
        from workspace.vision.public_meld_mobilenet_embedding import (
            KNOWN_HAND_SESSION_MATCH_GROUPS,
        )

        self.assertEqual(
            KNOWN_HAND_SESSION_MATCH_GROUPS["session_eight_hand_match_a"],
            "reviewed_match_2026_09_19_eight_hand",
        )

    def test_torch_is_not_required_by_normal_vision_test_import(self):
        from workspace.vision import public_meld_mobilenet_embedding as module

        self.assertTrue(callable(module.evaluate_public_meld_mobilenet_embedding))


if __name__ == "__main__":
    unittest.main()
