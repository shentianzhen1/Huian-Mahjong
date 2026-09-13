
from abc import ABC, abstractmethod
from .actions import Action, ActionType

class RulesAdapter(ABC):
    """
    规则层接口。
    Environment 不负责决定“动作是否符合开心泉州二人麻将规则”；
    它只执行 RulesAdapter 已经允许的动作。
    """

    @abstractmethod
    def legal_actions(self, state):
        raise NotImplementedError

    def is_legal(self, state, action: Action) -> bool:
        return action in self.legal_actions(state)

    def is_terminal(self, state) -> bool:
        return bool(state.terminal)

    def reward(self, state):
        return list(state.rewards)

class ScaffoldRules(RulesAdapter):
    """
    仅用于环境层自测的最小规则。
    不代表最终开心泉州二人麻将规则。

    目前只允许：
    - 轮到当前玩家且牌墙非空 -> DRAW
    - 当前玩家手中已有牌 -> DISCARD 任意一张
    - PASS
    其他动作类型保留接口，后续由正式 Rules 实现。
    """

    def legal_actions(self, state):
        if state.terminal:
            return []
        p = state.current_player
        actions = [Action(p, ActionType.PASS)]

        # 简化环境自测：如果当前玩家手牌数量为0或比另一家少，可摸牌
        if state.wall:
            actions.append(Action(p, ActionType.DRAW))

        # 任意已有手牌可作为弃牌动作
        seen = set()
        for t in state.hands[p]:
            if t not in seen:
                actions.append(Action(p, ActionType.DISCARD, tile=t))
                seen.add(t)
        return actions
