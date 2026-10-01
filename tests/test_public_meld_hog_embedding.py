import importlib.util
import unittest


VISION = all(
    importlib.util.find_spec(name) is not None
    for name in ("PIL", "cv2", "numpy")
)


@unittest.skipUnless(VISION, "Pillow/OpenCV/numpy are optional in core-only installs")
class PublicMeldHogEmbeddingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        from PIL import Image, ImageDraw
        from workspace.vision.public_meld_hog_embedding import (
            HOG_WIN_SIZE,
            _hog_embedding,
            _prototype_scores,
        )

        cls.np = np
        cls.Image = Image
        cls.ImageDraw = ImageDraw
        cls.hog_size = HOG_WIN_SIZE
        cls.embed = staticmethod(_hog_embedding)
        cls.score = staticmethod(_prototype_scores)

    def _tile(self, shift=0):
        image = self.Image.new("RGB", (44, 73), "white")
        draw = self.ImageDraw.Draw(image)
        draw.rectangle((2, 2, 41, 70), outline="gray", width=1)
        draw.ellipse((12 + shift, 18, 28 + shift, 34), fill="red")
        draw.ellipse((12, 42, 28, 58), fill="blue")
        return image

    def test_hog_embedding_is_normalized_and_deterministic(self):
        first = self.embed(self._tile())
        second = self.embed(self._tile())
        self.assertIsNotNone(first)
        self.assertEqual(first.shape, second.shape)
        self.assertGreater(first.size, 100)
        self.assertAlmostEqual(float(self.np.linalg.norm(first)), 1.0, places=5)
        self.assertTrue(self.np.allclose(first, second))

    def test_cosine_prototype_prefers_identical_embedding(self):
        query = self.embed(self._tile())
        nearby = self.embed(self._tile(3))
        prototypes = {
            "P1": query,
            "P2": nearby,
        }
        scores = self.score(query, prototypes)
        self.assertGreater(scores["P1"], scores["P2"])

    def test_hog_window_matches_synthetic_canonical_face(self):
        from workspace.vision.public_meld_synthetic_transfer import (
            SYNTHETIC_CANONICAL_SIZE,
        )

        self.assertEqual(tuple(self.hog_size), tuple(SYNTHETIC_CANONICAL_SIZE))


if __name__ == "__main__":
    unittest.main()
