"""Player-confirmed opening scenarios, not fabricated video evidence."""
from collections import Counter
from copy import deepcopy
import unittest

from huian import HuianEnvironment, HuianGameState, HuianRules, UnknownRuleError
from huian._legacy import env
from huian.environment.opening import plan_opening
from huian.rules.registry import DEFAULT_RULE_SNAPSHOT
from workspace.simulator.match import MatchProgressState

WIN = ['M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'P1', 'P2', 'P3',
       'S1', 'S2', 'S3', 'E', 'E', 'E', 'N', 'N']
LOSE = ['M1'] * 4 + ['M2'] * 4 + ['M4'] * 3 + ['P2', 'P2', 'S5', 'S5', 'W', 'R']


def staged_game(*, dealer=0, flowers=(), hand=None, phase='OPENING_GOLD_PENDING'):
    state = HuianGameState(dealer=dealer, current_player=dealer, phase=phase,
                          special_states=['NORMAL', 'NORMAL'])
    state.hands[dealer] = list(LOSE if hand is None else hand)
    state.flowers[dealer] = list(flowers)
    remaining = env.full_wall()
    for tile in state.physical_tiles():
        remaining.remove(tile)
    for tile in remaining.copy():
        if tile in env.BASE_TILES and len(state.hands[1-dealer]) < 16:
            state.hands[1-dealer].append(tile)
            remaining.remove(tile)
    state.wall = remaining
    game = HuianEnvironment()
    game.set_state(state)
    return game


def ready_wall(dealer_hand, replacements, *, dealer=0):
    remaining = env.full_wall()
    for tile in dealer_hand + replacements:
        remaining.remove(tile)
    idle = [t for t in remaining if t in env.BASE_TILES][:16]
    for tile in idle:
        remaining.remove(tile)
    prefix = [t for pair in zip(dealer_hand[:16], idle) for t in pair] + [dealer_hand[16]]
    return prefix + remaining + list(reversed(replacements))


