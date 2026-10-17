import importlib.util
import unittest


@unittest.skipUnless(all(importlib.util.find_spec(n) for n in ("cv2", "numpy", "PIL")),
                     "optional vision dependencies")
class TopRowPeerProbeTests(unittest.TestCase):
    def scene(self, *, peers=2, animation=False, distant=False):
        from PIL import Image, ImageDraw
        image = Image.new("RGB", (500, 300), (0, 100, 110))
        draw = ImageDraw.Draw(image)
        draw.rectangle((225 if not distant else 100, 15,
                        264 if not distant else 139, 34), fill=(220, 220, 220))
        for left in [270, 315][:peers]:
            draw.rectangle((left, 15, left + 39, 34), fill=(220, 220, 220))
        if animation:
            draw.rectangle((235, 35, 255, 80), fill=(220, 220, 220))
        return image

    def recover(self, image):
        from workspace.vision.public_tile_detector import detect_public_tile_geometry
        from workspace.vision.public_meld_top_row_peer_probe import recover_top_row_peer_candidates
        detection = detect_public_tile_geometry(image)
        before = detection.to_dict()
        result = recover_top_row_peer_candidates(image, detection)
        self.assertEqual(before, detection.to_dict())
        return result

    def test_leftmost_group_and_touching_animation_are_recovered_without_manual_roi(self):
        for animation in [False, True]:
            with self.subTest(animation=animation):
                rows = self.recover(self.scene(animation=animation))
                self.assertEqual(len(rows), 1)
                self.assertLess(rows[0].normalized_bbox[0], 0.54)
                self.assertEqual(rows[0].to_dict()["tile_id"], "UNKNOWN")

    def test_zero_or_one_peer_abstains(self):
        for peers in [0, 1]:
            self.assertEqual(self.recover(self.scene(peers=peers)), ())

    def test_distant_bright_component_is_not_a_row_neighbor(self):
        self.assertEqual(self.recover(self.scene(distant=True)), ())

    def test_existing_peer_groups_are_not_duplicated(self):
        from PIL import ImageDraw
        image = self.scene()
        ImageDraw.Draw(image).rectangle((225, 15, 264, 34), fill=(0, 100, 110))
        self.assertEqual(self.recover(image), ())
