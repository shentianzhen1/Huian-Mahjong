import random
import unittest
from collections import Counter

from huian._legacy import env
from test_huian_environment import HAND, scenario, game, choose


class PassBoundaryTests(unittest.TestCase):
    def test_pass_both_seats_preserves_river_and_draws_head(self):
        for player in (0, 1):
            for discard in ("M3", "P9"):
                state = scenario(discard=discard)
                if player == 1:
                    state.hands.reverse()
                    state.discards.reverse()
                    state.current_player = 1
                    state.pending_discard["player"] = 0
                instance = game(state)
                passed, _ = instance.step(env.Action(player, env.ActionType.PASS))
                self.assertEqual(passed.phase, "NEED_DRAW")
                self.assertEqual(passed.current_player, player)
                self.assertIsNone(passed.pending_discard)
                self.assertEqual(passed.discards, state.discards)
                self.assertEqual(passed.hands, state.hands)
                self.assertEqual(passed.wall, state.wall)
                action = env.Action(player, env.ActionType.DRAW, metadata={"source": "wall_head"})
                self.assertEqual(instance.legal_actions(), [action])
                drawn, _ = instance.step(action)
                self.assertEqual(drawn.hands[player][-1], state.wall[0])
                self.assertEqual(Counter(drawn.physical_tiles()), Counter(env.full_wall()))

    def test_illegal_pass_is_atomic(self):
        for phase, player in (("NEED_DRAW", 0), ("AFTER_DISCARD", 1)):
            instance = game(scenario(phase))
            before = instance.state.state_hash()
            with self.assertRaises(ValueError):
                instance.step(env.Action(player, env.ActionType.PASS))
            self.assertEqual(instance.state.state_hash(), before)
            self.assertEqual(instance.events, [])

    def test_head_and_kong_tail_reach_16_including_flower(self):
        for kind in (None, env.ActionType.MING_GANG, env.ActionType.AN_GANG):
            for tile in ("P8", "F8"):
                if kind is None:
                    state = scenario("NEED_DRAW")
                else:
                    state = (scenario(discard="E") if kind == env.ActionType.MING_GANG
                             else scenario("AFTER_DRAW", HAND + ["E"]))
                    setup = game(state, experimental=True)
                    setup.step(choose(setup, kind))
                    state = setup.state
                state.wall.remove(tile)
                state.reserved_tiles.extend(state.wall[16:])
                state.wall = state.wall[:16]
                state.wall.insert(0 if kind is None else len(state.wall), tile)
                instance = game(state)
                self.assertFalse(instance.is_terminal())
                token = instance.checkpoint()
                before = instance.state.state_hash()
                action = instance.legal_actions()[0]
                after, event = instance.step(action)
                self.assertTrue(after.terminal)
                self.assertEqual(after.phase, "TERMINAL")
                self.assertEqual(after.terminal_reason, "WALL_16")
                self.assertEqual(after.wall_remaining(), 16)
                self.assertEqual(after.hands[0][-1], tile)
                self.assertEqual(after.dealer, state.dealer)
                self.assertEqual(instance.get_reward(), [0, 0])
                self.assertEqual(Counter(after.physical_tiles()), Counter(env.full_wall()))
                self.assertEqual(event["after_hash"], after.state_hash())
                self.assertEqual(instance.legal_actions(), [])
                with self.assertRaises(ValueError):
                    instance.step(action)
                bad = instance.state
                bad.rewards = [44, -44]
                with self.assertRaises(ValueError):
                    game(bad)
                self.assertEqual(instance.rollback(token).state_hash(), before)
                self.assertEqual(instance.step(action)[1], event)

    def test_seeded_loop_conservation_zero_sum_and_replay(self):
        def seeded(seed):
            state = scenario()
            # Mid-hand fixture excludes unresolved gold/flower paths, not a deal.
            usable = [t for t in state.wall if t not in env.FLOWERS and t != "P9"]
            random.Random(seed).shuffle(usable)
            wall = usable[:20]
            for tile in wall:
                state.wall.remove(tile)
            state.reserved_tiles.extend(state.wall)
            state.wall = wall
            return game(state)
        a, b = seeded(71), seeded(71)
        self.assertEqual(a.state.state_hash(), b.state.state_hash())
        self.assertNotEqual(a.state.state_hash(), seeded(72).state.state_hash())
        replay = a.clone()
        for instance in (a, b):
            for _ in range(20):
                if instance.is_terminal():
                    break
                state = instance.state
                if state.phase == "AFTER_DISCARD":
                    action = env.Action(state.current_player, env.ActionType.PASS)
                elif state.phase == "NEED_DRAW":
                    action = env.Action(state.current_player, env.ActionType.DRAW,
                                        metadata={"source": "wall_head"})
                else:
                    action = env.Action(state.current_player, env.ActionType.DISCARD,
                                        tile=state.hands[state.current_player][-1])
                instance.step(action)
                self.assertEqual(Counter(instance.state.physical_tiles()), Counter(env.full_wall()))
                self.assertEqual(sum(instance.get_reward()), 0)
            self.assertTrue(instance.is_terminal())
            self.assertEqual(instance.state.wall_remaining(), 16)
        self.assertEqual(a.events, b.events)
        for event in a.events:
            replay.step(env.Action.from_dict(event["action"]))
        self.assertEqual(replay.events, a.events)
        self.assertEqual(replay.state.state_hash(), a.state.state_hash())
