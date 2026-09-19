import unittest

from huian import (HuContext, HuianEnvironment, HuianGameState, HuianRules,
                   HuianRulesAdapter, RulesConfig, UnknownRuleError, DeadLoopError)
from huian._legacy import env


HAND = ["M1", "M2", "M4", "M5", "M7", "M8", "P1", "P2",
        "P4", "S1", "S2", "S4", "E", "E", "E", "N"]


def scenario(phase="AFTER_DISCARD", hand=None, discard="M3"):
    state = HuianGameState(phase=phase, gold_tile="P9", special_states=["NORMAL", "NORMAL"])
    state.hands[0] = list(HAND if hand is None else hand)
    state.reserved_tiles = ["P9"]  # Explicit fixture accounting, not an opening rule.
    if phase == "AFTER_DISCARD":
        state.discards[1] = [discard]
        state.pending_discard = dict(player=1, tile=discard, river_index=0)
    remaining = env.full_wall()
    for tile in state.physical_tiles():
        remaining.remove(tile)
    for tile in remaining.copy():
        if tile in env.BASE_TILES and tile != "P9" and len(state.hands[1]) < 16:
            state.hands[1].append(tile)
            remaining.remove(tile)
    state.wall = remaining
    return state


def game(state, experimental=False, **kwargs):
    adapter = HuianRulesAdapter(HuianRules(RulesConfig(experimental_no_rob_kong=experimental)))
    result = HuianEnvironment(adapter, **kwargs)
    result.set_state(state)
    return result


def choose(instance, kind):
    return next(a for a in instance.action_report().known_actions if a.type == kind)


