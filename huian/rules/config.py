from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType


class EvidenceStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    WORKING = "WORKING"
    UNKNOWN = "UNKNOWN"


# Evidence authority: RULE_STATUS.md, not legacy KNOWN_RULES.md.
UNKNOWN_RULES = MappingProxyType({
    "ROB_KONG_SCORING_UNKNOWN": "Settlement for a declared added-kong robbery",
    "GANG_HU_SCORING_UNKNOWN": "Settlement for a declared kong-tail win",
    # No independent kong fee: confirmed by player 2026-09-18.
    # Legacy ADD_KONG_SCORING_UNKNOWN retired 2026-09-18: completed added-kong
    # no longer blocks ordinary simulation merely because it occurred.
    "rob_kong": "Scope, response window and resolution for each kong kind",
    "qiangjin_hand_shape": "Exact effective Hu decomposition and room-option interaction at the opening check",
    "qiangjin_seat_priority": "Which eligible seat has priority if more than one can declare",
    "qiangjin_settlement": "Multiplier, payer and dealer continuation after a Qiangjin declaration",
    "sanjindao": "Legacy special-win entry; use the confirmed eligibility API separately",
    # Sanjindao timing resolved 2026-09-18: one-shot when the third gold is received.
    "sanjindao_settlement": "Non-flower base, payment, terminal flow and dealer result after the confirmed x3 declaration",
    "sanjinyou_trigger": "Exact executable steps shared by Erjin-You and Sanjin-You",
    "gang_hu_scoring": "Fan, multiplier and stacking for a confirmed kong-tail Hu",
    "youjin_trigger": "Exact entry conditions and edge cases",
    "double_you_entry": "Direct entry versus required prior Youjin",
    "triple_you_sequence": "Chronological upgrade sequence",
    "youjin_permissions": "Opponent rights and cancellation actions at every stage",
    "room_multipliers": "Unconfirmed multipliers outside the confirmed Youjin 4/8/16 and dealer-win x2 factors",
    "flower_open_gold": "Ownership, replacement and reopening after revealing a flower",
    "tianhu": "Timing relative to flower replacement and opening gold",
    "tianting": "Exact definition",
    "match_tie": "Tie handling after eight hands",
    "dealer_base_extension": "Dealer third continuation onward and cap",
    # flower_groups resolved: strictly 1 fan per flower, no four-flower bonus.
    # multi_gold_fan resolved: strictly 1 fan per gold, cumulative.
    "fan_edge_cases": "Remaining gold/triplet/decomposition fan edge cases; kong table is adopted separately",
    "honor_peng_fan": "Whether exposed honor pung scores one fan",
    # External variants only; see references/HUIAN_WEB_RULES_2026-09-13.md.
    "exposed_triplet_fan": "Whether natural exposed suited triplets score in the target room",
    # Eight-flower trigger/pass confirmed; project provisional multiplier is x2.
    "eight_flower_real_multiplier": "Real-room multiplier for eight-flower win; project uses provisional x2",
    "open_gold_procedure": "Reveal location and physical tile accounting",
    "deal_replacement_order": "Dealing order, flower replacement order and source",
    "added_kong_details": "Remaining added-kong UI/payment edge cases; fan table and rob scope are adopted",
    "decomposition_scoring": "Selection among multiple winning decompositions",
    # three_plus_gold_ordinary_hu resolved for self-draw after declining Sanjindao.
    "three_plus_gold_discard_hu": "Whether 3+ golds may win from an opponent discard after Sanjindao was declined",
    "environment_phase": "Complete legal action set for unsupported legacy phases",
    "win_declaration_and_settlement": "Automatic fan aggregation and settlement after an audited Hu declaration",
    "self_draw_decline": "Whether an available ordinary self-draw Hu may be declined to continue play",
})


class UnknownRuleError(RuntimeError):
    def __init__(self, *rule_ids):
        self.rule_ids = tuple(rule_ids)
        super().__init__("Unresolved Huian rules: " + ", ".join(rule_ids))


@dataclass(frozen=True)
class RulesConfig:
    # Explicit opt-in to the hypothesis; no legacy formula fallback.
    settlement_model: str | None = None
    # Test scenarios only. False means UNKNOWN scope, not "rob kong allowed".
    experimental_no_rob_kong: bool = False
    # Player feedback: room/player setting, usually disabled. Never infer from the generic page.
    single_gold_can_pinghu: bool = False
    # Simulator-only profile.  It never enables a special Huian rule.
    simulation_only_normal_hand: bool = False
    # Disable only new added-kong offers; an existing response window still resolves.
    enable_added_kong: bool = True

    def __post_init__(self):
        if type(self.enable_added_kong) is not bool:
            raise ValueError("enable_added_kong must be boolean")
        if type(self.single_gold_can_pinghu) is not bool:
            raise ValueError("single_gold_can_pinghu must be boolean")
        if type(self.experimental_no_rob_kong) is not bool:
            raise ValueError("experimental_no_rob_kong must be boolean")
        if type(self.simulation_only_normal_hand) is not bool:
            raise ValueError("simulation_only_normal_hand must be boolean")
        if self.settlement_model not in (None, "current_dealer_plus_winner_v1"):
            raise ValueError("Unsupported settlement model")
