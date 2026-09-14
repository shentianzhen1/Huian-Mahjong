"""Atomic deterministic transitions for the supported M2 subset."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import random

from huian._legacy import env
from huian.rules import HuianRulesAdapter
from .state import HuianGameState
from .opening import plan_opening


class DeadLoopError(RuntimeError):
    pass


class HuianEnvironment:
    def __init__(self, rules=None, max_steps=10000):
        if type(max_steps) is not int or max_steps <= 0:
            raise ValueError("max_steps must be a positive integer")
        self.rules = rules if rules is not None else HuianRulesAdapter()
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
        opening = plan_opening(self._state.wall, self._state.dealer, dice_total)
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
        action = deepcopy(action)
        if self._state.terminal:
            raise ValueError("Hand is terminal")
        if len(self._events) >= self.max_steps:
            raise DeadLoopError("Scenario action limit reached; not a drawn hand")
        self.rules.authorize_action(self.state, action)
        before = self._state.state_hash()
        candidate = deepcopy(self._state)
        self._apply(candidate, action)
        self._resolve_wall_draw(candidate)
        candidate.turn_index += 1
        candidate.last_action = action.to_dict()
        self.rules.validate_state(candidate)
        if sorted(candidate.physical_tiles()) != sorted(self._state.physical_tiles()):
            raise ValueError("Tile conservation failure")
        position = self._position(candidate)
        if position in self._seen:
            raise DeadLoopError("Repeated position; not a drawn hand")
        event = env.Event(len(self._events), action, before, candidate.state_hash(),
                          candidate.wall_remaining(), candidate.current_player, candidate.phase).to_dict()
        event["rules_config"] = asdict(self.rules.rules.config)
        # Commit only after every check succeeds. Caller never receives live data.
        self._state = candidate
        self._events.append(event)
        self._seen.add(position)
        return self.state, deepcopy(event)

    def _resolve_wall_draw(self, state):
        if not state.terminal and self.rules.rules.is_wall_draw(state):
            state.terminal = True
            state.phase = "TERMINAL"
            state.terminal_reason = "WALL_16"
            state.rewards = [0, 0]
            state.pending_discard = None

    @staticmethod
    def _apply(state, action):
        p, kind = action.player, action.type
        T = env.ActionType
        if kind == T.DRAW:
            tile = state.wall.pop(-1 if action.metadata["source"] == "tail" else 0)
            state.hands[p].append(tile)
            state.phase = "NEED_FLOWER_REPLACE" if tile in env.FLOWERS else "AFTER_DRAW"
        elif kind == T.PASS:
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
