"""Versioned rule registry and immutable rule snapshots.

The registry is metadata-first: every high-impact rule keeps a stable ID,
evidence status, revision, value, blast radius and implementation boundary.
"""
from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import json
from types import MappingProxyType

from .config import EvidenceStatus


class RuleDomain(str, Enum):
    PHYSICAL = "physical"
    LEGALITY = "legality"
    STATE_MACHINE = "state_machine"
    FAN = "fan"
    SCORING = "scoring"
    SETTLEMENT = "settlement"
    MATCH = "match"


class ImpactLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RuleNotConfirmedError(RuntimeError):
    def __init__(self, rule_id, status):
        self.rule_id = rule_id
        self.status = status
        super().__init__(f"Rule {rule_id} is {status.value}, not CONFIRMED")


@dataclass(frozen=True)
class RuleRecord:
    rule_id: str
    domain: RuleDomain
    status: EvidenceStatus
    revision: int
    value: object
    impact: ImpactLevel
    evidence_ids: tuple[str, ...] = ()
    implementation: str | None = None
    depends_on: tuple[str, ...] = ()
    note: str = ""

    def __post_init__(self):
        if not isinstance(self.rule_id, str) or not self.rule_id:
            raise ValueError("rule_id must be a nonempty string")
        if not isinstance(self.domain, RuleDomain):
            raise TypeError("domain must be RuleDomain")
        if not isinstance(self.status, EvidenceStatus):
            raise TypeError("status must be EvidenceStatus")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be a positive integer")
        if not isinstance(self.impact, ImpactLevel):
            raise TypeError("impact must be ImpactLevel")
        if any(not isinstance(item, str) or not item for item in self.evidence_ids):
            raise ValueError("evidence_ids must contain nonempty strings")
        if any(not isinstance(item, str) or not item for item in self.depends_on):
            raise ValueError("depends_on must contain nonempty rule IDs")
        try:
            json.dumps(self.value, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("rule value must be JSON-serializable") from exc

    def to_dict(self):
        return {
            "rule_id": self.rule_id,
            "domain": self.domain.value,
            "status": self.status.value,
            "revision": self.revision,
            "value": self.value,
            "impact": self.impact.value,
            "evidence_ids": list(self.evidence_ids),
            "implementation": self.implementation,
            "depends_on": list(self.depends_on),
            "note": self.note,
        }


@dataclass(frozen=True)
class RuleSnapshot:
    label: str
    records: object
    schema_version: int = 1

    def __post_init__(self):
        if not isinstance(self.label, str) or not self.label:
            raise ValueError("label must be a nonempty string")
        if type(self.schema_version) is not int or self.schema_version < 1:
            raise ValueError("schema_version must be a positive integer")
        items = dict(self.records)
        for rule_id, record in items.items():
            if not isinstance(record, RuleRecord):
                raise TypeError("records must contain RuleRecord values")
            if rule_id != record.rule_id:
                raise ValueError("snapshot key must equal RuleRecord.rule_id")
        unknown_dependencies = sorted({
            dependency
            for record in items.values()
            for dependency in record.depends_on
            if dependency not in items
        })
        if unknown_dependencies:
            raise ValueError(
                "snapshot contains unknown dependencies: "
                + ", ".join(unknown_dependencies)
            )
        object.__setattr__(
            self, "records",
            MappingProxyType(dict(sorted(items.items()))),
        )

    def get(self, rule_id):
        try:
            return self.records[rule_id]
        except KeyError as exc:
            raise KeyError(f"Unknown rule ID: {rule_id}") from exc

    def require_confirmed(self, rule_id):
        record = self.get(rule_id)
        if record.status != EvidenceStatus.CONFIRMED:
            raise RuleNotConfirmedError(rule_id, record.status)
        return record

    def with_overrides(self, *, label, overrides):
        records = dict(self.records)
        for rule_id, changes in overrides.items():
            current = self.get(rule_id)
            if not isinstance(changes, dict) or not changes:
                raise ValueError("each override must be a nonempty dict")
            if "rule_id" in changes and changes["rule_id"] != rule_id:
                raise ValueError("override cannot rename a rule ID")
            records[rule_id] = replace(current, **changes)
        return RuleSnapshot(label=label, records=records,
                            schema_version=self.schema_version)

    def to_manifest(self):
        return {
            "schema_version": self.schema_version,
            "label": self.label,
            "fingerprint": self.fingerprint,
            "rules": [record.to_dict() for record in self.records.values()],
        }

    @property
    def fingerprint(self):
        payload = {
            "schema_version": self.schema_version,
            "rules": [record.to_dict() for record in self.records.values()],
        }
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _record(rule_id, domain, status, revision, value, impact, evidence_ids,
            implementation, *, depends_on=(), note=""):
    return RuleRecord(
        rule_id=rule_id,
        domain=domain,
        status=status,
        revision=revision,
        value=value,
        impact=impact,
        evidence_ids=tuple(evidence_ids),
        implementation=implementation,
        depends_on=tuple(depends_on),
        note=note,
    )


P20261006 = ("player_confirmed_special_rules_20261006_v1",)

RULE_REGISTRY = MappingProxyType({
    "physical.open_gold_reserved_copy": _record(
        "physical.open_gold_reserved_copy", RuleDomain.PHYSICAL,
        EvidenceStatus.CONFIRMED, 1, True, ImpactLevel.CRITICAL,
        ("player_2026-09-20",), "huian.environment",
        note="Opened Jin is one physical copy reserved outside the drawable wall.",
    ),
    "physical.max_playable_gold_copies": _record(
        "physical.max_playable_gold_copies", RuleDomain.PHYSICAL,
        EvidenceStatus.CONFIRMED, 1, 3, ImpactLevel.CRITICAL,
        ("player_2026-09-20",), "huian.environment",
        depends_on=("physical.open_gold_reserved_copy",),
    ),
    "physical.open_gold_candidate_flower": _record(
        "physical.open_gold_candidate_flower", RuleDomain.PHYSICAL,
        EvidenceStatus.CONFIRMED, 1,
        "DEALER_FLOWER_ZONE_NO_HAND_REPLACEMENT", ImpactLevel.CRITICAL,
        P20261006, "huian.environment.opening_flow",
    ),
    "state_machine.eight_flower_open_gold_force": _record(
        "state_machine.eight_flower_open_gold_force", RuleDomain.STATE_MACHINE,
        EvidenceStatus.CONFIRMED, 1, "NEW_EIGHTH_FLOWER_AUTO_END_BEFORE_GOLD",
        ImpactLevel.CRITICAL, P20261006, "huian.environment.opening_flow",
        depends_on=("physical.open_gold_candidate_flower",
                    "settlement.eight_flower_real"),
    ),
    "state_machine.eight_flower_pre_gold_choice": _record(
        "state_machine.eight_flower_pre_gold_choice", RuleDomain.STATE_MACHINE,
        EvidenceStatus.CONFIRMED, 1,
        "DECLARE_OR_PASS_AFTER_COMPLETED_REPLACEMENT", ImpactLevel.HIGH,
        P20261006, "huian.rules.opening_phases",
    ),
    "legality.tianhu_opening": _record(
        "legality.tianhu_opening", RuleDomain.LEGALITY,
        EvidenceStatus.CONFIRMED, 1,
        "DEALER_17_FIVE_MELDS_PAIR_AFTER_REPLACEMENT_AND_GOLD",
        ImpactLevel.CRITICAL, P20261006, "huian.rules.engine",
    ),
    "settlement.tianhu_fixed_fan": _record(
        "settlement.tianhu_fixed_fan", RuleDomain.SETTLEMENT,
        EvidenceStatus.CONFIRMED, 1, 0, ImpactLevel.HIGH,
        P20261006, "huian.environment.opening_flow",
        note="No ordinary Gold/flower/triplet/Kong fan stacks onto Tianhu.",
    ),
    "settlement.tianhu_multiplier": _record(
        "settlement.tianhu_multiplier", RuleDomain.SETTLEMENT,
        EvidenceStatus.CONFIRMED, 1, 2, ImpactLevel.HIGH,
        P20261006, "huian.environment.opening_flow",
        depends_on=("legality.tianhu_opening",),
        note="Automatic dealer opening Hu; no additive fan.",
    ),
    "legality.qiangjin_virtual_gold_shape": _record(
        "legality.qiangjin_virtual_gold_shape", RuleDomain.LEGALITY,
        EvidenceStatus.CONFIRMED, 1,
        {
            "dealer": "REMAINING_16_PLUS_RESERVED_GOLD_VIRTUAL_17",
            "nondealer": "FIRST_DRAW_17_REPLACE_DRAWN_TILE_WITH_RESERVED_GOLD",
            "physical_gold_moved": False,
        },
        ImpactLevel.CRITICAL, P20261006, "huian.rules.first_round",
        depends_on=("physical.open_gold_reserved_copy",),
        note="Virtual Gold is the one reserved opened copy; never duplicate an entity tile.",
    ),
    "state_machine.qiangjin_first_round_timing": _record(
        "state_machine.qiangjin_first_round_timing", RuleDomain.STATE_MACHINE,
        EvidenceStatus.CONFIRMED, 1,
        "OPENING_COMPLETE_THEN_DEALER_FIRST_DISCARD_THEN_NONDEALER_FIRST_DRAW_ONLY",
        ImpactLevel.CRITICAL, P20261006, "huian.rules.first_round",
        depends_on=("legality.qiangjin_virtual_gold_shape",),
        note="Later normal draws, flower replacement and Kong-tail draws do not reopen Qiangjin.",
    ),
    "state_machine.qiangjin_seat_priority": _record(
        "state_machine.qiangjin_seat_priority", RuleDomain.STATE_MACHINE,
        EvidenceStatus.CONFIRMED, 1, "NONDEALER_THEN_DEALER",
        ImpactLevel.CRITICAL, P20261006, "huian.rules.special_windows",
        depends_on=("state_machine.qiangjin_first_round_timing",),
        note="Dealer opportunity waits until nondealer is ineligible or explicitly passes.",
    ),
    "state_machine.tianting_status": _record(
        "state_machine.tianting_status", RuleDomain.STATE_MACHINE,
        EvidenceStatus.CONFIRMED, 1,
        {
            "dealer": "AFTER_FIRST_DISCARD_REMAINING_16_TING",
            "nondealer": "INITIAL_16_BEFORE_FIRST_DRAW_TING",
            "bonus_fan": 0,
            "bonus_multiplier": 1,
        },
        ImpactLevel.HIGH, P20261006, "huian.rules.first_round",
        note="Tianting is a status marker only; it does not change settlement.",
    ),
    "legality.single_gold_discard_pinghu": _record(
        "legality.single_gold_discard_pinghu", RuleDomain.LEGALITY,
        EvidenceStatus.CONFIRMED, 1, False, ImpactLevel.CRITICAL,
        ("target_room_setting", "player_confirmation"), "huian.rules.engine",
    ),
    "settlement.ordinary_pinghu_multiplier": _record(
        "settlement.ordinary_pinghu_multiplier", RuleDomain.SETTLEMENT,
        EvidenceStatus.CONFIRMED, 1, 1, ImpactLevel.CRITICAL,
        ("match_evidence_001",), "huian.rules.engine",
    ),
    "settlement.ordinary_zimo_multiplier": _record(
        "settlement.ordinary_zimo_multiplier", RuleDomain.SETTLEMENT,
        EvidenceStatus.CONFIRMED, 1, 2, ImpactLevel.CRITICAL,
        ("match_evidence_001", "evidence_b3892b34"), "huian.rules.engine",
    ),
    "match.new_dealer_base": _record(
        "match.new_dealer_base", RuleDomain.MATCH,
        EvidenceStatus.CONFIRMED, 1, 10, ImpactLevel.CRITICAL,
        ("match_evidence_001",), "huian.rules.dealer_base",
    ),
    "match.repeat_dealer_increment": _record(
        "match.repeat_dealer_increment", RuleDomain.MATCH,
        EvidenceStatus.CONFIRMED, 1, 5, ImpactLevel.CRITICAL,
        ("match_evidence_001", "player_2026-09-19"), "huian.rules.dealer_base",
    ),
    "match.normal_dealer_flow": _record(
        "match.normal_dealer_flow", RuleDomain.MATCH,
        EvidenceStatus.CONFIRMED, 1,
        {
            "scope": "ALL_HU_METHODS",
            "dealer_win": "STAY_AND_ADD_5",
            "draw": "STAY_AND_ADD_5",
            "nondealer_win": "SWITCH_AND_RESET_10",
        },
        ImpactLevel.CRITICAL, P20261006, "workspace.simulator.match",
        depends_on=("match.new_dealer_base", "match.repeat_dealer_increment"),
        note="Special win labels never override the winner-based dealer transition.",
    ),
    "match.fixed_eight_hand_tie": _record(
        "match.fixed_eight_hand_tie", RuleDomain.MATCH,
        EvidenceStatus.CONFIRMED, 1,
        {
            "hand_count": 8,
            "equal_final_scores": "TIE",
            "extra_hand": False,
            "dealer_tiebreak": False,
        },
        ImpactLevel.HIGH, P20261006, "workspace.simulator.match",
        note="Equal scores after hand 8 are final; no extra hand or dealer tiebreak.",
    ),
    "settlement.youjin_multiplier": _record(
        "settlement.youjin_multiplier", RuleDomain.SETTLEMENT,
        EvidenceStatus.CONFIRMED, 1, 4, ImpactLevel.CRITICAL,
        ("match_evidence_001", "evidence_66fe863f"), "huian.rules.special_outcomes",
    ),
    "settlement.youjin_full": _record(
        "settlement.youjin_full", RuleDomain.SETTLEMENT,
        EvidenceStatus.UNKNOWN, 1, None, ImpactLevel.CRITICAL,
        (), "huian.rules.special_outcomes",
        depends_on=("settlement.youjin_multiplier",),
        note=(
            "Youjin x4 is confirmed, but the full automatic trigger/payment/terminal "
            "contract remains intentionally unresolved. Manual score observations may "
            "reference this ID without turning them into rule evidence."
        ),
    ),
    "settlement.double_you_multiplier": _record(
        "settlement.double_you_multiplier", RuleDomain.SETTLEMENT,
        EvidenceStatus.CONFIRMED, 1, 8, ImpactLevel.CRITICAL,
        ("match_evidence_002",), "huian.rules.special_outcomes",
    ),
    "settlement.triple_you_multiplier": _record(
        "settlement.triple_you_multiplier", RuleDomain.SETTLEMENT,
        EvidenceStatus.CONFIRMED, 1, 16, ImpactLevel.CRITICAL,
        ("evidence_7bc12fa",), "huian.rules.special_outcomes",
    ),
    "state.youjin_response_must_discard": _record(
        "state.youjin_response_must_discard", RuleDomain.STATE_MACHINE,
        EvidenceStatus.CONFIRMED, 1, True, ImpactLevel.CRITICAL,
        ("player_2026-09-20",), "huian.rules.context",
    ),
    "legality.rob_kong_scope": _record(
        "legality.rob_kong_scope", RuleDomain.LEGALITY,
        EvidenceStatus.CONFIRMED, 1, "ADD_KONG_ONLY", ImpactLevel.CRITICAL,
        ("player_2026-09-18",), "huian.environment",
    ),
    "settlement.rob_kong_multiplier": _record(
        "settlement.rob_kong_multiplier", RuleDomain.SETTLEMENT,
        EvidenceStatus.CONFIRMED, 1, 2, ImpactLevel.HIGH,
        ("player_2026-09-18", "rule_page_2026-09-13"),
        "huian.rules.special_outcomes",
    ),
    "settlement.rob_kong_full": _record(
        "settlement.rob_kong_full", RuleDomain.SETTLEMENT,
        EvidenceStatus.CONFIRMED, 2,
        {"uses_ordinary_zimo_formula": True,
         "failed_added_kong_fan": 0,
         "kong_fee": 0,
         "dealer_flow": "ordinary_hu"},
        ImpactLevel.CRITICAL, ("github_issue_4_confirmed_2026-10-03",),
        "huian.environment",
        depends_on=("legality.rob_kong_scope", "settlement.rob_kong_multiplier"),
        note="Issue #4 / PR #125: original PENG remains; ordinary Zimo x2 and ordinary dealer flow.",
    ),
    "settlement.gang_hu": _record(
        "settlement.gang_hu", RuleDomain.SETTLEMENT,
        EvidenceStatus.CONFIRMED, 2,
        {"uses_ordinary_zimo_multiplier": True,
         "extra_multiplier": 1,
         "kong_fan_additive": True},
        ImpactLevel.CRITICAL, ("player_2026-09-30",), "huian.environment",
        depends_on=("settlement.ordinary_zimo_multiplier",),
    ),
    "settlement.sanjindao_multiplier": _record(
        "settlement.sanjindao_multiplier", RuleDomain.SETTLEMENT,
        EvidenceStatus.CONFIRMED, 1, 3, ImpactLevel.HIGH,
        ("player_confirmation", "rule_page_2026-09-13"),
        "huian.rules.special_outcomes",
    ),
    "settlement.sanjindao_full": _record(
        "settlement.sanjindao_full", RuleDomain.SETTLEMENT,
        EvidenceStatus.CONFIRMED, 2,
        "DEALER_BASE_PLUS_COMPLETED_KONG_FAN_X3", ImpactLevel.CRITICAL,
        P20261006, "huian.rules.special_outcomes",
        depends_on=("settlement.sanjindao_multiplier",),
    ),
    "settlement.qiangjin_full": _record(
        "settlement.qiangjin_full", RuleDomain.SETTLEMENT,
        EvidenceStatus.CONFIRMED, 2,
        {
            "uses_ordinary_fan": True,
            "multiplier": 2,
            "formula": "(current_dealer_base + ordinary_fan) * 2",
            "dealer_flow": "ordinary_hu",
            "virtual_gold_physical_move": False,
        },
        ImpactLevel.CRITICAL, P20261006, "huian.environment.special_apply",
        depends_on=("settlement.ordinary_zimo_multiplier",
                    "legality.qiangjin_virtual_gold_shape",
                    "state_machine.qiangjin_seat_priority"),
    ),
    "settlement.eight_flower_working_multiplier": _record(
        "settlement.eight_flower_working_multiplier", RuleDomain.SETTLEMENT,
        EvidenceStatus.CONFIRMED, 2, 1, ImpactLevel.HIGH,
        P20261006, "huian.rules.special_outcomes",
        note="Player-confirmed settlement; stable historical rule ID retained.",
    ),
    "settlement.eight_flower_working_fixed_fan": _record(
        "settlement.eight_flower_working_fixed_fan", RuleDomain.SETTLEMENT,
        EvidenceStatus.CONFIRMED, 2, 16, ImpactLevel.HIGH,
        P20261006, "huian.rules.special_outcomes",
        note="Player-confirmed settlement; stable historical rule ID retained.",
    ),
    "settlement.eight_flower_real": _record(
        "settlement.eight_flower_real", RuleDomain.SETTLEMENT,
        EvidenceStatus.CONFIRMED, 2,
        "DEALER_BASE_PLUS_FIXED_16_NO_STACKING", ImpactLevel.HIGH,
        P20261006, "huian.rules.special_outcomes",
        depends_on=("settlement.eight_flower_working_multiplier",
                    "settlement.eight_flower_working_fixed_fan"),
    ),
    "settlement.kong_fee": _record(
        "settlement.kong_fee", RuleDomain.SETTLEMENT,
        EvidenceStatus.CONFIRMED, 1, 0, ImpactLevel.HIGH,
        ("player_2026-09-18",), "huian.rules.fan",
    ),
})


DEFAULT_RULE_SNAPSHOT = RuleSnapshot(
    label="huian-target-2026-10-06-first-round-r1",
    records=RULE_REGISTRY,
)
