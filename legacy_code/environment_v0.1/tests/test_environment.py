
import unittest
from qzenv import QuanzhouEnvironment, Action, ActionType
from qzenv.tiles import full_wall
from qzenv.evaluation import MatchStats, paired_wall_seeds

class EnvTests(unittest.TestCase):
    def test_reset_144(self):
        env = QuanzhouEnvironment()
        st = env.reset(seed=1)
        self.assertEqual(st.wall_remaining(), 144)
        self.assertEqual(st.players, 2)

    def test_draw_reduces_wall(self):
        env = QuanzhouEnvironment()
        st = env.reset(seed=2)
        p = st.current_player
        st, ev = env.step(Action(p, ActionType.DRAW))
        self.assertEqual(st.wall_remaining(), 143)
        self.assertEqual(len(st.hands[p]), 1)
        self.assertEqual(ev.action.type, ActionType.DRAW)

    def test_discard_moves_tile_to_river(self):
        env = QuanzhouEnvironment()
        st = env.reset(seed=3)
        p = st.current_player
        st, _ = env.step(Action(p, ActionType.DRAW))
        tile = st.hands[p][0]
        st, _ = env.step(Action(p, ActionType.DISCARD, tile=tile))
        self.assertNotIn(tile, st.hands[p])
        self.assertIn(tile, st.discards[p])
        self.assertEqual(st.current_player, 1)

    def test_checkpoint_rollback(self):
        env = QuanzhouEnvironment()
        st = env.reset(seed=4)
        p = st.current_player
        st, _ = env.step(Action(p, ActionType.DRAW))
        before = env.state.state_hash()
        token = env.checkpoint()
        tile = env.state.hands[p][0]
        env.step(Action(p, ActionType.DISCARD, tile=tile))
        self.assertNotEqual(env.state.state_hash(), before)
        env.rollback(token)
        self.assertEqual(env.state.state_hash(), before)

    def test_clone_is_independent(self):
        env = QuanzhouEnvironment()
        st = env.reset(seed=5)
        clone = env.clone()
        clone.step(Action(clone.state.current_player, ActionType.DRAW))
        self.assertEqual(env.state.wall_remaining(), 144)
        self.assertEqual(clone.state.wall_remaining(), 143)

    def test_event_log(self):
        env = QuanzhouEnvironment()
        st = env.reset(seed=6)
        env.step(Action(st.current_player, ActionType.DRAW))
        self.assertEqual(len(env.events), 1)
        self.assertEqual(env.events[0].seq, 0)
        self.assertNotEqual(env.events[0].before_hash, env.events[0].after_hash)

    def test_end_hand_rewards(self):
        env = QuanzhouEnvironment()
        st = env.reset(seed=7)
        env.step(Action(
            st.current_player,
            ActionType.END_HAND,
            metadata={"rewards":[34,-34]}
        ), strict=False)
        self.assertTrue(env.is_terminal())
        self.assertEqual(env.get_reward(), [34,-34])

    def test_zero_sum_stats(self):
        stats = MatchStats()
        stats.add_result([34,-34])
        stats.add_result([-10,10])
        stats.assert_zero_sum()
        self.assertEqual(stats.games, 2)

    def test_paired_wall_seeds(self):
        items = list(paired_wall_seeds(3, base_seed=100))
        self.assertEqual(len(items), 6)
        self.assertEqual(items[0]["seed"], items[1]["seed"])
        self.assertNotEqual(items[0]["swap_seats"], items[1]["swap_seats"])

if __name__ == "__main__":
    unittest.main()
