"""Issue #9 Tianting status + first-discard timing (scripted, PLAYER_CONFIRMED).

Tianhu already has dedicated coverage. This locks the remaining Tianting
contract: status-only, Gold wildcard, dealer-after-first-discard /
nondealer-before-first-draw timing, both seats, and no score change.
These are synthetic rule scenarios, not video confirmation.
"""
from __future__ import annotations

from collections import Counter
import unittest

from huian import HuianEnvironment, HuianGameState
from huian._legacy import env
from huian.rules.first_round import (
    EVIDENCE_ID,
    new_first_round_state,
    record_dealer_first_discard,
    tianting_status,
)
from huian.rules.registry import DEFAULT_RULE_SNAPSHOT


GOLD = "P9"

# Four melds + pair-ish wait: ting for P3/P6 (and Gold wildcard paths).
LISTENING16 = [
    "M1", "M2", "M3", "M4", "M5", "M6",
    "P1", "P2", "P3", "S1", "S2", "S3",
    "W", "W", "P4", "P5",
]

# Dealer opening 17 = listening16 + one discardable singleton.
DEALER_LISTENING17 = [*LISTENING16, "N"]

# Clearly not ting even with Gold wildcard.
NOT_LISTENING16 = [
    "M1", "M1", "M2", "M4", "M6", "M8",
    "P1", "P3", "P5", "P7",
    "S1", "S3", "S5", "S7",
    "W", "W",
]

DEALER_NOT_LISTENING17 = [*NOT_LISTENING16, "N"]

# Gold is the only way this 16 reaches ting (pair of Gold as wildcards
# completing the missing tile in a near-ready shape is out of scope here).
# Hand is 3 melds + EE pair + P1 P2 + one Gold: waits P3 via Gold or P3.
GOLD_WILDCARD_TING16 = [
    "M1", "M2", "M3", "M4", "M5", "M6",
    "S1", "S2", "S3", "E", "E",
    "P1", "P2", GOLD, "W", "W",
]


def first_round_game(
    *,
    dealer=0,
    dealer_hand=None,
    nondealer_hand=None,
    draw_tile="B",
    base=10,
):
    state = HuianGameState(
        dealer=dealer,
        current_player=dealer,
        phase="OPENING_POST_GOLD_PENDING",
        gold_tile=GOLD,
        special_states=["NORMAL", "NORMAL"],
        reserved_tiles=[GOLD],
    )
    state.hands[dealer] = list(
        DEALER_LISTENING17 if dealer_hand is None else dealer_hand
    )
    state.hands[1 - dealer] = list(
        LISTENING16 if nondealer_hand is None else nondealer_hand
    )
    remaining = env.full_wall()
    for tile in state.physical_tiles():
        remaining.remove(tile)
    remaining.remove(draw_tile)
    state.wall = [draw_tile, *remaining]
    state.first_round = new_first_round_state(state, current_dealer_base=base)
    game = HuianEnvironment()
    game.set_state(state)
    return game


def dealer_discard_tile(game, tile="N"):
    return next(
        action
        for action in game.legal_actions()
        if action.type == env.ActionType.DISCARD and action.tile == tile
    )