class EnvironmentTests(unittest.TestCase):
    def test_chi_transfers_river_tile_and_requires_discard(self):
        instance = game(scenario())
        self.assertIn(env.Action(0, env.ActionType.PASS), instance.legal_actions())
        before = sorted(instance.state.physical_tiles())
        state, event = instance.step(choose(instance, env.ActionType.CHI))
        self.assertEqual(state.discards[1], [])
        self.assertIsNone(state.pending_discard)
        self.assertEqual(state.melds[0][0].tiles, ["M1", "M2", "M3"])
        self.assertEqual(len(state.hands[0]), 14)
        self.assertEqual(state.phase, "AFTER_CHI")
        self.assertEqual(sorted(state.physical_tiles()), before)
        self.assertTrue(all(a.type == env.ActionType.DISCARD for a in instance.legal_actions()))
        after, _ = instance.step(instance.legal_actions()[0])
        self.assertEqual(after.phase, "AFTER_DISCARD")
        self.assertEqual(after.current_player, 1)
        self.assertEqual(len(after.hands[0]), 13)
        self.assertEqual(event["after_hash"], state.state_hash())

    def test_peng_transfers_only_latest_river_copy(self):
        # Move another physical E from wall into the earlier river position.
        # HAND has three E, so use a two-E hand to leave one spare copy.
        state = scenario(hand=HAND[:-2] + ["P6", "N"], discard="E")
        state.wall.remove("E")
        state.discards[1].insert(0, "E")
        state.pending_discard["river_index"] = 1
        instance = game(state)
        after, _ = instance.step(choose(instance, env.ActionType.PENG))
        self.assertEqual(after.discards[1], ["E"])
        self.assertEqual(after.melds[0][0].tiles, ["E"] * 3)
        self.assertEqual(after.phase, "AFTER_PENG")

    def test_ming_and_an_kong_tail_draw_explicit_experiment(self):
        for kind in (env.ActionType.MING_GANG, env.ActionType.AN_GANG):
            if kind == env.ActionType.MING_GANG:
                state = scenario(discard="E")
            else:
                state = scenario("AFTER_DRAW", HAND + ["E"])
            state.wall.remove("P8")
            state.wall.append("P8")
            instance = game(state, experimental=True)
            after, event = instance.step(choose(instance, kind))
            self.assertEqual(len(after.hands[0]), 13)
            self.assertEqual(after.phase, "AFTER_" + kind.value)
            self.assertTrue(event["rules_config"]["experimental_no_rob_kong"])
            action = instance.legal_actions()[0]
            self.assertEqual(action.metadata, {
                "source": "wall_tail", "kong_kind": kind.value
            })
            final, _ = instance.step(action)
            self.assertEqual(final.hands[0][-1], "P8")
            self.assertEqual(len(final.wall), len(state.wall) - 1)
            self.assertEqual(len(final.hands[0]), 14)
            self.assertEqual(final.phase, "AFTER_DRAW")
            self.assertEqual(final.last_action["metadata"]["source"], "wall_tail")
            self.assertEqual(final.last_action["metadata"]["kong_kind"], kind.value)
            self.assertEqual(final.last_action["metadata"]["drawn_tile"], "P8")
            self.assertTrue(HuContext.from_draw_metadata(final.last_action["metadata"]).is_gang_hu)

    def test_big_ming_gang_from_opponent_discard_is_confirmed_unrobbable(self):
        instance = game(scenario(discard="E"))
        report = instance.action_report()
        self.assertNotIn("rob_kong", report.unresolved)
        action = next(a for a in report.known_actions if a.type == env.ActionType.MING_GANG)
        after, _ = instance.step(action)
        self.assertEqual(after.phase, "AFTER_MING_GANG")

    def test_resolved_kong_tail_draw_needs_no_experimental_override(self):
        experimental = game(scenario(discard="E"), experimental=True)
        experimental.step(choose(experimental, env.ActionType.MING_GANG))
        # External verified scenario begins AFTER kong response resolution.
        instance = game(experimental.state)
        self.assertEqual(instance.legal_actions()[0].metadata, {
            "source": "wall_tail", "kong_kind": "MING_GANG"
        })
        instance.step(instance.legal_actions()[0])

    def test_tail_flower_runs_dealer_first_replacement_rounds(self):
        instance = game(scenario(discard="E"), experimental=True)
        instance.step(choose(instance, env.ActionType.MING_GANG))
        after, event = instance.step(instance.legal_actions()[0])  # Full-wall order ends with F8.
        self.assertEqual(after.phase, "AFTER_DRAW")
        self.assertFalse(any(tile in env.FLOWERS for hand in after.hands for tile in hand))
        self.assertIn("F8", after.flowers[0])
        self.assertEqual(len(after.hands[0]), 14)
        self.assertIn("flower_replacements", event)
        self.assertTrue(event["flower_replacements"])

    def test_head_flower_replaces_from_tail_and_audits_event(self):
        state = scenario("NEED_DRAW")
        flower_index = state.wall.index("F1")
        state.wall[0], state.wall[flower_index] = state.wall[flower_index], state.wall[0]
        normal_index = next(i for i, tile in enumerate(state.wall[:-1]) if tile == "M9")
        state.wall[-1], state.wall[normal_index] = state.wall[normal_index], state.wall[-1]
        instance = game(state)
        before_wall = len(state.wall)
        after, event = instance.step(instance.legal_actions()[0])
        self.assertEqual(after.phase, "AFTER_DRAW")
        self.assertEqual(after.flowers[0], ["F1"])
        self.assertEqual(after.hands[0][-1], "M9")
        self.assertEqual(len(after.wall), before_wall - 2)
        self.assertEqual(event["flower_replacements"][0]["player"], 0)
        self.assertEqual(event["flower_replacements"][0]["flowers"], ("F1",))
    def test_head_draw_and_wrong_source_rejected(self):
        instance = game(scenario("NEED_DRAW"))
        expected = instance.state.wall[0]
        before = instance.state.state_hash()
        with self.assertRaises(ValueError):
            instance.step(env.Action(0, env.ActionType.DRAW, metadata={"source": "wall_tail"}))
        self.assertEqual(instance.state.state_hash(), before)
        after, _ = instance.step(instance.legal_actions()[0])
        self.assertEqual(after.hands[0][-1], expected)

    def test_legacy_draw_source_alias_is_logged_canonically(self):
        instance = game(scenario("NEED_DRAW"))
        after, event = instance.step(
            env.Action(0, env.ActionType.DRAW, metadata={"source": "head"})
        )
        self.assertEqual(event["action"]["metadata"]["source"], "wall_head")
        self.assertEqual(event["action"]["metadata"]["drawn_tile"], after.hands[0][-1])

    def test_atomic_post_validation_failure(self):
        class Broken(HuianEnvironment):
            @staticmethod
            def _apply(state, action):
                HuianEnvironment._apply(state, action)
                state.wall.pop()  # Inject tile loss AFTER mutation.
        instance = Broken()
        instance.set_state(scenario("NEED_DRAW"))
        token = instance.checkpoint()
        before = instance.state.state_hash()
        with self.assertRaises(ValueError):
            instance.step(instance.legal_actions()[0])
        self.assertEqual(instance.state.state_hash(), before)
        self.assertEqual(instance.events, [])
        self.assertEqual(instance.rollback(token).state_hash(), before)

    def test_set_state_failure_preserves_existing_history(self):
        instance = game(scenario("NEED_DRAW"))
        instance.step(instance.legal_actions()[0])
        before, events = instance.state.state_hash(), instance.events
        invalid = instance.state
        invalid.wall.append("M1")
        with self.assertRaises(ValueError):
            instance.set_state(invalid)
        self.assertEqual(instance.state.state_hash(), before)
        self.assertEqual(instance.events, events)

    def test_missing_tile_bad_pending_and_hand_size_rejected(self):
        for mutate in (
            lambda s: s.wall.pop(),
            lambda s: s.pending_discard.update(tile="P9"),
            lambda s: s.pending_discard.update(player=0),
            lambda s: s.pending_discard.update(river_index=-1),
            lambda s: s.wall.append(s.hands[0].pop()),
            lambda s: s.special_states.clear(),
            lambda s: setattr(s, "pending_hu", {
                "winner": 0, "source": "self_draw", "winning_tile": "E",
                "kong_kind": None, "discard_player": None, "river_index": None,
            }),
        ):
            state = scenario()
            mutate(state)
            with self.assertRaises(ValueError):
                game(state)

    def test_gold_and_special_history_block_claims(self):
        for special in ("UNKNOWN", "YOUJIN", "DOUBLE_YOU", "TRIPLE_YOU"):
            state = scenario()
            state.special_states[1] = special
            instance = game(state)
            self.assertFalse(instance.action_report().known_actions)
            with self.assertRaises(UnknownRuleError):
                instance.legal_actions()

    def test_gold_in_acting_hand_blocks_without_using_wildcard_in_chi(self):
        state = scenario(hand=["P9"] + HAND[1:])
        instance = game(state)
        self.assertFalse(instance.action_report().known_actions)
        with self.assertRaises(UnknownRuleError):
            instance.legal_actions()

    def test_sanjindao_pass_closes_current_prompt_but_later_draw_reopens(self):
        state = scenario("AFTER_DRAW", hand=["P9"] * 3 + HAND[2:])
        state.last_action = env.Action(
            0, env.ActionType.DRAW,
            metadata={"source": "wall_head", "drawn_tile": "P9"},
        ).to_dict()
        instance = game(state)
        report = instance.action_report()
        self.assertFalse(report.unresolved)
        self.assertEqual(report.known_actions[0].metadata.get("special"), "SANJINDAO")
        self.assertTrue(any(
            action.type == env.ActionType.PASS_QIANGJIN
            and action.metadata.get("continue_play")
            for action in report.known_actions
        ))

        # PASS closes this exact decision node; it must not immediately loop.
        instance.step(next(
            a for a in report.known_actions if a.type == env.ActionType.PASS_QIANGJIN
        ))
        self.assertFalse(any(
            a.metadata.get("special") == "SANJINDAO"
            for a in instance.action_report().known_actions
        ))

        # match_evidence_002/player clarification: a later own draw while the
        # same three golds remain can offer Sanjindao again.
        later_state = scenario("AFTER_DRAW", hand=["P9"] * 3 + HAND[2:])
        later_state.last_action = env.Action(
            0, env.ActionType.DRAW,
            metadata={"source": "wall_head", "drawn_tile": HAND[2]},
        ).to_dict()
        later = game(later_state).action_report()
        self.assertTrue(any(
            a.metadata.get("special") == "SANJINDAO"
            for a in later.known_actions
        ))

    def test_sanjindao_can_reopen_more_than_once_after_separate_passes(self):
        def later_report(draw_tile):
            state = scenario("AFTER_DRAW", hand=["P9"] * 3 + HAND[2:])
            state.last_action = env.Action(
                0, env.ActionType.DRAW,
                metadata={"source": "wall_head", "drawn_tile": draw_tile},
            ).to_dict()
            return game(state).action_report()

        first = later_report(HAND[2])
        self.assertTrue(any(
            a.metadata.get("special") == "SANJINDAO"
            for a in first.known_actions
        ))

        # A later, separate own-draw node is still eligible even though an
        # earlier Sanjindao prompt was passed. match_evidence_002 shows repeated
        # PASS nodes while the same three gold tiles remain visible.
        second = later_report(HAND[3])
        self.assertTrue(any(
            a.metadata.get("special") == "SANJINDAO"
            for a in second.known_actions
        ))

    def test_eight_flower_special_declares_and_project_x2_settles(self):
        state = scenario("AFTER_DRAW", hand=HAND + ["M9"])
        for flower in env.FLOWERS:
            state.wall.remove(flower)
            state.flowers[0].append(flower)
        state.last_action = env.Action(
            0, env.ActionType.DRAW,
            metadata={"source": "wall_head", "drawn_tile": "F8"},
        ).to_dict()
        instance = game(state)
        actions = instance.legal_actions()
        declare = next(
            a for a in actions if a.metadata.get("special") == "EIGHT_FLOWER_YOU"
        )
        self.assertEqual(declare.metadata["multiplier"], 2)
        self.assertTrue(declare.metadata["project_rule"])
        instance.step(declare)
        self.assertEqual(instance.state.phase, "EIGHT_FLOWER_YOU_DECLARED")
        terminal, event = instance.finalize_eight_flower_outcome(
            current_dealer_base=5, winner_fan=8)
        self.assertTrue(terminal.terminal)
        self.assertEqual(terminal.rewards, [26, -26])
        self.assertEqual(terminal.terminal_reason, "PROJECT_EIGHT_FLOWER_YOU")
        self.assertEqual(event["action"]["metadata"]["multiplier"], 2)
        self.assertEqual(event["action"]["metadata"]["evidence_status"], "WORKING")

    def test_eight_flower_pass_closes_window_and_keeps_eight_flowers(self):
        state = scenario("AFTER_DRAW", hand=HAND + ["M9"])
        for flower in env.FLOWERS:
            state.wall.remove(flower)
            state.flowers[0].append(flower)
        state.last_action = env.Action(
            0, env.ActionType.DRAW,
            metadata={"source": "wall_head", "drawn_tile": "F8"},
        ).to_dict()
        instance = game(state)
        pass_action = next(
            a for a in instance.legal_actions()
            if a.type == env.ActionType.PASS_QIANGJIN
        )
        after, _ = instance.step(pass_action)
        self.assertEqual(len(after.flowers[0]), 8)
        self.assertTrue(all(
            a.type == env.ActionType.DISCARD for a in instance.legal_actions()
        ))

    def test_fifth_copy_rejected_even_when_total_remains_144(self):
        state = scenario()
        replacement = next(i for i, tile in enumerate(state.wall) if tile != "E")
        state.wall[replacement] = "E"
        self.assertEqual(len(state.physical_tiles()), 144)
        with self.assertRaises(ValueError):
            game(state)

    def test_ordinary_win_is_explicitly_blocked_pending_settlement(self):
        hand = ["M1", "M1", "M2", "M3", "M4", "M5", "M6", "M7",
                "P1", "P2", "P3", "S1", "S2", "S3", "E", "E", "E"]
        instance = game(scenario("AFTER_DRAW", hand))
        self.assertFalse(instance.action_report().known_actions)
        self.assertIn("win_declaration_and_settlement", instance.action_report().unresolved)

    def test_draw_hu_is_declared_then_observed_zimo_settles(self):
        complete = ["M1", "M1", "M2", "M3", "M4", "M5", "M6", "M7",
                    "P1", "P2", "P3", "S1", "S2", "S3", "E", "E", "E"]
        state = scenario("NEED_DRAW", complete[:-1])
        index = state.wall.index("E")
        state.wall[0], state.wall[index] = state.wall[index], state.wall[0]
        instance = game(state)
        instance.step(instance.legal_actions()[0])
        report = instance.action_report()
        hu = next(action for action in report.known_actions
                  if action.type == env.ActionType.HU)
        self.assertEqual(hu.tile, "E")
        self.assertEqual(hu.metadata, {"win_source": "self_draw", "kong_kind": None})
        self.assertIn("self_draw_decline", report.unresolved)
        declared, _ = instance.step(hu)
        self.assertEqual(declared.phase, "HU_DECLARED")
        self.assertEqual(declared.pending_hu, {
            "winner": 0, "source": "self_draw", "winning_tile": "E",
            "kong_kind": None, "discard_player": None, "river_index": None,
        })
        with self.assertRaises(UnknownRuleError):
            instance.legal_actions()
        terminal, event = instance.finalize_observed_outcome(
            winner=0, current_dealer_base=10, winner_fan=1, win_type="ZIMO"
        )
        self.assertTrue(terminal.terminal)
        self.assertIsNone(terminal.pending_hu)
        self.assertEqual(event["action"]["metadata"]["hu_declaration"]["source"],
                         "self_draw")

    def test_discard_hu_keeps_source_tile_in_river_until_observed_settlement(self):
        complete = ["M1", "M1", "M2", "M3", "M4", "M5", "M6", "M7",
                    "P1", "P2", "P3", "S1", "S2", "S3", "E", "E", "E"]
        instance = game(scenario("AFTER_DISCARD", complete[:-1], discard="E"))
        hu = next(action for action in instance.action_report().known_actions
                  if action.type == env.ActionType.HU)
        declared, _ = instance.step(hu)
        self.assertEqual(declared.phase, "HU_DECLARED")
        self.assertEqual(declared.discards[1], ["E"])
        self.assertIsNone(declared.pending_discard)
        self.assertEqual(declared.pending_hu["discard_player"], 1)
        self.assertEqual(declared.pending_hu["river_index"], 0)
        with self.assertRaises(ValueError):
            instance.finalize_observed_outcome(
                winner=0, current_dealer_base=10, winner_fan=1, win_type="ZIMO"
            )
        terminal, _ = instance.finalize_observed_outcome(
            winner=0, current_dealer_base=10, winner_fan=1, win_type="PINGHU"
        )
        self.assertEqual(terminal.rewards, [11, -11])

    def test_automatic_zimo_settlement_uses_fan_aggregator(self):
        complete = ["M1", "M1", "M2", "M3", "M4", "M5", "M6", "M7",
                    "P1", "P2", "P3", "S1", "S2", "S3", "E", "E", "E"]
        state = scenario("NEED_DRAW", complete[:-1])
        index = state.wall.index("E")
        state.wall[0], state.wall[index] = state.wall[index], state.wall[0]
        instance = game(state)
        instance.step(instance.legal_actions()[0])
        hu = next(action for action in instance.action_report().known_actions
                  if action.type == env.ActionType.HU)
        instance.step(hu)

        terminal, event = instance.finalize_ordinary_outcome(
            current_dealer_base=10)
        self.assertEqual(terminal.terminal_reason, "AUTO_ZIMO")
        self.assertEqual(terminal.rewards, [24, -24])
        metadata = event["action"]["metadata"]
        self.assertEqual(metadata["winner_fan"], 2)
        self.assertEqual(metadata["multiplier"], 2)
        self.assertEqual(metadata["source"], "automatic_fan")
        self.assertEqual(
            [(item["category"], item["fan"]) for item in metadata["fan_components"]],
            [("concealed_triplet", 2)],
        )

    def test_automatic_pinghu_does_not_count_discard_completed_triplet(self):
        complete = ["M1", "M1", "M2", "M3", "M4", "M5", "M6", "M7",
                    "P1", "P2", "P3", "S1", "S2", "S3", "E", "E", "E"]
        instance = game(scenario("AFTER_DISCARD", complete[:-1], discard="E"))
        hu = next(action for action in instance.action_report().known_actions
                  if action.type == env.ActionType.HU)
        instance.step(hu)

        terminal, event = instance.finalize_ordinary_outcome(
            current_dealer_base=10)
        self.assertEqual(terminal.terminal_reason, "AUTO_PINGHU")
        self.assertEqual(terminal.rewards, [10, -10])
        metadata = event["action"]["metadata"]
        self.assertEqual(metadata["winner_fan"], 0)
        self.assertEqual(metadata["multiplier"], 1)
        self.assertEqual(metadata["fan_components"], [])

    def test_automatic_settlement_uses_maximum_fan_decomposition(self):
        hand = [
            "M1", "M1", "M1",
            "M2", "M2", "M2",
            "M3", "M3", "M3",
            "M4", "M4", "M4",
            "M5", "M5", "M5",
            "M6", "M6",
        ]
        state = scenario("HU_DECLARED", hand)
        state.pending_hu = {
            "winner": 0, "source": "self_draw", "winning_tile": "M6",
            "kong_kind": None, "discard_player": None, "river_index": None,
        }
        instance = game(state)
        terminal, event = instance.finalize_ordinary_outcome(
            current_dealer_base=10)
        metadata = event["action"]["metadata"]
        self.assertTrue(terminal.terminal)
        self.assertEqual(metadata["fan_selection_policy"], "MAX_TOTAL_FAN")
        self.assertEqual(
            metadata["winner_fan"], max(metadata["fan_candidate_fans"]))
        self.assertEqual(
            terminal.rewards,
            [2 * (10 + metadata["winner_fan"]),
             -2 * (10 + metadata["winner_fan"])],
        )

    def test_flower_replacement_records_effective_self_draw_for_hu(self):
        complete = ["M1", "M1", "M2", "M3", "M4", "M5", "M6", "M7",
                    "P1", "P2", "P3", "S1", "S2", "S3", "E", "E", "E"]
        state = scenario("NEED_DRAW", complete[:-1])
        flower_index = state.wall.index("F1")
        state.wall[0], state.wall[flower_index] = state.wall[flower_index], state.wall[0]
        gold_index = state.wall.index("E")
        state.wall[-1], state.wall[gold_index] = state.wall[gold_index], state.wall[-1]
        instance = game(state)
        _, event = instance.step(instance.legal_actions()[0])
        self.assertEqual(event["action"]["metadata"]["drawn_tile"], "F1")
        self.assertEqual(event["action"]["metadata"]["effective_drawn_tile"], "E")
        hu = next(action for action in instance.action_report().known_actions
                  if action.type == env.ActionType.HU)
        self.assertEqual(hu.tile, "E")

    def test_kong_tail_hu_declaration_preserves_kind_and_blocks_scoring(self):
        state = HuianGameState(phase="AFTER_AN_GANG", gold_tile="P9",
                               special_states=["NORMAL", "NORMAL"])
        state.hands[0] = ["M1", "M1", "M2", "M3", "M4", "M5", "M6",
                          "M7", "P1", "P2", "P3", "E", "E"]
        state.melds[0] = [env.Meld("AN_GANG", ["S9"] * 4, None)]
        state.reserved_tiles = ["P9"]
        remaining = env.full_wall()
        for tile in state.physical_tiles():
            remaining.remove(tile)
        for tile in remaining.copy():
            if tile in env.BASE_TILES and tile != "P9" and len(state.hands[1]) < 16:
                state.hands[1].append(tile)
                remaining.remove(tile)
        index = remaining.index("E")
        remaining[-1], remaining[index] = remaining[index], remaining[-1]
        state.wall = remaining
        instance = game(state)
        instance.step(instance.legal_actions()[0])
        hu = next(action for action in instance.action_report().known_actions
                  if action.type == env.ActionType.HU)
        self.assertEqual(hu.metadata, {
            "win_source": "kong_tail_draw", "kong_kind": "AN_GANG",
        })
        declared, _ = instance.step(hu)
        self.assertEqual(declared.pending_hu["kong_kind"], "AN_GANG")
        before = declared.state_hash()
        with self.assertRaises(UnknownRuleError):
            instance.finalize_observed_outcome(
                winner=0, current_dealer_base=10, winner_fan=1, win_type="ZIMO"
            )
        self.assertEqual(instance.state.state_hash(), before)

    def test_pass_known_and_startup_remains_unknown(self):
        instance = game(scenario())
        instance.step(env.Action(0, env.ActionType.PASS))
        self.assertEqual(instance.state.phase, "NEED_DRAW")
        instance.reset(seed=42)
        with self.assertRaises(UnknownRuleError):
            instance.legal_actions()

    def test_boundary_import_and_invalid_short_wall(self):
        for count in (0, 15, 16):
            state = scenario("NEED_DRAW")
            state.reserved_tiles.extend(state.wall[count:])
            state.wall = state.wall[:count]
            if count < 16:
                with self.assertRaises(ValueError):
                    game(state)
            else:
                instance = game(state)
                self.assertTrue(instance.is_terminal())
                self.assertEqual(instance.get_reward(), [0, 0])
                self.assertEqual(instance.state.wall_remaining(), 16)

    def test_no_legality_bypass_and_no_caller_mutation(self):
        instance = game(scenario("NEED_DRAW"))
        action = instance.legal_actions()[0]
        with self.assertRaises(ValueError):
            instance.step(action, strict=False)
        result, event = instance.step(action)
        expected = instance.state.state_hash()
        result.wall.clear()
        action.metadata["source"] = "wall_tail"
        event["action"]["metadata"]["source"] = "wall_tail"
        instance.events.clear()
        self.assertEqual(instance.state.state_hash(), expected)
        self.assertEqual(instance.events[0]["action"]["metadata"]["source"], "wall_head")

    def test_seed_clone_rollback_and_replayed_actions(self):
        a, b = HuianEnvironment(), HuianEnvironment()
        self.assertEqual(a.reset(seed=71).state_hash(), b.reset(seed=71).state_hash())
        a.set_state(scenario())
        token = a.checkpoint()
        b = a.clone()
        action = choose(a, env.ActionType.CHI)
        a.step(action)
        action2 = a.legal_actions()[0]
        a.step(action2)
        for event in a.events:
            b.step(env.Action.from_dict(event["action"]))
        self.assertEqual(a.events, b.events)
        a.rollback(token)
        a.step(action)
        a.step(action2)
        self.assertEqual(a.events, b.events)
        with self.assertRaises(ValueError):
            a.rollback(token)
        fresh = a.checkpoint()
        a.reset(seed=1)
        a.checkpoint()
        with self.assertRaises(ValueError):
            a.rollback(fresh)

    def test_loop_detection_ignores_turn_counter(self):
        class NoProgress(HuianEnvironment):
            @staticmethod
            def _apply(state, action):
                pass
        instance = NoProgress()
        instance.set_state(scenario("NEED_DRAW"))
        before = instance.state.state_hash()
        with self.assertRaises(DeadLoopError):
            instance.step(instance.legal_actions()[0])
        self.assertEqual(instance.state.state_hash(), before)
        self.assertEqual(instance.events, [])

    def test_step_limit_and_zero_sum_terminal(self):
        instance = game(scenario(), max_steps=1)
        instance.step(choose(instance, env.ActionType.CHI))
        with self.assertRaises(DeadLoopError):
            instance.step(instance.legal_actions()[0])
        self.assertFalse(instance.is_terminal())
        state = instance.state
        state.phase, state.terminal, state.rewards = "TERMINAL", True, [44, -44]
        terminal = game(state)
        self.assertEqual(terminal.legal_actions(), [])
        self.assertEqual(terminal.get_reward(), [44, -44])
        state.rewards = [44, 0]
        with self.assertRaises(ValueError):
            terminal.set_state(state)


if __name__ == "__main__":
    unittest.main()
