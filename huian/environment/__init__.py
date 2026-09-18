from .state import HuianGameState
from .engine import HuianEnvironment, DeadLoopError
from .special_apply import apply_qiangjin_action

_orig_apply = HuianEnvironment._apply.__func__

@staticmethod
def _apply_with_qiangjin(state, action):
    if apply_qiangjin_action(state, action):
        return None
    return _orig_apply(state, action)

HuianEnvironment._apply = _apply_with_qiangjin

__all__ = ["HuianGameState", "HuianEnvironment", "DeadLoopError"]
