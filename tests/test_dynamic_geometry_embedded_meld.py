import unittest
from workspace.vision.tiles_runtime_v0_2.dynamic_geometry import _split_embedded_meld_prefix


class EmbeddedMeldPrefixTests(unittest.TestCase):
    def test_plain_upright_hand_is_not_split(self):
        hand=[(100+i*25,430,24,64) for i in range(16)]
        meld,concealed=_split_embedded_meld_prefix(hand,24)
        self.assertEqual(meld,[])
        self.assertEqual(len(concealed),16)

    def test_flush_short_meld_prefix_is_split_from_upright_hand(self):
        meld=[(100+i*25,442,24,52) for i in range(4)]
        hand=[(200+i*25,430,24,64) for i in range(13)]
        exposed,concealed=_split_embedded_meld_prefix(meld+hand,24)
        self.assertEqual(len(exposed),4)
        self.assertEqual(len(concealed),13)

    def test_height_difference_without_baseline_change_is_not_enough(self):
        prefix=[(100+i*25,442,24,52) for i in range(4)]  # bottom=494
        hand=[(200+i*25,430,24,64) for i in range(13)]   # bottom=494
        exposed,concealed=_split_embedded_meld_prefix(prefix+hand,24)
        self.assertEqual(exposed,[])
        self.assertEqual(len(concealed),17)


if __name__=="__main__": unittest.main()
