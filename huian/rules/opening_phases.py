"""Validation and choice windows before a Gold indicator exists."""
from huian._legacy import env
from .special_outcomes import special_outcome_profile

PRE_GOLD_PHASES = {
    'OPENING_GOLD_PENDING', 'OPENING_EIGHT_FLOWER_CHOICE',
    'OPENING_EIGHT_FLOWER_DECLARED',
}


def validate_pre_gold(state):
    """Return True only for the narrowly supported, physically complete no-Gold opening."""
    no_gold_terminal = (state.terminal and state.gold_tile is None
                        and state.terminal_reason == 'AUTO_EIGHT_FLOWER_YOU')
    if state.phase not in PRE_GOLD_PHASES and not no_gold_terminal:
        return False
    if state.gold_tile is not None or state.reserved_tiles:
        raise ValueError('Pre-Gold opening cannot reserve an artificial indicator')
    if (any(state.melds) or any(state.discards) or state.pending_discard is not None
            or state.pending_kong is not None
            or state.special_states != ['NORMAL', 'NORMAL']):
        raise ValueError('Pre-Gold opening cannot contain in-play actions')
    if any(len(state.hands[p]) != (17 if p == state.dealer else 16) for p in (0, 1)):
        raise ValueError('Pre-Gold opening requires dealer17/non-dealer16')
    if state.phase in ('OPENING_EIGHT_FLOWER_CHOICE', 'OPENING_EIGHT_FLOWER_DECLARED'):
        if len(state.flowers[state.current_player]) != 8:
            raise ValueError('Opening eight-flower choice requires all eight flowers')
    elif state.phase == 'OPENING_GOLD_PENDING' and state.current_player != state.dealer:
        raise ValueError('Only dealer owns the opening Gold process')
    if no_gold_terminal:
        winner = 0 if state.rewards[0] > 0 else 1
        if len(state.flowers[winner]) != 8:
            raise ValueError('No-Gold terminal requires the winner to hold all eight flowers')
        last = state.last_action
        if (not isinstance(last, dict)
                or last.get('metadata', {}).get('opening_no_gold') is not True):
            raise ValueError('No-Gold terminal requires opening provenance')
    return True


def opening_eight_flower_actions(state):
    profile = special_outcome_profile('EIGHT_FLOWER_YOU')
    metadata = {**profile.action_metadata, 'window': 'opening_pre_gold',
                'opening_no_gold': True}
    return (
        env.Action(state.current_player, env.ActionType.HU, metadata=metadata),
        env.Action(state.current_player, env.ActionType.PASS_QIANGJIN,
                   metadata={'window': 'opening_pre_gold', 'opening_no_gold': True}),
    )
