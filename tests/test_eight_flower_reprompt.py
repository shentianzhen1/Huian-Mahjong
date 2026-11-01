import unittest

from huian import HuianEnvironment, HuianGameState
from huian._legacy import env
from huian.rules.registry import DEFAULT_RULE_SNAPSHOT


GOLD = "P9"


def eight_flower_after_draw_state(*, replacement=False):
    state = HuianGameState(
        dealer=0,
        current_player=0,
        phase="AFTER_DRAW",
        gold_tile=GOLD,
        special_states=["NORMAL", "NORMAL"],
        reserved_tiles=[GOLD],
    )
    state.flowers[0] = list(env.FLOWERS)

    pool = env.full_wall()
    for flower in env.FLOWERS:
        pool.remove(flower)
    pool.remove(GOLD)
    state.hands[0] = pool[:17]
    state.hands[1] = pool[17:33]
    state.wall = pool[33:]

    drawn_tile = state.hands[0][-1]
    metadata = {
        "source": "WALL_HEAD",
        "drawn_tile": drawn_tile,
    }
    if replacement:
        # A completed automatic replacement chain remains represented by the
        # original DRAW event with the final non-flower exposed separately.
        metadata["drawn_tile"] = env.FLOWERS[0]
        metadata["effective_drawn_tile"] = drawn_tile
    state.last_action = env.Action(
        0, env.ActionType.DRAW, metadata=metadata
    ).to_dict()
    return state


def game_from(state):
    game = HuianEnvironment()
    game.set_state(state)
    return game


def eight_flower_actions(game):
    return [
        action for action in game.legal_actions()
        if (action.type == env.ActionType.HU
            and action.metadata.get("special") == "EIGHT_FLOWER_YOU")
    ]


class EightFlowerRepromptTests(unittest.TestCase):
    def test_registry_records_node_local_pass_and_later_reoffer(self):
        rule = DEFAULT_RULE_SNAPSHOT.require_confirmed(
            "state_machine.eight_flower_reprompt"
        )
        self.assertEqual(rule.value["pass_scope"], "CURRENT_NODE_ONLY")
        self.assertEqual(rule.value["later_own_draw"], "REOFFER_WHILE_STILL_8")
        self.assertEqual(
            rule.value["completed_replacement"], "REOFFER_WHILE_STILL_8"
        )
        self.assertFalse(rule.value["same_node_immediate_reprompt"])
        self.assertIn(
            "player_confirmed_special_rules_20261006_v1",
            rule.evidence_ids,
        )

    def test_later_normal_own_draw_reoffers_while_still_eight_flowers(self):
        game = game_from(eight_flower_after_draw_state())
        actions = game.legal_actions()
        self.assertEqual(len(eight_flower_actions(game)), 1)
        self.assertEqual(
            {action.type for action in actions},
            {env.ActionType.HU, env.ActionType.PASS_QIANGJIN},
        )

    def test_pass_closes_only_current_node_without_immediate_reprompt(self):
        game = game_from(eight_flower_after_draw_state())
        passed = next(
            action for action in game.legal_actions()
            if action.type == env.ActionType.PASS_QIANGJIN
        )
        state, event = game.step(passed)
        self.assertEqual(
            event["action"]["metadata"]["declined"],
            "EIGHT_FLOWER_YOU",
        )
        self.assertEqual(state.phase, "AFTER_DRAW")
        actions = game.legal_actions()
        self.assertFalse(any(
            action.type == env.ActionType.HU
            and action.metadata.get("special") == "EIGHT_FLOWER_YOU"
            for action in actions
        ))
        self.assertTrue(any(
            action.type == env.ActionType.DISCARD for action in actions
        ))

    def test_completed_replacement_draw_also_reoffers(self):
        game = game_from(eight_flower_after_draw_state(replacement=True))
        actions = game.legal_actions()
        special = next(
            action for action in actions
            if action.type == env.ActionType.HU
            and action.metadata.get("special") == "EIGHT_FLOWER_YOU"
        )
        self.assertEqual(special.metadata["fixed_fan"], 16)
        self.assertEqual(special.metadata["multiplier"], 1)


if __name__ == "__main__":
    unittest.main()
