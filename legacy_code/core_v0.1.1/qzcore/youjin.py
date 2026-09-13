
from enum import Enum

class YouJinState(str, Enum):
    NORMAL = "NORMAL"
    YOUJIN = "YOUJIN"
    DOUBLE_YOU = "DOUBLE_YOU"
    TRIPLE_YOU = "TRIPLE_YOU"

def next_state(current, condition_met):
    """
    Minimal explicit state machine.
    The caller is responsible for evaluating the exact game condition
    (e.g. gold can serve as pair member, drawing another gold, etc.).
    """
    if not condition_met:
        return current
    if current == YouJinState.NORMAL:
        return YouJinState.YOUJIN
    if current == YouJinState.YOUJIN:
        return YouJinState.DOUBLE_YOU
    if current == YouJinState.DOUBLE_YOU:
        return YouJinState.TRIPLE_YOU
    return YouJinState.TRIPLE_YOU
