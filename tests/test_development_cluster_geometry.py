import unittest

try:
    from workspace.vision.tiles_runtime_v0_2.development_cluster_geometry import _development_select_hand_cluster
except ImportError:
    _development_select_hand_cluster = None


@unittest.skipIf(_development_select_hand_cluster is None, "Vision dependencies required")
class DevelopmentClusterSelectionTests(unittest.TestCase):
    def group(self, count, height, y=100, width=100, start=0):
        return [(start + i * (width + 2), y, width, height) for i in range(count)]

    def test_shorter_count_taller_lower_upright_group_is_selected(self):
        meld = self.group(9, 135, width=115)
        hand = self.group(7, 170, y=94, width=124, start=1500)
        self.assertEqual(_development_select_hand_cluster([meld, hand]), hand)

    def test_isolated_tall_draw_does_not_replace_hand(self):
        hand = self.group(9, 135, width=115)
        draw = self.group(1, 170, width=124, start=1500)
        self.assertEqual(_development_select_hand_cluster([hand, draw]), hand)

    def test_same_scale_preserves_largest_group(self):
        large = self.group(13, 170)
        small = self.group(7, 170, start=2000)
        self.assertEqual(_development_select_hand_cluster([large, small]), large)

    def test_two_alternative_groups_do_not_choose_arbitrarily(self):
        largest = self.group(9, 135, width=115)
        a = self.group(7, 170, y=94, width=124, start=1500)
        b = self.group(4, 170, y=94, width=124, start=2600)
        self.assertEqual(_development_select_hand_cluster([largest, a, b]), largest)

    def test_empty_input_stays_empty(self):
        self.assertEqual(_development_select_hand_cluster([]), [])
