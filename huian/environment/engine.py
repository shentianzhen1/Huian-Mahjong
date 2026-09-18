"""Atomic deterministic transitions for the supported M2 subset."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import random

from huian._legacy import env
from huian.rules import HuianRulesAdapter
from huian.rules.context import DrawSource, HuContext, WinSource
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
        """Apply the V0.1 opening planner and stop for the unresolved 抢金 check.

        This is an explicit simulator setup operation, not an automatic game
        action.  It preserves the selected indicator in the wall until the
        real room's physical accounting is observed.
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
        if self._has_added_kong(self._state):
            from huian.rules.config import UnknownRuleError
            raise UnknownRuleError("ADD_KONG_SCORING_UNKNOWN")
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
            source = WinSource(declaration["source"])
            if source == WinSource.ROB_KONG:
                from huian.rules.config import UnknownRuleError
                raise UnknownRuleError("ROB_KONG_SCORING_UNKNOWN")
            if source == WinSource.KONG_TAIL_DRAW:
                from huian.rules.config import UnknownRuleError
                raise UnknownRuleError("GANG_HU_SCORING_UNKNOWN")
            expected = "PINGHU" if source == WinSource.DISCARD else "ZIMO"
            if win_type != expected:
                raise ValueError("Observed win type disagrees with the Hu declaration source")
        if self._state.pending_kong is not None or self._has_added_kong(self._state):
            from huian.rules.config import UnknownRuleError
            raise UnknownRuleError("ADD_KONG_SCORING_UNKNOWN")
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

    @staticmethod
    def _has_added_kong(state):
        return any(meld.kind == "ADDED_GANG" for zone in state.melds for meld in zone)

    @classmethod
    def _resolve_flowers(cls, state):
        """Apply the high-confidence dealer-first flower replacement rounds."""
        if state.phase != "NEED_FLOWER_REPLACE":
            return None
        # An added kong has unresolved accounting at a drawn-hand boundary.
        # Stop replacement at 16 without manufacturing a zero-fee settlement.
        boundary = 16 if cls._has_added_kong(state) else 0
        result = replace_flowers(state.hands, state.flowers, state.wall, state.dealer,
                                 minimum_wall_remaining=boundary)
        state.hands = [list(zone) for zone in result.hands]
        state.flowers = [list(zone) for zone in result.flowers]
        state.wall = list(result.wall)
        state.phase = ("NEED_FLOWER_REPLACE" if any(
            tile in env.FLOWERS for zone in state.hands for tile in zone
        ) else "AFTER_DRAW")
        return result
    def _resolve_wall_draw(self, state):
        if state.pending_kong is not None or self._has_added_kong(state):
            # Preserve the response/declaration first; scoring remains UNKNOWN.
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
            source = DrawSource.parse(action.metadata.get("source"))
            tile = state.wall.pop(-1 if source == DrawSource.WALL_TAIL else 0)
            action.metadata["drawn_tile"] = tile
            state.hands[p].append(tile)
            state.phase = "NEED_FLOWER_REPLACE" if tile in env.FLOWERS else "AFTER_DRAW"
        elif kind == T.PASS:
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
