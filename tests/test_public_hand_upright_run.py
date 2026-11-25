import unittest
from workspace.vision.public_hand_upright_run import UprightFace,count_upright_hand,fuse_upright_hand_counts


def hand(n,start=200):
    return [UprightFace(start+i*25,430,24,64) for i in range(n)]


class UprightHandRunTests(unittest.TestCase):
    def test_plain_sixteen(self):
        self.assertEqual(count_upright_hand(hand(16)).count,16)

    def test_short_flush_meld_does_not_join_hand(self):
        meld=[UprightFace(100+i*25,442,24,52) for i in range(4)]
        out=count_upright_hand(meld+hand(13,start=200))
        self.assertEqual(out.count,13)

    def test_isolated_draw_does_not_join_hand(self):
        faces=hand(13)+[UprightFace(550,430,24,64)]
        self.assertEqual(count_upright_hand(faces).count,13)

    def test_three_frame_fusion(self):
        counts=[count_upright_hand(hand(13)) for _ in range(3)]
        out=fuse_upright_hand_counts(counts)
        self.assertEqual(out.status,"STABLE_UPRIGHT_HAND_COUNT_CANDIDATE_ONLY")
        self.assertEqual(out.count,13)


if __name__=="__main__": unittest.main()