class TiantingFirstDiscardRegressionTests(unittest.TestCase):
    def test_registry_marks_tianting_as_zero_bonus_status(self):
        record = DEFAULT_RULE_SNAPSHOT.require_confirmed(
            "state_machine.tianting_status"
        )
        self.assertEqual(
            record.value["dealer"], "AFTER_FIRST_DISCARD_REMAINING_16_TING"
        )
        self.assertEqual(
            record.value["nondealer"], "INITIAL_16_BEFORE_FIRST_DRAW_TING"
        )
        self.assertEqual(record.value["bonus_fan"], 0)
        self.assertEqual(record.value["bonus_multiplier"], 1)
        self.assertIn("status", record.note.lower())

    def test_tianting_status_helper_requires_16_and_uses_gold(self):
        listening, waits = tianting_status(LISTENING16, GOLD)
        self.assertTrue(listening)
        self.assertTrue(waits)
        self.assertIn("P3", waits)

        quiet, empty = tianting_status(NOT_LISTENING16, GOLD)
        self.assertFalse(quiet)
        self.assertEqual(empty, ())

        gold_listening, gold_waits = tianting_status(GOLD_WILDCARD_TING16, GOLD)
        self.assertTrue(gold_listening)
        self.assertTrue(gold_waits)

        with self.assertRaises(ValueError):
            tianting_status(LISTENING16[:15], GOLD)
        with self.assertRaises(ValueError):
            tianting_status([*LISTENING16, "N"], GOLD)

    def test_nondealer_tianting_marked_before_first_draw_both_seats(self):
        for dealer in (0, 1):
            with self.subTest(dealer=dealer, listening=True):
                game = first_round_game(dealer=dealer)
                first = game.state.first_round
                nondealer = 1 - dealer
                self.assertEqual(first["evidence_id"], EVIDENCE_ID)
                self.assertTrue(first["active"])
                self.assertTrue(first["tianting"][nondealer])
                self.assertTrue(first["tianting_waits"][nondealer])
                # Dealer is evaluated only after the first discard.
                self.assertIsNone(first["tianting"][dealer])
                self.assertEqual(first["tianting_waits"][dealer], [])
                self.assertFalse(first["dealer_first_discard_done"])
                self.assertEqual(game.state.rewards, [0, 0])
                self.assertFalse(game.state.terminal)

            with self.subTest(dealer=dealer, listening=False):
                game = first_round_game(
                    dealer=dealer, nondealer_hand=NOT_LISTENING16
                )
                first = game.state.first_round
                nondealer = 1 - dealer
                self.assertFalse(first["tianting"][nondealer])
                self.assertEqual(first["tianting_waits"][nondealer], [])
                self.assertIsNone(first["tianting"][dealer])
                self.assertEqual(game.state.rewards, [0, 0])

    def test_dealer_tianting_only_after_first_discard_both_seats(self):
        for dealer in (0, 1):
            with self.subTest(dealer=dealer, listening=True):
                game = first_round_game(dealer=dealer)
                before_rewards = list(game.state.rewards)
                before_tiles = Counter(game.state.physical_tiles())
                self.assertIsNone(game.state.first_round["tianting"][dealer])

                state, event = game.step(dealer_discard_tile(game, "N"))
                first = state.first_round
                self.assertTrue(first["dealer_first_discard_done"])
                self.assertEqual(first["dealer_first_discard_tile"], "N")
                self.assertEqual(len(state.hands[dealer]), 16)
                self.assertTrue(first["tianting"][dealer])
                self.assertTrue(first["tianting_waits"][dealer])
                self.assertTrue(event["action"]["metadata"]["first_round_dealer_discard"])
                self.assertTrue(event["action"]["metadata"]["dealer_tianting"])
                self.assertEqual(
                    list(event["action"]["metadata"]["dealer_tianting_waits"]),
                    first["tianting_waits"][dealer],
                )
                # Status marker only: no settlement, no tile creation/loss.
                self.assertEqual(state.rewards, before_rewards)
                self.assertEqual(sum(state.rewards), 0)
                self.assertFalse(state.terminal)
                self.assertEqual(before_tiles, Counter(state.physical_tiles()))

            with self.subTest(dealer=dealer, listening=False):
                game = first_round_game(
                    dealer=dealer, dealer_hand=DEALER_NOT_LISTENING17
                )
                state, event = game.step(dealer_discard_tile(game, "N"))
                first = state.first_round
                self.assertTrue(first["dealer_first_discard_done"])
                self.assertFalse(first["tianting"][dealer])
                self.assertEqual(first["tianting_waits"][dealer], [])
                self.assertFalse(event["action"]["metadata"]["dealer_tianting"])
                self.assertEqual(state.rewards, [0, 0])
                self.assertFalse(state.terminal)

    def test_tianting_does_not_alter_rewards_across_first_discard_window(self):
        game = first_round_game(base=25)
        self.assertEqual(game.state.rewards, [0, 0])
        nondealer = 1 - game.state.dealer
        self.assertTrue(game.state.first_round["tianting"][nondealer])

        game.step(dealer_discard_tile(game, "N"))
        self.assertEqual(game.state.rewards, [0, 0])
        self.assertTrue(game.state.first_round["tianting"][game.state.dealer])

        # Opponent PASS on the discard, then nondealer draws — still no
        # Tianting-driven score change.
        game.step(next(
            a for a in game.legal_actions() if a.type == env.ActionType.PASS
        ))
        game.step(next(
            a for a in game.legal_actions() if a.type == env.ActionType.DRAW
        ))
        self.assertEqual(game.state.rewards, [0, 0])
        self.assertFalse(game.state.terminal)
        # Nondealer status was fixed at opening; first draw does not rewrite it.
        self.assertTrue(game.state.first_round["tianting"][nondealer])

    def test_record_dealer_first_discard_is_idempotent_for_tianting(self):
        game = first_round_game()
        state = game.state
        dealer = state.dealer
        # Mirror transitions: tile leaves the hand before provenance records.
        state.hands[dealer].remove("N")
        state.discards[dealer].append("N")
        record_dealer_first_discard(state, "N")
        first = state.first_round
        marked = first["tianting"][dealer]
        waits = list(first["tianting_waits"][dealer])
        self.assertTrue(first["dealer_first_discard_done"])
        record_dealer_first_discard(state, "N")
        self.assertEqual(first["tianting"][dealer], marked)
        self.assertEqual(first["tianting_waits"][dealer], waits)
        self.assertEqual(first["dealer_first_discard_tile"], "N")

    def test_tianhu_terminal_leaves_no_first_round_tianting_to_mark(self):
        # Structural guard: when Tianhu already ended the hand, first_round
        # provenance (and therefore Tianting) must not be present. Full staged
        # opening Tianhu coverage lives in test_confirmed_opening_flow.
        from tests.test_confirmed_opening_flow import staged_game, WIN

        wildcard = WIN.copy()
        wildcard[-1] = GOLD
        for dealer in (0, 1):
            with self.subTest(dealer=dealer):
                game = staged_game(dealer=dealer, hand=wildcard)
                state, _event = game.reveal_opening_candidate(
                    wall_index=game.state.wall.index(GOLD),
                    current_dealer_base=20,
                )
                self.assertEqual(state.terminal_reason, "AUTO_TIANHU")
                self.assertIsNone(state.first_round)
                self.assertEqual(state.rewards[dealer], 40)
                self.assertEqual(state.rewards[1 - dealer], -40)


if __name__ == "__main__":
    unittest.main()
