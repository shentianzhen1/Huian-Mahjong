"""Confirmed opening events with an explicit candidate; never infer hidden dice mapping."""
from copy import deepcopy
from dataclasses import asdict

from huian._legacy import env
from huian.rules.registry import DEFAULT_RULE_SNAPSHOT
from huian.rules.first_round import new_first_round_state
from .flowers import replace_flowers
from .opening import deal_initial_hands

EVIDENCE_ID = 'player_confirmed_special_rules_20261006_v1'


def _metadata():
    return {'source': 'player_confirmed_rule', 'evidence_id': EVIDENCE_ID,
            'rule_snapshot_fingerprint': DEFAULT_RULE_SNAPSHOT.fingerprint}


def _commit(environment, candidate, action):
    candidate.last_action = deepcopy(action)
    environment.rules.validate_state(candidate)
    event = {'seq': len(environment._events), 'action': action,
             'before_hash': environment._state.state_hash(),
             'after_hash': candidate.state_hash(),
             'wall_remaining': candidate.wall_remaining(),
             'current_player_after': candidate.current_player, 'phase_after': candidate.phase}
    environment._state = candidate
    environment._events.append(event)
    environment._seen.add(environment._position(candidate))
    return environment.state, deepcopy(event)


def begin_confirmed_opening(environment):
    """Deal and finish both players' tail replacements, pausing before any Gold flip."""
    environment._require_state()
    if environment._state.phase != 'READY':
        raise ValueError('Confirmed opening requires READY')
    environment.rules.validate_state(environment._state)
    hands, wall = deal_initial_hands(environment._state.wall, environment._state.dealer)
    replacement = replace_flowers(hands, [[], []], wall, environment._state.dealer)
    candidate = deepcopy(environment._state)
    candidate.hands = [list(zone) for zone in replacement.hands]
    candidate.flowers = [list(zone) for zone in replacement.flowers]
    candidate.wall = list(replacement.wall)
    candidate.special_states = ['NORMAL', 'NORMAL']
    candidate.first_round = None
    qualifying = [p for p in (0, 1) if len(candidate.flowers[p]) == 8]
    candidate.current_player = qualifying[0] if qualifying else candidate.dealer
    candidate.phase = 'OPENING_EIGHT_FLOWER_CHOICE' if qualifying else 'OPENING_GOLD_PENDING'
    action = {'player': candidate.dealer, 'type': 'OPENING_REPLACE_FLOWERS',
              'tile': None, 'tiles': [], 'metadata': {
                  **_metadata(), 'deal_order': 'SIMULATOR_CONVENTION',
                  'replacement_source': 'wall_tail',
                  'replacement_events': [asdict(item) for item in replacement.events]}}
    return _commit(environment, candidate, action)


def reveal_opening_candidate(environment, *, wall_index, current_dealer_base):
    """Consume one externally specified candidate; no default location or direction.

    This is a scripted-wall/environment API, not a live hidden-position estimator.
    Live Vision continues to read only the final visible Gold and flower zones.
    """
    environment._require_state()
    state = environment._state
    if state.phase != 'OPENING_GOLD_PENDING':
        raise ValueError('Opening candidate requires OPENING_GOLD_PENDING')
    if type(wall_index) is not int or not 0 <= wall_index < len(state.wall):
        raise ValueError('wall_index must name a current drawable-wall tile')
    if type(current_dealer_base) is not int or current_dealer_base < 0:
        raise ValueError('current_dealer_base must be a nonnegative integer')
    if len(environment._events) >= environment.max_steps:
        raise ValueError('Opening event limit reached; not a drawn hand')
    environment.rules.validate_state(state)
    DEFAULT_RULE_SNAPSHOT.require_confirmed('physical.open_gold_candidate_flower')
    candidate = deepcopy(state)
    tile = candidate.wall.pop(wall_index)
    metadata = {**_metadata(), 'candidate_wall_index': wall_index,
                'location_policy': 'EXPLICIT_CANDIDATE_NO_INFERENCE'}
    action_type = 'OPEN_GOLD'
    if tile in env.FLOWERS:
        candidate.flowers[candidate.dealer].append(tile)
        action_type = 'OPEN_GOLD_FLOWER'
        metadata.update(hand_replacement=False, opening_no_gold=True)
        if len(candidate.flowers[candidate.dealer]) == 8:
            DEFAULT_RULE_SNAPSHOT.require_confirmed('state_machine.eight_flower_open_gold_force')
            fixed_fan = DEFAULT_RULE_SNAPSHOT.require_confirmed(
                'settlement.eight_flower_working_fixed_fan').value
            multiplier = DEFAULT_RULE_SNAPSHOT.require_confirmed(
                "settlement.eight_flower_working_multiplier").value
            net = (current_dealer_base + fixed_fan) * multiplier
            candidate.terminal = True
            candidate.phase = 'TERMINAL'
            candidate.terminal_reason = 'AUTO_EIGHT_FLOWER_YOU'
            candidate.rewards = [net, -net] if candidate.dealer == 0 else [-net, net]
            action_type = 'END_HAND'
            metadata.update(special='EIGHT_FLOWER_YOU', forced=True,
                            current_dealer_base=current_dealer_base, winner_fan=fixed_fan,
                            fixed_fan=fixed_fan, multiplier=multiplier,
                            fan_policy='FIXED_SPECIAL_FAN_NO_STACKING',
                            evidence_status='CONFIRMED', rewards=list(candidate.rewards))
    else:
        candidate.gold_tile = tile
        candidate.reserved_tiles.append(tile)
        candidate.phase = 'OPENING_POST_GOLD_PENDING'
        metadata['indicator_removed_from_drawable_wall'] = True
        if environment.rules.rules.can_tianhu(
                candidate.hands[candidate.dealer], tile,
                is_dealer=True, opening_complete=True):
            multiplier = DEFAULT_RULE_SNAPSHOT.require_confirmed('settlement.tianhu_multiplier').value
            fixed_fan = DEFAULT_RULE_SNAPSHOT.require_confirmed(
                "settlement.tianhu_fixed_fan").value
            net = (current_dealer_base + fixed_fan) * multiplier
            candidate.terminal = True
            candidate.phase = 'TERMINAL'
            candidate.terminal_reason = 'AUTO_TIANHU'
            candidate.rewards = [net, -net] if candidate.dealer == 0 else [-net, net]
            action_type = 'END_HAND'
            metadata.update(special='TIANHU', forced=True,
                            current_dealer_base=current_dealer_base, winner_fan=fixed_fan,
                            multiplier=multiplier, fan_policy='NO_ADDITIVE_FAN',
                            evidence_status='CONFIRMED', rewards=list(candidate.rewards))
        else:
            candidate.first_round = new_first_round_state(
                candidate,
                current_dealer_base=current_dealer_base,
                rules=environment.rules.rules,
            )
            nondealer = 1 - candidate.dealer
            metadata.update(
                first_round_initialized=True,
                qiangjin_window='FIRST_ROUND_ONLY',
                nondealer_tianting=candidate.first_round['tianting'][nondealer],
                nondealer_tianting_waits=list(
                    candidate.first_round['tianting_waits'][nondealer]
                ),
            )
    action = {'player': candidate.dealer, 'type': action_type,
              'tile': tile, 'tiles': [], 'metadata': metadata}
    return _commit(environment, candidate, action)