class ConfirmedOpeningTests(unittest.TestCase):
    def assert_physical(self, state):
        self.assertEqual(Counter(state.physical_tiles()), Counter(env.full_wall()))
        self.assertEqual(len(state.hands[state.dealer]), 17)
        self.assertEqual(len(state.hands[1-state.dealer]), 16)

    def test_replacement_chain_finishes_before_any_candidate(self):
        initial = LOSE.copy()
        initial[0] = 'F1'
        game = HuianEnvironment()
        game.reset(wall=ready_wall(initial, ['F2', 'M9']))
        state, event = game.begin_confirmed_opening()
        self.assertEqual(state.phase, 'OPENING_GOLD_PENDING')
        self.assertIsNone(state.gold_tile)
        self.assertEqual(state.flowers[0], ['F1', 'F2'])
        self.assertIn('M9', state.hands[0])
        self.assertEqual(len(event['action']['metadata']['replacement_events']), 2)
        self.assert_physical(state)
        self.assertEqual(game.action_report().unresolved, ('opening_candidate_location',))
        with self.assertRaises(ValueError):
            game.begin_confirmed_opening()

    def test_candidate_flowers_go_only_to_dealer_then_indicator_reserved(self):
        for dealer in (0, 1):
            game = staged_game(dealer=dealer)
            hands = deepcopy(game.state.hands)
            for flower in ('F1', 'F2'):
                state, event = game.reveal_opening_candidate(
                    wall_index=game.state.wall.index(flower), current_dealer_base=10)
                self.assertEqual(state.hands, hands)
                self.assertIn(flower, state.flowers[dealer])
                self.assertNotIn(flower, state.wall)
                self.assertIsNone(state.gold_tile)
                self.assertFalse(event['action']['metadata']['hand_replacement'])
                self.assert_physical(state)
            state, _ = game.reveal_opening_candidate(
                wall_index=game.state.wall.index('P9'), current_dealer_base=10)
            self.assertEqual(state.phase, 'OPENING_POST_GOLD_PENDING')
            self.assertEqual(state.reserved_tiles, ['P9'])
            self.assertEqual(state.wall.count('P9') + sum(h.count('P9') for h in state.hands), 3)
            self.assertEqual(state.hands, hands)
            self.assert_physical(state)
            with self.assertRaises(UnknownRuleError):
                game.legal_actions()  # Future Qiangjin/Tianting cannot be guessed.

    def test_new_eighth_flower_forces_terminal_with_no_gold_and_no_more_flips(self):
        for dealer in (0, 1):
            # Even an ordinary winning17 must end by Eight-Flower before Gold/Tianhu.
            game = staged_game(dealer=dealer, flowers=env.FLOWERS[:7], hand=WIN)
            before = deepcopy(game.state.hands)
            state, event = game.reveal_opening_candidate(
                wall_index=game.state.wall.index('F8'), current_dealer_base=15)
            self.assertTrue(state.terminal)
            self.assertEqual(state.terminal_reason, 'AUTO_EIGHT_FLOWER_YOU')
            self.assertIsNone(state.gold_tile)
            self.assertEqual(state.reserved_tiles, [])
            self.assertEqual(state.hands, before)
            self.assertEqual(state.rewards[dealer], 31)
            self.assertTrue(event['action']['metadata']['forced'])
            self.assertEqual(game.legal_actions(), [])
            self.assert_physical(state)
            progress = MatchProgressState.initial(dealer=dealer).apply_settled_hand(state.rewards, winner=dealer)
            self.assertEqual(progress.current_dealer_base, 15)
            with self.assertRaises(ValueError):
                game.reveal_opening_candidate(wall_index=0, current_dealer_base=15)
            imported = HuianEnvironment().set_state(state)
            self.assertEqual(imported.state_hash(), state.state_hash())

    def test_preopening_eight_flowers_choice_hu_or_pass_then_tianhu(self):
        for dealer in (0, 1):
            initial = WIN[:9] + list(env.FLOWERS)
            wall = ready_wall(initial, WIN[9:])
            game = HuianEnvironment()
            game.reset(wall=wall, dealer=dealer)
            state, _ = game.begin_confirmed_opening()
            self.assertEqual(state.phase, 'OPENING_EIGHT_FLOWER_CHOICE')
            self.assertIsNone(state.gold_tile)
            self.assert_physical(state)
            actions = game.legal_actions()
            self.assertEqual({a.type for a in actions}, {env.ActionType.HU, env.ActionType.PASS_QIANGJIN})
            declare = game.clone()
            declare.step(next(a for a in actions if a.type == env.ActionType.HU))
            ended, _ = declare.finalize_eight_flower_outcome(current_dealer_base=10)
            self.assertIsNone(ended.gold_tile)
            self.assertEqual(ended.rewards[dealer], 26)
            self.assert_physical(ended)
            game.step(next(a for a in actions if a.type == env.ActionType.PASS_QIANGJIN))
            self.assertEqual(game.state.phase, 'OPENING_GOLD_PENDING')
            self.assertEqual(len(game.state.flowers[dealer]), 8)
            ended, event = game.reveal_opening_candidate(
                wall_index=game.state.wall.index('P9'), current_dealer_base=10)
            self.assertEqual(ended.terminal_reason, 'AUTO_TIANHU')
            self.assertEqual(ended.rewards[dealer], 20)  # No eight flowers or triplet fan.
            self.assertEqual(event['action']['metadata']['winner_fan'], 0)
            self.assert_physical(ended)

    def test_preopening_eight_pass_does_not_force_or_immediately_reoffer(self):
        for owner in (0, 1):
            game = staged_game(flowers=env.FLOWERS, phase='OPENING_EIGHT_FLOWER_CHOICE')
            if owner == 1:
                state = game.state
                state.flowers = [[], list(env.FLOWERS)]
                state.current_player = 1
                game.set_state(state)
            with self.assertRaises(ValueError):
                game.reveal_opening_candidate(wall_index=0, current_dealer_base=10)
            clone = game.clone()
            clone.step(next(a for a in clone.legal_actions() if a.type == env.ActionType.HU))
            terminal, _ = clone.finalize_eight_flower_outcome(current_dealer_base=15)
            self.assertEqual(terminal.rewards[owner], 31)
            self.assert_physical(terminal)
            passed = next(a for a in game.legal_actions() if a.type == env.ActionType.PASS_QIANGJIN)
            game.step(passed)
            state, _ = game.reveal_opening_candidate(
                wall_index=game.state.wall.index('P9'), current_dealer_base=10)
            self.assertFalse(state.terminal)
            self.assertEqual(state.phase, 'OPENING_POST_GOLD_PENDING')
            self.assertEqual(len(state.flowers[owner]), 8)
            self.assertEqual(state.rewards, [0, 0])
            self.assert_physical(state)

    def test_tianhu_uses_gold_only_after_full_opening_for_dealer(self):
        wildcard = WIN.copy()
        wildcard[-1] = 'P9'
        rules = HuianRules()
        self.assertFalse(rules.can_tianhu(wildcard, None, is_dealer=True, opening_complete=False))
        self.assertFalse(rules.can_tianhu(wildcard, 'P9', is_dealer=False, opening_complete=True))
        self.assertFalse(rules.can_tianhu(wildcard[:14], 'P9', is_dealer=True, opening_complete=True))
        self.assertFalse(rules.can_tianhu(wildcard, 'P9', is_dealer=True, opening_complete=False))
        for dealer in (0, 1):
            game = staged_game(dealer=dealer, hand=wildcard)
            state, event = game.reveal_opening_candidate(
                wall_index=game.state.wall.index('P9'), current_dealer_base=25)
            self.assertEqual(state.terminal_reason, 'AUTO_TIANHU')
            self.assertEqual(state.rewards[dealer], 50)
            self.assertEqual(event['action']['metadata']['special'], 'TIANHU')
            self.assert_physical(state)
        three_gold = LOSE.copy()
        three_gold[:3] = ['P9'] * 3
        self.assertFalse(rules.can_tianhu(three_gold, 'P9', is_dealer=True, opening_complete=True))
        with self.assertRaises(ValueError):
            rules.can_tianhu(wildcard, 'P9', is_dealer=1, opening_complete=True)

    def test_invalid_candidate_requests_are_atomic_and_goldless_import_is_narrow(self):
        game = staged_game()
        before, events = game.state.state_hash(), game.events
        for index, base in ((True, 10), (-1, 10), (9999, 10), (0, True), (0, -1)):
            with self.assertRaises(ValueError):
                game.reveal_opening_candidate(wall_index=index, current_dealer_base=base)
            self.assertEqual(game.state.state_hash(), before)
            self.assertEqual(game.events, events)
        for change in ('bad_hand', 'reserved', 'normal_phase', 'fake_terminal'):
            invalid = game.state
            if change == 'bad_hand':
                invalid.wall.append(invalid.hands[0].pop())
            elif change == 'reserved':
                invalid.reserved_tiles.append(invalid.wall.pop())
            elif change == 'normal_phase':
                invalid.phase = 'AFTER_DRAW'
            else:
                invalid.phase = 'TERMINAL'
                invalid.terminal = True
                invalid.terminal_reason = 'AUTO_ZIMO'
                invalid.rewards = [20, -20]
            with self.assertRaises(ValueError):
                HuianEnvironment().set_state(invalid)

    def test_rollback_and_deterministic_opening_history(self):
        game = staged_game(flowers=env.FLOWERS[:7])
        duplicate = game.clone()
        token = game.checkpoint()
        index = game.state.wall.index('F8')
        state, event = game.reveal_opening_candidate(wall_index=index, current_dealer_base=10)
        other, other_event = duplicate.reveal_opening_candidate(wall_index=index, current_dealer_base=10)
        self.assertEqual(state.state_hash(), other.state_hash())
        self.assertEqual(event, other_event)
        game.rollback(token)
        self.assertFalse(game.state.terminal)
        self.assertIn('F8', game.state.wall)
        self.assertEqual(game.events, [])
        self.assertEqual(event['action']['metadata']['rule_snapshot_fingerprint'], DEFAULT_RULE_SNAPSHOT.fingerprint)

    def test_legacy_planner_must_pause_instead_of_skip_preopening_eight_choice(self):
        initial = WIN[:9] + list(env.FLOWERS)
        with self.assertRaisesRegex(UnknownRuleError, 'eight_flower_opening_choice'):
            plan_opening(ready_wall(initial, WIN[9:]), 0, 2)
