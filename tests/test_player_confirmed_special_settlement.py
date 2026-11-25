"""Player-confirmed score regressions; these are not direct-video fixtures."""
from collections import Counter
import json
from pathlib import Path
import unittest

from huian import HuianEnvironment, HuianGameState, HuianRules
from huian._legacy import env
from huian.rules.registry import DEFAULT_RULE_SNAPSHOT
from workspace.simulator.match import MatchProgressState

FIXTURE = json.loads((Path(__file__).parent / 'fixtures' /
                      'player_confirmed_special_settlement_20261006.json').read_text())


def declaration_game(winner, *, kind=None, tile=None, eight=False):
    state = HuianGameState(phase='AFTER_DRAW', gold_tile='P9', current_player=winner,
                          dealer=0, special_states=['NORMAL', 'NORMAL'])
    state.reserved_tiles = ['P9']
    hand = ['P9'] * (1 if eight else 3) + ['E'] * 3
    state.hands[winner] = hand
    if kind:
        state.melds[winner] = [env.Meld(kind, [tile] * 4, None if kind == 'AN_GANG' else 1-winner)]
    state.flowers[winner] = list(env.FLOWERS) if eight else ['F1']
    remaining = env.full_wall()
    for item in state.physical_tiles():
        remaining.remove(item)
    for player, size in ((winner, 17 - 3 * len(state.melds[winner])), (1-winner, 16)):
        for item in remaining.copy():
            if item in env.BASE_TILES and item != 'P9' and len(state.hands[player]) < size:
                state.hands[player].append(item)
                remaining.remove(item)
    state.wall = remaining
    state.last_action = env.Action(winner, env.ActionType.DRAW,
                                  metadata={'source': 'wall_head',
                                            'drawn_tile': 'F8' if eight else 'P9'}).to_dict()
    game = HuianEnvironment()
    game.set_state(state)
    special = 'EIGHT_FLOWER_YOU' if eight else 'SANJINDAO'
    game.step(next(a for a in game.legal_actions() if a.metadata.get('special') == special))
    return game


class PlayerConfirmedSpecialSettlementTests(unittest.TestCase):
    def test_sanjindao_golden_cases_both_seats_and_dealer_flow(self):
        for winner in (0, 1):
            for case in FIXTURE['cases']:
                with self.subTest(winner=winner, case=case):
                    game = declaration_game(winner, kind=case['kind'], tile=case['tile'])
                    before = game.state
                    terminal, event = game.finalize_sanjindao_outcome(current_dealer_base=case['base'])
                    self.assertEqual(terminal.rewards[winner], case['net'])
                    self.assertEqual(sum(terminal.rewards), 0)
                    self.assertEqual(terminal.terminal_reason, 'AUTO_SANJINDAO')
                    self.assertEqual(Counter(terminal.physical_tiles()), Counter(env.full_wall()))
                    self.assertEqual(terminal.hands, before.hands)
                    self.assertEqual(terminal.wall, before.wall)
                    meta = event['action']['metadata']
                    self.assertEqual(meta['winner_fan'], case['kong_fan'])
                    self.assertEqual(meta['evidence_id'], FIXTURE['evidence_id'])
                    self.assertEqual(meta['rule_snapshot_fingerprint'], DEFAULT_RULE_SNAPSHOT.fingerprint)
                    progress = MatchProgressState.initial().apply_settled_hand(terminal.rewards, winner=winner)
                    self.assertEqual(progress.dealer, winner)
                    self.assertEqual(progress.current_dealer_base, 15 if winner == 0 else 10)
                    with self.assertRaisesRegex(ValueError, 'already terminal'):
                        game.finalize_sanjindao_outcome(current_dealer_base=case['base'])

    def test_eight_flower_no_gold_triplet_or_kong_stacking_both_seats(self):
        for winner in (0, 1):
            game = declaration_game(winner, kind='AN_GANG', tile='R', eight=True)
            before = Counter(game.state.physical_tiles())
            terminal, event = game.finalize_eight_flower_outcome(current_dealer_base=15)
            self.assertEqual(terminal.rewards[winner], 31)
            self.assertEqual(sum(terminal.rewards), 0)
            self.assertEqual(Counter(terminal.physical_tiles()), before)
            self.assertFalse(event['action']['metadata']['project_rule'])
            self.assertEqual(event['action']['metadata']['evidence_status'], 'CONFIRMED')
            progress = MatchProgressState.initial().apply_settled_hand(terminal.rewards, winner=winner)
            self.assertEqual(progress.current_dealer_base, 15 if winner == 0 else 10)

    def test_invalid_base_is_atomic_and_wrong_phase_is_rejected(self):
        for value in (-1, True, 1.5, '10'):
            for eight in (False, True):
                game = declaration_game(0, eight=eight)
                before, events = game.state.state_hash(), game.events
                finalizer = game.finalize_eight_flower_outcome if eight else game.finalize_sanjindao_outcome
                with self.assertRaises(ValueError):
                    finalizer(current_dealer_base=value)
                self.assertEqual(game.state.state_hash(), before)
                self.assertEqual(game.events, events)
        legacy = declaration_game(0, eight=True).state
        legacy.pending_hu['project_rule'] = True
        with self.assertRaises(ValueError):
            HuianEnvironment().set_state(legacy)
        with self.assertRaisesRegex(ValueError, 'declaration phase'):
            declaration_game(0, eight=True).finalize_sanjindao_outcome(current_dealer_base=10)

    def test_multiple_completed_kongs_sum_and_peng_does_not_score(self):
        rules = HuianRules()
        self.assertEqual(rules.sanjindao_fan([
            env.Meld('AN_GANG', ['M9'] * 4, 1),
            env.Meld('ADDED_GANG', ['R'] * 4, 1),
            env.Meld('PENG', ['E'] * 3, 1),
        ]), 6)
        with self.assertRaises(ValueError):
            rules.sanjindao_fan([env.Meld('AN_GANG', ['M9'] * 3, 1)])

    def test_promoted_records_have_new_revisions_and_player_provenance(self):
        for rule_id in ('settlement.sanjindao_full', 'settlement.eight_flower_real',
                        'settlement.eight_flower_working_multiplier',
                        'settlement.eight_flower_working_fixed_fan'):
            record = DEFAULT_RULE_SNAPSHOT.require_confirmed(rule_id)
            self.assertEqual(record.revision, 2)
            self.assertIn(FIXTURE['evidence_id'], record.evidence_ids)
        self.assertEqual(DEFAULT_RULE_SNAPSHOT.get('settlement.sanjindao_multiplier').revision, 1)
