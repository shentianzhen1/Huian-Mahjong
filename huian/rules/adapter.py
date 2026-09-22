"""Legacy M1 compatibility plus explicit M2 Huian state validation/legality."""
from huian._legacy import env
from huian._compat.qzenv.rules_adapter import RulesAdapter
from mahjong_framework import MahjongRulesPlugin
from .config import UnknownRuleError
from .engine import HuianRules


class HuianRulesAdapter(RulesAdapter, MahjongRulesPlugin):
    variant_id = "huian.two_player.v0_1"
    def __init__(self, rules=None):
        self.rules = rules if rules is not None else HuianRules()

    def validate_state(self, state):
        from huian.environment.state import HuianGameState
        if isinstance(state, HuianGameState):
            from .phases import validate
            return validate(self, state)
        return self._validate_legacy_state(state)

    def _validate_legacy_state(self, state):
        if state.players != 2 or state.dealer not in (0, 1) or state.current_player not in (0, 1):
            raise ValueError("Invalid two-player seats")
        for zones in (state.hands, state.discards, state.melds, state.flowers):
            if len(zones) != 2:
                raise ValueError("Expected two player zones")
        if state.wall_remaining() < 0:
            raise ValueError("Negative wall count")
        tiles = list(state.wall)
        for p in range(2):
            self.rules.validate_tiles(state.hands[p])
            self.rules.validate_tiles(state.discards[p])
            if any(t not in env.FLOWERS for t in state.flowers[p]):
                raise ValueError("Non-flower in flower zone")
            tiles.extend(state.hands[p] + state.discards[p] + state.flowers[p])
            for meld in state.melds[p]:
                self.rules.validate_tiles(meld.tiles)
                if state.gold_tile in meld.tiles:
                    raise ValueError("Gold cannot participate in melds")
                kind = meld.kind
                if kind == "CHI":
                    if len(meld.tiles) != 3:
                        raise ValueError("Chi must contain three tiles")
                    ordered = sorted(meld.tiles)
                    first = ordered[0]
                    if first not in env.BASE_TILES[:27] or ordered != [
                        f"{first[0]}{int(first[1:]) + i}" for i in range(3)
                    ]:
                        raise ValueError("Invalid Chi sequence")
                elif kind in ("PENG", "MING_GANG", "AN_GANG", "ADDED_GANG"):
                    expected = 3 if kind == "PENG" else 4
                    if len(meld.tiles) != expected or len(set(meld.tiles)) != 1:
                        raise ValueError("Invalid pung/kong composition")
                else:
                    raise UnknownRuleError("added_kong_details")
                tiles.extend(meld.tiles)
        ok, message = env.validate_multiset(tiles)
        if not ok:
            raise ValueError(message)
        if state.gold_tile is not None and state.gold_tile not in env.BASE_TILES:
            raise ValueError("Invalid gold tile")
        if len(state.rewards) != 2 or sum(state.rewards) != 0:
            raise ValueError("Rewards must be two-player zero-sum")

    def legal_actions(self, state):
        from huian.environment.state import HuianGameState
        if isinstance(state, HuianGameState):
            result = self.action_report(state)
            if result.unresolved:
                raise UnknownRuleError(*result.unresolved)
            return list(result.known_actions)
        self.validate_state(state)
        if state.terminal:
            return []
        if state.phase not in ("AFTER_CHI", "AFTER_PENG"):
            raise UnknownRuleError("environment_phase")
        p = state.current_player
        if state.gold_tile is None or state.gold_tile in state.hands[p]:
            raise UnknownRuleError("youjin_trigger", "youjin_permissions")
        if len(state.hands[p]) != (5 - len(state.melds[p])) * 3 + 2:
            raise ValueError("Invalid post-claim hand size")
        if not state.melds[p] or state.melds[p][-1].kind != state.phase.removeprefix("AFTER_"):
            raise ValueError("Post-claim phase must match the latest meld")
        return [env.Action(p, env.ActionType.DISCARD, tile=t)
                for t in sorted(set(state.hands[p]))]

    def reward(self, state):
        self.validate_state(state)
        return list(state.rewards)

    def analyze_hu(self, hand, **context):
        return self.rules.analyze_hu(hand, **context)

    def action_report(self, state):
        from .special_windows import report_with_specials
        return report_with_specials(self, state)

    def authorize_action(self, state, action):
        if action.type in (env.ActionType.ADD_KONG, env.ActionType.ROB_KONG_HU):
            metadata = action.metadata
            if (not isinstance(metadata, dict)
                    or type(metadata.get("meld_index")) is not int):
                raise ValueError("A kong action requires an integer meld index")
            if (action.type == env.ActionType.ROB_KONG_HU
                    and type(metadata.get("kong_player")) is not int):
                raise ValueError("A rob-kong action requires an integer kong player")
        result = self.action_report(state)
        known = list(result.known_actions)
        # A specifically known action may execute even when other alternatives
        # remain unresolved. Match the full immutable Action, including metadata,
        # so forged kong indices/draw sources cannot be silently accepted.
        if action in known:
            return None
        if result.unresolved:
            raise UnknownRuleError(*result.unresolved)
        raise ValueError("Illegal action")
