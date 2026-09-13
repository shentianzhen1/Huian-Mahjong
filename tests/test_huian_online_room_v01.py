import unittest

from huian._legacy import env
from huian.rules.online_room_v01 import HuianOnlineRoomV01


class Meld:
    def __init__(self, kind):
        self.kind = kind


class OnlineRoomProfileTests(unittest.TestCase):
    def test_target_feedback_is_explicit(self):
        profile = HuianOnlineRoomV01()
        self.assertEqual(profile.gold_tiles("M5"), frozenset(("M5",)))
        self.assertTrue(profile.allow_chi)
        self.assertFalse(profile.discard_gold_can_hu)
        self.assertEqual(profile.zimo_multiplier, 2)

    def test_gold_discard_cannot_be_claimed(self):
        profile = HuianOnlineRoomV01()
        for action in (env.ActionType.CHI, env.ActionType.PENG,
                       env.ActionType.MING_GANG, env.ActionType.HU):
            self.assertFalse(profile.may_claim_discard(action, "M5", "M5"))
        self.assertTrue(profile.may_claim_discard(env.ActionType.CHI, "M4", "M5"))

    def test_dynamic_reserve_is_explicit_and_switchable(self):
        melds = [[Meld("MING_GANG"), Meld("AN_GANG")], [Meld("AN_GANG")]]
        profile = HuianOnlineRoomV01()
        self.assertEqual(profile.wall_reserve(melds), 21)
        self.assertTrue(profile.is_wall_draw(21, melds))
        self.assertFalse(profile.is_wall_draw(22, melds))
        fixed = HuianOnlineRoomV01(dynamic_kong_reserve=False)
        self.assertEqual(fixed.wall_reserve(melds), 16)


if __name__ == "__main__":
    unittest.main()
