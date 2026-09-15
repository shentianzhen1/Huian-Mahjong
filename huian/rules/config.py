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
    "rob_kong": "Scope, response window and resolution for each kong kind",
    "qiangjin_hand_shape": "Exact effective Hu decomposition and room-option interaction at the opening check",
    "qiangjin_seat_priority": "Which eligible seat has priority if more than one can declare",
    "qiangjin_settlement": "Multiplier, payer and dealer continuation after a Qiangjin declaration",
    "sanjindao": "Legacy special-win entry; use the confirmed eligibility API separately",
    "sanjindao_timing": "Exact phases in which the confirmed declare/continue choice is offered",
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
    "flower_groups": "Group totals and replacement versus stacking",
    "fan_edge_cases": "Huian confirmation of gold/triplet/kong working values",
    "honor_peng_fan": "Whether exposed honor pung scores one fan",
    # External variants only; see references/HUIAN_WEB_RULES_2026-09-13.md.
    "exposed_triplet_fan": "Whether natural exposed suited triplets score in the target room",
    "eight_flowers_special_win": "Whether eight flowers grant a special win; timing and multiplier",
    "open_gold_procedure": "Reveal location and physical tile accounting",
    "deal_replacement_order": "Dealing order, flower replacement order and source",
    "added_kong_details": "Response window, replacement and incremental versus total fan",
    "decomposition_scoring": "Selection among multiple winning decompositions",
    "three_plus_gold_ordinary_hu": "Whether any ordinary Hu branch remains available with three or more golds",
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

    def __post_init__(self):
        if type(self.single_gold_can_pinghu) is not bool:
            raise ValueError("single_gold_can_pinghu must be boolean")
        if type(self.experimental_no_rob_kong) is not bool:
            raise ValueError("experimental_no_rob_kong must be boolean")
        if self.settlement_model not in (None, "current_dealer_plus_winner_v1"):
            raise ValueError("Unsupported settlement model")
