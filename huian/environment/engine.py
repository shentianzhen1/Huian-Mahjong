"""Atomic deterministic transitions for the supported M2 subset."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import random

from huian._legacy import env
from huian.rules import HuianRulesAdapter
from huian.rules.context import (DrawSource, HuContext, WinSource, YoujinStage,
                                 youjin_progression_rule)
from .state import HuianGameState
from .opening import HuianOpeningPlugin
from .flowers import replace_flowers
from huian.rules.observed_settlement import HuianObservedSettlementPlugin


class DeadLoopError(RuntimeError):
    pass


class HuianEnvironment:
    def __init__(self, rules=None, opening=None, max_steps=10000, settlement=None):
        if type(max_steps) is not int or max_steps <= 0:
            raise ValueError("max_steps must be a positive integer")
        self.rules = rules if rules is not None else HuianRulesAdapter()
        self.opening = opening if opening is not None else HuianOpeningPlugin()
        self.settlement = settlement if settlement is not None else HuianObservedSettlementPlugin()
        self.max_steps = max_steps
        self._state = None
        self._events = []
        self._snapshots = []
        self._next_token = 0
        self._seen = set()

    @property
    def state(self):
        return deepcopy(self._state)

    @property
    def events(self):
        return deepcopy(self._events)

    def _require_state(self):
        if self._state is None:
            raise RuntimeError("Call reset or set_state first")

    @staticmethod
    def _position(state):
        data = state.canonical_dict()
        data.pop("turn_index")
        data.pop("last_action")
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def set_state(self, state):
        if not isinstance(state, HuianGameState):
            raise TypeError("Use HuianGameState with explicit phase/history and all 144 tiles")
        candidate = deepcopy(state)
        self.rules.validate_state(candidate)
        self._resolve_wall_draw(candidate)
        self.rules.validate_state(candidate)
        self._state = candidate
        self._events = []
        self._snapshots = []
        self._seen = {self._position(candidate)}
        return self.state

    def reset(self, wall=None, seed=None, dealer=0):
        tiles = env.full_wall() if wall is None else list(wall)
        if wall is None:
            random.Random(seed).shuffle(tiles)
        return self.set_state(HuianGameState(wall=tiles, dealer=dealer,
                                           current_player=dealer, phase="READY"))

    def begin_opening(self, dice_total):
        """Apply opening and stop for the current-player special check.

        The opened gold indicator is a physical tile but is not drawable. It is
        moved into reserved_tiles so all 144 tiles remain accounted for while
        only the other three copies can enter playable zones.
        """
        self._require_state()
        if self._state.phase != "READY":
            raise ValueError("Opening can begin only from READY")
        before = self._state.state_hash()
        opening = self.opening.plan_opening(self._state.wall, self._state.dealer, dice_total)
        candidate = deepcopy(self._state)
        candidate.hands = [list(zone) for zone in opening.hands]
        candidate.flowers = [list(zone) for zone in opening.flowers]
        candidate.wall = list(opening.wall)
        candidate.gold_tile = opening.gold_indicator.tile
        candidate.reserved_tiles = list(candidate.reserved_tiles)
        candidate.reserved_tiles.append(opening.gold_indicator.tile)
        candidate.current_player = candidate.dealer
        candidate.phase = "OPENING_QIANGJIN_CHECK"
        self.rules.validate_state(candidate)
        self._state = candidate
        self._events = [{
            "seq": 0,
            "action": {"player": candidate.dealer, "type": "OPEN_GOLD",
                       "tile": candidate.gold_tile, "tiles": [],
                       "metadata": {"dice_total": dice_total,
                                    "indicator_wall_index": opening.gold_indicator.wall_index,
                                    "indicator_removed_from_drawable_wall": True,
                                    "skipped_flowers": list(opening.gold_indicator.skipped_flowers)}},
            "before_hash": before,
            "after_hash": candidate.state_hash(),
            "wall_remaining": candidate.wall_remaining(),
            "current_player_after": candidate.current_player,
            "phase_after": candidate.phase,
        }]
        self._snapshots = []
        self._seen = {self._position(candidate)}
        return self.state
    def begin_normal_hand(self, dice_total):
        """Simulation-only opening bypass; never resolves or enables 抢金."""
        if not self.rules.rules.config.simulation_only_normal_hand:
            raise ValueError("Normal-hand opening requires simulation_only_normal_hand")
        self.begin_opening(dice_total)
        candidate = deepcopy(self._state)
        candidate.phase = "AFTER_DRAW"
        candidate.special_states = ["NORMAL", "NORMAL"]
        self.rules.validate_state(candidate)
        self._state = candidate
        self._events.append({"seq": len(self._events), "action": {"player": candidate.dealer,
            "type": "SIMULATION_SKIP_QIANGJIN", "tile": None, "tiles": [],
            "metadata": {"simulation_only": True}},
            "before_hash": self._events[-1]["after_hash"], "after_hash": candidate.state_hash(),
            "wall_remaining": candidate.wall_remaining(), "current_player_after": candidate.current_player,
            "phase_after": candidate.phase})
        self._seen.add(self._position(candidate))
        return self.state
    def finalize_simulation_only_outcome(self):
        """Close an already-declared ordinary Hu with non-real scoring units."""
        self._require_state()
        if not self.rules.rules.config.simulation_only_normal_hand:
            raise ValueError("Simulation settlement requires simulation_only_normal_hand")
        if self._state.phase not in ("HU_DECLARED", "ROB_KONG_HU_DECLARED"):
            raise ValueError("Simulation settlement requires HU_DECLARED")
        self.rules.validate_state(self._state)
        before = self._state.state_hash()
        pending = deepcopy(self._state.pending_hu)
        if pending["source"] == WinSource.ROB_KONG.value:
            from huian.rules.config import UnknownRuleError
            raise UnknownRuleError("ROB_KONG_SCORING_UNKNOWN")
        if pending["source"] == WinSource.KONG_TAIL_DRAW.value:
            from huian.rules.config import UnknownRuleError
            raise UnknownRuleError("GANG_HU_SCORING_UNKNOWN")
        winner = pending["winner"]
        multiplier = 1 if pending["source"] == WinSource.DISCARD.value else 2
        candidate = deepcopy(self._state)
        candidate.rewards = [multiplier if winner == 0 else -multiplier,
                             -multiplier if winner == 0 else multiplier]
        candidate.phase, candidate.terminal = "TERMINAL", True
        candidate.terminal_reason = "SIMULATION_" + ("PINGHU" if multiplier == 1 else "ZIMO")
        candidate.pending_discard = candidate.pending_hu = None
        self.rules.validate_state(candidate)
        self._state = candidate
        self._events.append({"seq": len(self._events), "action": {"player": winner,
            "type": "END_HAND", "tile": None, "tiles": [], "metadata": {
                "source": "simulation_only", "simulation_only": True,
                "win_type": "PINGHU" if multiplier == 1 else "ZIMO",
                "unit_base": 1, "multiplier": multiplier,
                "hu_declaration": pending, "rewards": list(candidate.rewards)}},
            "before_hash": before, "after_hash": candidate.state_hash(), "wall_remaining": candidate.wall_remaining(),
            "current_player_after": candidate.current_player, "phase_after": candidate.phase})
        self._seen.add(self._position(candidate))
        return self.state
    def finalize_ordinary_outcome(self, *, current_dealer_base):
        """Automatically fan-count and settle a declared ordinary Pinghu/Zimo.

        This real-scoring path derives winner fan from the current audited
        state instead of accepting caller-supplied fan. Completed kongs affect
        winner fan through FanAggregator only; there is no independent kong fee.
        """
        self._require_state()
        if self._state.terminal:
            raise ValueError("Hand is already terminal")
        if self._state.phase != "HU_DECLARED" or not isinstance(self._state.pending_hu, dict):
            raise ValueError("Automatic ordinary settlement requires HU_DECLARED")

        declaration = deepcopy(self._state.pending_hu)
        source = WinSource(declaration["source"])
        if source == WinSource.ROB_KONG:
            from huian.rules.config import UnknownRuleError
            raise UnknownRuleError("ROB_KONG_SCORING_UNKNOWN")
        if source == WinSource.KONG_TAIL_DRAW:
            from huian.rules.config import UnknownRuleError
            raise UnknownRuleError("GANG_HU_SCORING_UNKNOWN")
        if source not in (WinSource.DISCARD, WinSource.SELF_DRAW):
            from huian.rules.config import UnknownRuleError
            raise UnknownRuleError("win_declaration_and_settlement")

        winner = declaration["winner"]
        winning_tile = declaration["winning_tile"]
        hand = list(self._state.hands[winner])
        if source == WinSource.DISCARD:
            # The winning discard remains in the source river for physical-tile
            # accounting; add a virtual copy only for structural/fan analysis.
            hand.append(winning_tile)

        context = HuContext(source, winning_tile=winning_tile)
        hu_result = self.rules.rules.analyze_hu(
            hand,
            self._state.gold_tile,
            open_melds=len(self._state.melds[winner]),
            win_context=context,
        )
        if not hu_result.legal:
            raise ValueError("Declared ordinary Hu no longer passes structural analysis")

        fan_result = self.rules.rules.aggregate_fan(
            hand,
            self._state.melds[winner],
            self._state.flowers[winner],
            self._state.gold_tile,
            hu_result=hu_result,
        )
        if not fan_result.complete:
            from huian.rules.config import UnknownRuleError
            raise UnknownRuleError(*fan_result.unresolved)

        win_type = "PINGHU" if source == WinSource.DISCARD else "ZIMO"
        result = self.settlement.settle(
            winner=winner,
            current_dealer_base=current_dealer_base,
            winner_fan=fan_result.fan,
            win_type=win_type,
        )

        before = self._state.state_hash()
        candidate = deepcopy(self._state)
        candidate.rewards = list(result.rewards)
        candidate.phase = "TERMINAL"
        candidate.terminal = True
        candidate.terminal_reason = "AUTO_" + result.win_type
        candidate.pending_discard = None
        candidate.pending_hu = None
        self.rules.validate_state(candidate)

        fan_components = [{
            "category": component.category,
            "fan": component.fan,
            "detail": component.detail,
            "status": component.status.value,
            "evidence": component.evidence,
        } for component in fan_result.components]
        metadata = {
            "source": "automatic_fan",
            "win_type": result.win_type,
            "current_dealer_base": current_dealer_base,
            "winner_fan": fan_result.fan,
            "multiplier": result.multiplier,
            "fan_components": fan_components,
            "fan_candidate_fans": list(fan_result.candidate_fans),
            "fan_decomposition_count": fan_result.decomposition_count,
            "fan_selected_decomposition_index": fan_result.selected_decomposition_index,
            "fan_selection_policy": fan_result.selection_policy,
            "hu_declaration": declaration,
            "rewards": list(result.rewards),
        }
        event = {
            "seq": len(self._events),
            "action": {
                "player": winner, "type": "END_HAND", "tile": None, "tiles": [],
                "metadata": metadata,
            },
            "before_hash": before,
            "after_hash": candidate.state_hash(),
            "wall_remaining": candidate.wall_remaining(),
            "current_player_after": candidate.current_player,
            "phase_after": candidate.phase,
        }
        self._state = candidate
        self._events.append(event)
        self._seen.add(self._position(candidate))
        return self.state, deepcopy(event)

    def finalize_eight_flower_outcome(
            self, *, current_dealer_base, winner_fan=None):
        """Settle the project Eight-Flower-You working rule.

        Working rule chosen 2026-09-20:
        - fixed special fan = 16;
        - Hu multiplier = x1 (no extra multiplier);
        - do not stack the ordinary eight-flower +8, gold fan, meld fan, kong fan,
          or other additive fan on top of the special 16.
        - PASS is separate: if the player declines Eight-Flower-You, the eight
          flowers remain ordinary +8 fan for a later non-Eight-Flower result.

        winner_fan is accepted only as a compatibility guard. Supplying a
        value other than 16 is rejected so callers cannot accidentally re-add
        ordinary flower fan or other fan components.
        """
        self._require_state()
        if self._state.terminal:
            raise ValueError("Hand is already terminal")
        if (self._state.phase != "EIGHT_FLOWER_YOU_DECLARED"
                or not isinstance(self._state.pending_hu, dict)):
            raise ValueError("Eight-flower settlement requires its declaration phase")
        if type(current_dealer_base) is not int or current_dealer_base < 0:
            raise ValueError("current_dealer_base must be a nonnegative integer")

        declaration = deepcopy(self._state.pending_hu)
        winner = declaration["winner"]
        fixed_fan = declaration["fixed_fan"]
        multiplier = declaration["multiplier"]
        if (fixed_fan != 16 or multiplier != 1
                or declaration.get("project_rule") is not True):
            raise ValueError(
                "Eight-flower declaration must use fixed 16 fan with no extra multiplier"
            )
        if winner_fan is not None and winner_fan != fixed_fan:
            raise ValueError(
                "Eight-Flower-You fan is fixed at 16; ordinary/additional fan must not stack"
            )

        net = (current_dealer_base + fixed_fan) * multiplier
        rewards = [net, -net] if winner == 0 else [-net, net]

        before = self._state.state_hash()
        candidate = deepcopy(self._state)
        candidate.rewards = rewards
        candidate.phase = "TERMINAL"
        candidate.terminal = True
        candidate.terminal_reason = "PROJECT_EIGHT_FLOWER_YOU"
        candidate.pending_hu = None
        candidate.pending_discard = None
        self.rules.validate_state(candidate)

        event = {
            "seq": len(self._events),
            "action": {
                "player": winner, "type": "END_HAND", "tile": None, "tiles": [],
                "metadata": {
                    "source": "project_working_rule",
                    "special": "EIGHT_FLOWER_YOU",
                    "project_rule": True,
                    "evidence_status": "WORKING",
                    "current_dealer_base": current_dealer_base,
                    "winner_fan": fixed_fan,
                    "fixed_fan": fixed_fan,
                    "multiplier": multiplier,
                    "fan_policy": "FIXED_SPECIAL_FAN_NO_STACKING",
                    "hu_declaration": declaration,
                    "rewards": list(rewards),
                },
            },
            "before_hash": before,
            "after_hash": candidate.state_hash(),
            "wall_remaining": candidate.wall_remaining(),
            "current_player_after": candidate.current_player,
            "phase_after": candidate.phase,
        }
        self._state = candidate
        self._events.append(event)
        self._seen.add(self._position(candidate))
        return self.state, deepcopy(event)

    def finalize_observed_special_outcome(
            self, *, winner, rewards, evidence_id, observed_fields=None):
        """Record a directly observed special settlement without inferring a formula.

        This evidence-ingestion API accepts the net score transfer visible in a
        replay/screenshot. It does not derive rewards from a multiplier, fan,
        dealer base, or payer hypothesis. Formula inference remains a separate
        evidence task.
        """
        from huian.rules.special_outcomes import (
            special_outcome_for_phase, special_outcome_for_source)

        self._require_state()
        if self._state.terminal:
            raise ValueError("Hand is already terminal")
        if type(winner) is not int or winner not in (0, 1):
            raise ValueError("winner must be seat 0 or 1")
        if (not isinstance(rewards, (list, tuple)) or len(rewards) != 2
                or any(type(value) is not int for value in rewards)):
            raise ValueError("rewards must be two integer net scores")
        rewards = tuple(rewards)
        if sum(rewards) != 0:
            raise ValueError("Observed two-player settlement must be zero-sum")
        if rewards[winner] <= 0 or rewards[1 - winner] >= 0:
            raise ValueError("Observed winner must have the positive net reward")
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            raise ValueError("evidence_id must be a non-empty string")
        if observed_fields is None:
            observed_fields = {}
        if not isinstance(observed_fields, dict):
            raise ValueError("observed_fields must be a dict")

        declaration = deepcopy(self._state.pending_hu)
        if not isinstance(declaration, dict) or declaration.get("winner") != winner:
            raise ValueError("Observed special outcome requires its matching declaration")
        phase_profile = special_outcome_for_phase(self._state.phase)
        source_profile = special_outcome_for_source(declaration.get("source"))
        if phase_profile.key != source_profile.key:
            raise ValueError("Special declaration phase/source profile mismatch")
        profile = phase_profile

        before = self._state.state_hash()
        candidate = deepcopy(self._state)
        candidate.rewards = list(rewards)
        candidate.phase = "TERMINAL"
        candidate.terminal = True
        candidate.terminal_reason = "OBSERVED_SPECIAL"
        candidate.pending_discard = None
        candidate.pending_hu = None
        candidate.pending_kong = None
        self.rules.validate_state(candidate)

        metadata = {
            "source": "observed_special",
            "special": profile.key,
            "evidence_id": evidence_id.strip(),
            "rewards": list(rewards),
            "observed_fields": deepcopy(observed_fields),
            "registered_multiplier": profile.multiplier,
            "registered_multiplier_evidence": profile.multiplier_status.value,
            "registered_settlement_rule_id": profile.settlement_rule_id,
            "hu_declaration": declaration,
        }
        event = {
            "seq": len(self._events),
            "action": {
                "player": winner, "type": "END_HAND", "tile": None, "tiles": [],
                "metadata": metadata,
            },
            "before_hash": before,
            "after_hash": candidate.state_hash(),
            "wall_remaining": candidate.wall_remaining(),
            "current_player_after": candidate.current_player,
            "phase_after": candidate.phase,
        }
        self._state = candidate
        self._events.append(event)
        self._seen.add(self._position(candidate))
        return self.state, deepcopy(event)

    def finalize_observed_outcome(self, *, winner, current_dealer_base, winner_fan, win_type):
        """Record an externally verified ordinary outcome without inferring it.

        This API is for replay/Vision-confirmed outcomes.  It deliberately does
        not decide whether a hand may Hu, aggregate fan, or settle special wins.
        """
        self._require_state()
        if self._state.terminal:
            raise ValueError("Hand is already terminal")
        declaration = deepcopy(self._state.pending_hu)
        if declaration is not None:
            if winner != declaration["winner"]:
                raise ValueError("Observed winner disagrees with the Hu declaration")
            try:
                source = WinSource(declaration["source"])
            except (TypeError, ValueError):
                from huian.rules.config import UnknownRuleError
                from huian.rules.special_outcomes import special_outcome_for_source
                profile = special_outcome_for_source(declaration.get("source"))
                if profile.settlement_rule_id is None:
                    raise
                raise UnknownRuleError(profile.settlement_rule_id)
            if source == WinSource.ROB_KONG:
                from huian.rules.config import UnknownRuleError
                raise UnknownRuleError("ROB_KONG_SCORING_UNKNOWN")
            if source == WinSource.KONG_TAIL_DRAW:
                from huian.rules.config import UnknownRuleError
                raise UnknownRuleError("GANG_HU_SCORING_UNKNOWN")
            expected = "PINGHU" if source == WinSource.DISCARD else "ZIMO"
            if win_type != expected:
                raise ValueError("Observed win type disagrees with the Hu declaration source")
        if self._state.pending_kong is not None:
            from huian.rules.config import UnknownRuleError
            raise UnknownRuleError("ROB_KONG_SCORING_UNKNOWN")
        last = self._state.last_action
        if (self._state.phase in ("AFTER_DRAW", "NEED_FLOWER_REPLACE")
                and isinstance(last, dict) and last.get("type") == env.ActionType.DRAW.value):
            context = HuContext.from_draw_metadata(last.get("metadata", {}))
            if context.is_gang_hu:
                from huian.rules.config import UnknownRuleError
                raise UnknownRuleError("GANG_HU_SCORING_UNKNOWN")
        result = self.settlement.settle(
            winner=winner,
            current_dealer_base=current_dealer_base,
            winner_fan=winner_fan,
            win_type=win_type,
        )
        before = self._state.state_hash()
        candidate = deepcopy(self._state)
        candidate.rewards = list(result.rewards)
        candidate.phase = "TERMINAL"
        candidate.terminal = True
        candidate.terminal_reason = "OBSERVED_" + result.win_type
        candidate.pending_discard = None
        candidate.pending_hu = None
        self.rules.validate_state(candidate)
        metadata = {"source": "observed", "win_type": result.win_type,
                    "current_dealer_base": current_dealer_base,
                    "winner_fan": winner_fan, "multiplier": result.multiplier}
        if declaration is not None:
            metadata["hu_declaration"] = declaration
        event = {
            "seq": len(self._events),
            "action": {"player": winner, "type": "END_HAND", "tile": None, "tiles": [],
                       "metadata": metadata},
            "before_hash": before,
            "after_hash": candidate.state_hash(),
            "wall_remaining": candidate.wall_remaining(),
            "current_player_after": candidate.current_player,
            "phase_after": candidate.phase,
        }
        self._state = candidate
        self._events.append(event)
        self._seen.add(self._position(candidate))
        return self.state, deepcopy(event)
    def action_report(self):
        self._require_state()
        return self.rules.action_report(self.state)

    def legal_actions(self):
        self._require_state()
        return self.rules.legal_actions(self.state)

    def is_terminal(self):
        self._require_state()
        self.rules.validate_state(self._state)
        return self._state.terminal

    def get_reward(self):
        self._require_state()
        return self.rules.reward(self.state)

    def checkpoint(self):
        self._require_state()
        token = self._next_token
        self._next_token += 1
        self._snapshots.append((token, deepcopy((self._state, self._events, self._seen))))
        return token

    def rollback(self, token=None):
        if not self._snapshots:
            raise ValueError("No checkpoint")
        if token is None:
            index = len(self._snapshots) - 1
        else:
            index = next((i for i, (t, _) in enumerate(self._snapshots) if t == token), None)
            if index is None:
                raise ValueError("Invalid or stale checkpoint")
        self._state, self._events, self._seen = deepcopy(self._snapshots[index][1])
        self._snapshots = self._snapshots[:index]
        return self.state

    def clone(self):
        return deepcopy(self)

    def step(self, action, strict=True):
        self._require_state()
        if strict is not True:
            raise ValueError("HuianEnvironment does not allow legality bypass")
        if self._state.terminal:
            raise ValueError("Hand is terminal")
        if len(self._events) >= self.max_steps:
            raise DeadLoopError("Scenario action limit reached; not a drawn hand")
        was_youjin_response_draw = self._state.phase == "YOUJIN_RESPONSE_DRAW"
        was_youjin_player_draw = self._state.phase == "YOUJIN_STAGE_SUCCESS"
        action = self._canonical_action(self._state, deepcopy(action))
        self.rules.authorize_action(self.state, action)
        before = self._state.state_hash()
        candidate = deepcopy(self._state)
        self._apply(candidate, action)
        self._resolve_wall_draw(candidate)
        flower_result = None
        if not candidate.terminal:
            flower_result = self._resolve_flowers(candidate)
            self._resolve_wall_draw(candidate)
        if flower_result is not None and action.type == env.ActionType.DRAW:
            replacements = [tile for item in flower_result.events
                            if item.player == action.player
                            for tile in item.replacements if tile not in env.FLOWERS]
            if len(replacements) == 1:
                action.metadata["effective_drawn_tile"] = replacements[0]
        if was_youjin_response_draw and not candidate.terminal:
            response_player = action.player
            youjin_player = 1 - response_player
            context = HuContext.from_draw_metadata(action.metadata)
            if self.rules.rules.can_win(
                    candidate.hands[response_player], candidate.gold_tile,
                    len(candidate.melds[response_player]), win_context=context):
                candidate.phase = "YOUJIN_RESPONSE_AFTER_DRAW"
            else:
                # Confirmed 2026-09-20: the missed interception draw remains
                # physically in the opponent's hand.
                candidate.youjin_response_draws[response_player] += 1
                candidate.current_player = youjin_player
                stage = YoujinStage(candidate.special_states[youjin_player])
                progression = youjin_progression_rule(stage)
                candidate.phase = (
                    "YOUJIN_SETTLEMENT_READY"
                    if progression.youjin_player_draw_chances == 0
                    else "YOUJIN_STAGE_SUCCESS"
                )
        if was_youjin_player_draw and not candidate.terminal:
            youjin_player = action.player
            if self.rules.rules.can_youjin_upgrade_after_draw(
                    candidate.hands[youjin_player], candidate.gold_tile,
                    len(candidate.melds[youjin_player])):
                candidate.phase = "YOUJIN_UPGRADE_CHOICE"
            else:
                candidate.phase = "YOUJIN_SETTLEMENT_READY"
        candidate.turn_index += 1
        candidate.last_action = action.to_dict()
        self.rules.validate_state(candidate)
        if sorted(candidate.physical_tiles()) != sorted(self._state.physical_tiles()):
            raise ValueError("Tile conservation failure")
        position = self._position(candidate)
        # PASS_QIANGJIN may intentionally keep every physical zone/phase unchanged
        # while closing the current special window via last_action. Other actions
        # must still make semantic progress.
        if position in self._seen and action.type != env.ActionType.PASS_QIANGJIN:
            raise DeadLoopError("Repeated position; not a drawn hand")
        event = env.Event(len(self._events), action, before, candidate.state_hash(),
                          candidate.wall_remaining(), candidate.current_player, candidate.phase).to_dict()
        event["rules_config"] = asdict(self.rules.rules.config)
        if flower_result is not None:
            event["flower_replacements"] = [asdict(item) for item in flower_result.events]
        if action.type == env.ActionType.ROB_KONG_HU:
            event["hu_declaration"] = deepcopy(candidate.pending_hu)
        # Commit only after every check succeeds. Caller never receives live data.
        self._state = candidate
        self._events.append(event)
        self._seen.add(position)
        return self.state, deepcopy(event)

    @classmethod
    def _resolve_flowers(cls, state):
        """Apply the high-confidence dealer-first flower replacement rounds."""
        if state.phase != "NEED_FLOWER_REPLACE":
            return None
        result = replace_flowers(
            state.hands, state.flowers, state.wall, state.dealer,
            minimum_wall_remaining=0)
        state.hands = [list(zone) for zone in result.hands]
        state.flowers = [list(zone) for zone in result.flowers]
        state.wall = list(result.wall)
        state.phase = ("NEED_FLOWER_REPLACE" if any(
            tile in env.FLOWERS for zone in state.hands for tile in zone
        ) else "AFTER_DRAW")
        return result
    def _resolve_wall_draw(self, state):
        if state.pending_kong is not None:
            # Preserve the rob-kong response/declaration first.
            return
        if not state.terminal and self.rules.rules.is_wall_draw(state):
            state.terminal = True
            state.phase = "TERMINAL"
            state.terminal_reason = "WALL_16"
            state.rewards = [0, 0]
            state.pending_discard = None

    @staticmethod
    def _canonical_action(state, action):
        """Normalize old replay draw labels before legality checks and new logging."""
        if (action.type == env.ActionType.PASS and state.phase == "ROB_KONG_WINDOW"
                and action.metadata == state.pending_kong
                and type(action.metadata.get("kong_player")) is int
                and type(action.metadata.get("meld_index")) is int
                and type(action.metadata.get("tile")) is str):
            return env.Action(action.player, action.type, action.tile, action.tiles)
        if action.type != env.ActionType.DRAW:
            return action
        metadata = dict(action.metadata)
        metadata.pop("drawn_tile", None)
        metadata.pop("effective_drawn_tile", None)
        source = DrawSource.parse(metadata.get("source"))
        metadata["source"] = source.value
        if source == DrawSource.WALL_TAIL and "kong_kind" not in metadata:
            if state.phase in ("AFTER_MING_GANG", "AFTER_AN_GANG", "AFTER_ADDED_GANG"):
                metadata["kong_kind"] = state.phase.removeprefix("AFTER_")
        return env.Action(action.player, action.type, action.tile, action.tiles, metadata)

    @staticmethod
    def _apply(state, action):
        p, kind = action.player, action.type
        T = env.ActionType
        if kind == T.DRAW:
            response_draw = state.phase == "YOUJIN_RESPONSE_DRAW"
            progression_draw = state.phase == "YOUJIN_STAGE_SUCCESS"
            source = DrawSource.parse(action.metadata.get("source"))
            tile = state.wall.pop(-1 if source == DrawSource.WALL_TAIL else 0)
            action.metadata["drawn_tile"] = tile
            state.hands[p].append(tile)
            if tile in env.FLOWERS:
                state.phase = "NEED_FLOWER_REPLACE"
            elif response_draw:
                state.phase = "YOUJIN_RESPONSE_AFTER_DRAW"
            elif progression_draw:
                state.phase = "AFTER_DRAW"
            else:
                state.phase = "AFTER_DRAW"
        elif kind == T.PASS:
            if state.phase == "YOUJIN_UPGRADE_CHOICE":
                if not action.metadata.get("youjin_upgrade_decline"):
                    raise ValueError("Youjin upgrade PASS must explicitly decline upgrade")
                state.phase = "YOUJIN_SETTLEMENT_READY"
                return
            if state.phase == "ROB_KONG_WINDOW":
                pending = state.pending_kong
                kong_player, tile = pending["kong_player"], pending["tile"]
                meld = state.melds[kong_player][pending["meld_index"]]
                state.hands[kong_player].remove(tile)
                state.melds[kong_player][pending["meld_index"]] = env.Meld(
                    "ADDED_GANG", list(meld.tiles) + [tile], meld.from_player)
                action.metadata.update(pending)
                state.pending_kong = None
                state.current_player = kong_player
                state.phase = "AFTER_ADDED_GANG"
                return
            # DISCARD already selected the sole opponent as current_player.
            # The declined tile stays in its owner's river.
            state.pending_discard = None
            state.phase = "NEED_DRAW"
        elif kind == T.YOUJIN:
            state.hands[p].remove(action.tile)
            state.discards[p].append(action.tile)
            state.pending_discard = None
            state.special_states[p] = "YOUJIN"
            state.current_player = 1 - p
            state.phase = "YOUJIN_RESPONSE_DRAW"
        elif kind in (T.DOUBLE_YOU, T.TRIPLE_YOU):
            if state.phase != "YOUJIN_UPGRADE_CHOICE":
                raise ValueError("Youjin upgrade action requires its choice phase")
            current = YoujinStage(state.special_states[p])
            progression = youjin_progression_rule(current)
            expected = (
                YoujinStage.DOUBLE_YOU if kind == T.DOUBLE_YOU
                else YoujinStage.TRIPLE_YOU
            )
            if progression.next_stage != expected:
                raise ValueError("Youjin upgrade does not match the next confirmed stage")
            if action.tile != state.gold_tile:
                raise ValueError("Youjin upgrade must discard one current gold tile")
            state.hands[p].remove(state.gold_tile)
            state.discards[p].append(state.gold_tile)
            state.pending_discard = None
            state.special_states[p] = expected.value
            state.current_player = 1 - p
            state.phase = "YOUJIN_RESPONSE_DRAW"
        elif kind == T.DISCARD:
            state.hands[p].remove(action.tile)
            state.discards[p].append(action.tile)
            state.pending_discard = dict(player=p, tile=action.tile,
                                         river_index=len(state.discards[p]) - 1)
            state.current_player = 1 - p
            state.phase = "AFTER_DISCARD"
        elif kind == T.ADD_KONG:
            state.pending_kong = {
                "kong_player": p, "tile": action.tile,
                "meld_index": action.metadata["meld_index"],
            }
            state.current_player = 1 - p
            state.phase = "ROB_KONG_WINDOW"
        elif kind == T.ROB_KONG_HU:
            pending = state.pending_kong
            state.pending_hu = {
                "winner": p, "loser": pending["kong_player"],
                "source": WinSource.ROB_KONG.value, "robbed_tile": action.tile,
                "winning_tile": action.tile, "kong_player": pending["kong_player"],
                "meld_index": pending["meld_index"],
            }
            state.current_player = p
            state.phase = "ROB_KONG_HU_DECLARED"
        elif kind == T.HU:
            if state.phase == "YOUJIN_RESPONSE_AFTER_DRAW":
                youjin_player = 1 - p
                state.special_states[youjin_player] = "NORMAL"
            source = WinSource(action.metadata.get("win_source"))
            pending = state.pending_discard if source == WinSource.DISCARD else None
            state.pending_hu = {
                "winner": p,
                "source": source.value,
                "winning_tile": action.tile,
                "kong_kind": action.metadata.get("kong_kind"),
                "discard_player": pending["player"] if pending else None,
                "river_index": pending["river_index"] if pending else None,
            }
            state.pending_discard = None
            state.current_player = p
            state.phase = "HU_DECLARED"
        elif kind in (T.CHI, T.PENG, T.MING_GANG, T.AN_GANG):
            consume = list(action.tiles)
            source = None
            if kind != T.AN_GANG:
                pending = state.pending_discard
                source = pending["player"]
                consume.remove(pending["tile"])
                state.discards[source].pop(pending["river_index"])
                state.pending_discard = None
            for tile in consume:
                state.hands[p].remove(tile)
            state.melds[p].append(env.Meld(kind.value, list(action.tiles), source))
            state.phase = "AFTER_" + kind.value
        else:
            raise ValueError("Unsupported transition")
