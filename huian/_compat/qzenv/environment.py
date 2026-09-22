
from __future__ import annotations
from copy import deepcopy
import random

from .actions import Action, ActionType
from .events import Event
from .state import GameState, Meld
from .tiles import full_wall, validate_multiset
from .rules_adapter import RulesAdapter, ScaffoldRules

class QuanzhouEnvironment:
    """
    泉州麻将环境层骨架：
    - GameState 状态维护
    - step(action)
    - clone()
    - checkpoint()/rollback()
    - EventLog
    - 与 RulesAdapter 解耦

    重要：
    本文件只实现“状态怎么变化”，不写死未确认的麻将规则。
    """

    def __init__(self, rules: RulesAdapter | None = None):
        self.rules = rules or ScaffoldRules()
        self.state = GameState()
        self.events: list[Event] = []
        self._snapshots: list[tuple[GameState, list[Event]]] = []

    def reset(self, wall=None, seed=None, dealer=0):
        if wall is None:
            wall = full_wall()
            rng = random.Random(seed)
            rng.shuffle(wall)
        else:
            wall = list(wall)

        ok, msg = validate_multiset(wall)
        if not ok:
            raise ValueError(msg)

        self.state = GameState(
            players=2,
            dealer=dealer,
            current_player=dealer,
            wall=list(wall),
            phase="READY",
        )
        self.events = []
        self._snapshots = []
        return deepcopy(self.state)

    def set_state(self, state: GameState):
        self.state = deepcopy(state)
        return deepcopy(self.state)

    def legal_actions(self):
        return self.rules.legal_actions(self.state)

    def checkpoint(self):
        token = len(self._snapshots)
        self._snapshots.append((deepcopy(self.state), deepcopy(self.events)))
        return token

    def rollback(self, token=None):
        if not self._snapshots:
            raise RuntimeError("没有可回滚的快照")
        if token is None:
            state, events = self._snapshots.pop()
        else:
            if token < 0 or token >= len(self._snapshots):
                raise IndexError("无效 checkpoint token")
            state, events = self._snapshots[token]
            self._snapshots = self._snapshots[:token]
        self.state = deepcopy(state)
        self.events = deepcopy(events)
        return deepcopy(self.state)

    def clone(self):
        other = QuanzhouEnvironment(self.rules)
        other.state = deepcopy(self.state)
        other.events = deepcopy(self.events)
        other._snapshots = deepcopy(self._snapshots)
        return other

    def is_terminal(self):
        return self.rules.is_terminal(self.state)

    def get_reward(self):
        return self.rules.reward(self.state)

    def step(self, action: Action, strict=True):
        if self.state.terminal:
            raise RuntimeError("牌局已经结束")

        if strict and not self.rules.is_legal(self.state, action):
            raise ValueError(f"非法动作: {action}")

        before = self.state.state_hash()
        self._apply(action)
        self.state.turn_index += 1
        self.state.last_action = action.to_dict()
        after = self.state.state_hash()

        ev = Event(
            seq=len(self.events),
            action=action,
            before_hash=before,
            after_hash=after,
            wall_remaining=self.state.wall_remaining(),
            current_player_after=self.state.current_player,
            phase_after=self.state.phase,
        )
        self.events.append(ev)
        return deepcopy(self.state), ev

    def _apply(self, action: Action):
        p = action.player
        if not (0 <= p < self.state.players):
            raise ValueError("player 越界")

        t = action.type

        if t == ActionType.DRAW:
            if not self.state.wall:
                raise RuntimeError("牌墙为空")
            tile = self.state.wall.pop(0)
            self.state.hands[p].append(tile)
            self.state.phase = "AFTER_DRAW"
            return

        if t == ActionType.DISCARD:
            if action.tile is None:
                raise ValueError("DISCARD 需要 tile")
            try:
                self.state.hands[p].remove(action.tile)
            except ValueError:
                raise ValueError(f"玩家{p}手牌里没有 {action.tile}")
            self.state.discards[p].append(action.tile)
            self.state.current_player = (p + 1) % self.state.players
            self.state.phase = "AFTER_DISCARD"
            return

        if t == ActionType.FLOWER_REPLACE:
            # 这里只执行状态变化；何时允许补花由 Rules 决定。
            if action.tile is None:
                raise ValueError("FLOWER_REPLACE 需要 flower tile")
            if action.tile in self.state.hands[p]:
                self.state.hands[p].remove(action.tile)
            self.state.flowers[p].append(action.tile)
            if not self.state.wall:
                raise RuntimeError("牌墙为空，无法补花")
            replacement = self.state.wall.pop()
            self.state.hands[p].append(replacement)
            self.state.phase = "AFTER_FLOWER_REPLACE"
            return

        if t == ActionType.OPEN_GOLD:
            if action.tile is not None:
                self.state.gold_tile = action.tile
            elif self.state.wall:
                self.state.gold_tile = self.state.wall.pop()
            else:
                raise RuntimeError("没有牌可开金")
            self.state.phase = "GOLD_OPENED"
            return

        if t in (ActionType.CHI, ActionType.PENG, ActionType.MING_GANG, ActionType.AN_GANG):
            tiles = list(action.tiles)
            if not tiles:
                raise ValueError(f"{t.value} 需要 tiles")
            # 只做通用“把本家提供的牌移出手牌并形成副露”。
            # claimed_tile / 来源玩家等具体语义由 metadata 传入。
            consume = list(action.metadata.get("consume_from_hand", tiles))
            for tile in consume:
                try:
                    self.state.hands[p].remove(tile)
                except ValueError:
                    raise ValueError(f"副露动作需要的 {tile} 不在玩家{p}手牌中")
            self.state.melds[p].append(
                Meld(
                    kind=t.value,
                    tiles=tiles,
                    from_player=action.metadata.get("from_player"),
                )
            )
            self.state.current_player = p
            self.state.phase = f"AFTER_{t.value}"
            return

        if t == ActionType.HU:
            self.state.terminal = True
            rewards = action.metadata.get("rewards")
            if rewards is not None:
                if len(rewards) != self.state.players:
                    raise ValueError("rewards 长度必须等于玩家数")
                self.state.rewards = list(rewards)
            self.state.phase = "TERMINAL"
            return

        if t in (ActionType.YOUJIN, ActionType.DOUBLE_YOU, ActionType.TRIPLE_YOU):
            self.state.phase = t.value
            return

        if t == ActionType.END_HAND:
            self.state.terminal = True
            rewards = action.metadata.get("rewards", [0] * self.state.players)
            self.state.rewards = list(rewards)
            self.state.phase = "TERMINAL"
            return

        if t == ActionType.PASS:
            self.state.phase = "PASS"
            return

        raise NotImplementedError(f"Environment 尚未实现动作: {t.value}")
