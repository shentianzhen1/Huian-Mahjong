"""Transitions for current-player special declarations and PASS windows."""
from huian._legacy import env
from huian.rules.registry import DEFAULT_RULE_SNAPSHOT


def _first_round_qiangjin(state, action):
    first = getattr(state, "first_round", None)
    if (not isinstance(first, dict) or not first.get("active")
            or action.metadata.get("window") != "first_round"):
        return False
    p = action.player
    if p not in (0, 1) or not first["qiangjin_eligible"][p]:
        raise ValueError("First-round Qiangjin action requires an eligible seat")
    if first["qiangjin_resolved"][p]:
        raise ValueError("First-round Qiangjin opportunity is already resolved")
    if action.type == env.ActionType.PASS_QIANGJIN:
        first["qiangjin_resolved"][p] = True
        action.metadata.update(
            evidence_id=first["evidence_id"],
            settlement_ready=False,
            resolved_without_hu=True,
        )
        # Dealer priority is evaluated while the nondealer still owns the
        # post-first-draw turn. A dealer PASS therefore must not steal the turn.
        state.phase = "AFTER_DRAW"
        return True
    if action.type != env.ActionType.QIANGJIN:
        return False

    rule = DEFAULT_RULE_SNAPSHOT.require_confirmed("settlement.qiangjin_full")
    multiplier = rule.value["multiplier"]
    fan = first["qiangjin_fan"][p]
    if type(fan) is not int or fan < 0:
        raise ValueError("Confirmed Qiangjin settlement requires audited normal fan")
    base = first["current_dealer_base"]
    net = (base + fan) * multiplier
    state.rewards = [net, -net] if p == 0 else [-net, net]
    state.current_player = p
    state.pending_discard = None
    state.pending_hu = None
    state.pending_kong = None
    state.terminal = True
    state.phase = "TERMINAL"
    # Qiangjin uses the ordinary Zimo x2 settlement class. The action metadata
    # retains the distinct special trigger/rule ID instead of inventing a new
    # payer or multiplier model.
    state.terminal_reason = "AUTO_ZIMO"
    first["active"] = False
    first["qiangjin_resolved"][p] = True
    first["closed_reason"] = "QIANGJIN"
    action.metadata.update(
        source="player_confirmed_rule",
        evidence_id=first["evidence_id"],
        evidence_status="CONFIRMED",
        settlement_rule_id="settlement.qiangjin_full",
        current_dealer_base=base,
        winner_fan=fan,
        multiplier=multiplier,
        formula="(current_dealer_base + ordinary_fan) * 2",
        virtual_gold=True,
        physical_gold_moved=False,
        rewards=list(state.rewards),
    )
    return True


def apply_qiangjin_action(state, action):
    T = env.ActionType
    p = action.player
    if _first_round_qiangjin(state, action):
        return True
    if action.type == T.HU and action.metadata.get("special") == "SANJINDAO":
        state.pending_hu = {
            "winner": p,
            "source": "sanjindao",
            "gold_count": state.hands[p].count(state.gold_tile),
        }
        state.current_player = p
        state.phase = "SANJINDAO_DECLARED"
        return True
    if action.type == T.HU and action.metadata.get("special") == "EIGHT_FLOWER_YOU":
        state.pending_hu = {
            "winner": p,
            "source": "eight_flower_you",
            "flower_count": len(state.flowers[p]),
            "fixed_fan": action.metadata.get("fixed_fan"),
            "multiplier": action.metadata.get("multiplier"),
            "project_rule": bool(action.metadata.get("project_rule")),
        }
        state.current_player = p
        state.phase = ("OPENING_EIGHT_FLOWER_DECLARED"
                       if state.phase == "OPENING_EIGHT_FLOWER_CHOICE"
                       else "EIGHT_FLOWER_YOU_DECLARED")
        return True
    if action.type == T.PASS_QIANGJIN and state.phase == "OPENING_EIGHT_FLOWER_CHOICE":
        state.current_player = state.dealer
        state.phase = "OPENING_GOLD_PENDING"
        return True
    if action.type == T.PASS_QIANGJIN:
        expected = 16 - 3 * len(state.melds[p])
        state.phase = "AFTER_DRAW" if len(state.hands[p]) > expected else "NEED_DRAW"
        return True
    if action.type == T.QIANGJIN:
        # Historical/imported states without first_round provenance remain
        # declaration-only. New confirmed runtime paths never reach this branch.
        state.pending_hu = {
            "winner": p,
            "source": "qiangjin",
        }
        state.current_player = p
        state.phase = "QIANGJIN_DECLARED"
        return True
    return False
