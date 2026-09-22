
DEFAULT_MULTIPLIERS = {
    "pinghu": 1,
    "zimo": 2,
    "qianggang": 2,
    "sanjindao": 3,
    "youjin": 3,
    "double_you": None,
    "triple_you": None,
}

def two_player_net_score(winner_base, winner_fan, loser_base, loser_fan,
                         win_type="zimo", multiplier=None):
    """
    Evidence-backed two-player formula from a real settlement:
      winner 5 base + 24 fan
      loser 10 base + 2 fan
      zimo x2
      => (29 - 12) * 2 = 34
    """
    if multiplier is None:
        multiplier = DEFAULT_MULTIPLIERS.get(win_type)
    if multiplier is None:
        raise ValueError(f"{win_type} 的二人倍率尚未确认，请手动传入 multiplier")
    return ((winner_base + winner_fan) - (loser_base + loser_fan)) * multiplier

def zero_sum_pair(net):
    return int(net), -int(net)
