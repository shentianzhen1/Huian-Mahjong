import unittest

from huian import HuianEnvironment, HuianGameState
from huian._legacy import env
from huian.rules.first_round import EVIDENCE_ID
from huian.rules.registry import DEFAULT_RULE_SNAPSHOT


GOLD = "P9"


def allocate_state(*, dealer, current_player, hand_sizes, flower_owner=None,
                   current_gold_count=0, discard=None):
    state = HuianGameState(
        dealer=dealer,
        current_player=current_player,
        phase="AFTER_DRAW",
        gold_tile=GOLD,
        special_states=["NORMAL", "NORMAL"],
        reserved_tiles=[GOLD],
    )
    pool = env.full_wall()
    pool.remove(GOLD)
    if flower_owner is not None:
        state.flowers[flower_owner] = list(env.FLOWERS)
        for flower in env.FLOWERS:
            pool.remove(flower)

    if discard is not None:
        pool.remove(discard)
        state.discards[dealer] = [discard]

    if current_gold_count:
        for _ in range(current_gold_count):
            pool.remove(GOLD)
        state.hands[current_player].extend([GOLD] * current_gold_count)

    for seat, target in enumerate(hand_sizes):
        need = target - len(state.hands[seat])
        candidates = [tile for tile in pool if tile != GOLD][:need]
        if len(candidates) != need:
            raise AssertionError("priority fixture could not allocate hand")
        for tile in candidates:
            pool.remove(tile)
        state.hands[seat].extend(candidates)

    state.wall = pool
    drawn = GOLD if current_gold_count else state.hands[current_player][-1]
    state.last_action = env.Action(
        current_player,
        env.ActionType.DRAW,
        metadata={"source": "WALL_HEAD", "drawn_tile": drawn},
    ).to_dict()
    return state


def game_from(state):
    game = HuianEnvironment()
    game.set_state(state)
    return game


class SpecialPriorityTests(unittest.TestCase):
    def test_eight_flower_suppresses_same_node_sanjindao(self):
        state = allocate_state(
            dealer=0,
            current_player=0,
            hand_sizes=(17, 16),
            flower_owner=0,
            current_gold_count=3,
        )
        actions = game_from(state).legal_actions()
        self.assertEqual(
            {action.type for action in actions},
            {env.ActionType.HU, env.ActionType.PASS_QIANGJIN},
        )
        hu = next(action for action in actions if action.type == env.ActionType.HU)
        self.assertEqual(hu.metadata.get("special"), "EIGHT_FLOWER_YOU")
        self.assertFalse(any(
            action.metadata.get("special") == "SANJINDAO"
            for action in actions
        ))

    def test_sanjindao_suppresses_first_round_qiangjin(self):
        state = allocate_state(
            dealer=0,
            current_player=1,
            hand_sizes=(16, 17),
            current_gold_count=3,
            discard="N",
        )
        state.first_round = {
            "evidence_id": EVIDENCE_ID,
            "rule_snapshot_fingerprint": DEFAULT_RULE_SNAPSHOT.fingerprint,
            "active": True,
            "dealer": 0,
            "nondealer": 1,
            "current_dealer_base": 10,
            "dealer_first_discard_done": True,
            "dealer_first_discard_tile": "N",
            "nondealer_first_draw_done": True,
            "nondealer_first_draw_tile": GOLD,
            "tianting": [False, False],
            "tianting_waits": [[], []],
            "qiangjin_eligible": [True, True],
            "qiangjin_resolved": [False, False],
            "qiangjin_fan": [0, 0],
            "qiangjin_candidate_fans": [[0], [0]],
            "qiangjin_reason": [
                "CONFIRMED_VIRTUAL_GOLD_HU",
                "CONFIRMED_VIRTUAL_GOLD_HU",
            ],
        }
        actions = game_from(state).legal_actions()
        self.assertEqual(
            {action.type for action in actions},
            {env.ActionType.HU, env.ActionType.PASS_QIANGJIN},
        )
        hu = next(action for action in actions if action.type == env.ActionType.HU)
        self.assertEqual(hu.metadata.get("special"), "SANJINDAO")
        self.assertFalse(any(
            action.type == env.ActionType.QIANGJIN for action in actions
        ))


if __name__ == "__main__":
    unittest.main()
