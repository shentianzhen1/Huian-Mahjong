"""Evidence-scoped registry for Huian special outcomes.

This module centralizes what is actually known about each special outcome.
It deliberately separates:
- trigger/window evidence,
- multiplier evidence,
- settlement readiness.

A special can therefore be legal to declare while still refusing to settle
until the missing payment/dealer-flow rule is confirmed.
"""
from dataclasses import dataclass
from types import MappingProxyType

from .config import EvidenceStatus


@dataclass(frozen=True)
class SpecialOutcomeProfile:
    key: str
    declaration_phase: str | None
    multiplier: int | None
    multiplier_status: EvidenceStatus
    settlement_rule_id: str | None
    settlement_ready: bool
    project_rule: bool = False
    note: str = ""

    @property
    def action_metadata(self):
        data = {
            "special": self.key,
            "multiplier_evidence": self.multiplier_status.value,
            "settlement_ready": self.settlement_ready,
        }
        if self.multiplier is not None:
            data["multiplier"] = self.multiplier
        if self.settlement_rule_id is not None:
            data["settlement_rule_id"] = self.settlement_rule_id
        if self.project_rule:
            data["project_rule"] = True
        return data


_SPECIAL_OUTCOMES = {
    "QIANGJIN": SpecialOutcomeProfile(
        key="QIANGJIN",
        declaration_phase="QIANGJIN_DECLARED",
        multiplier=None,
        multiplier_status=EvidenceStatus.UNKNOWN,
        settlement_rule_id="qiangjin_settlement",
        settlement_ready=False,
        note="Window ownership/PASS are confirmed; hand shape and settlement are not.",
    ),
    "SANJINDAO": SpecialOutcomeProfile(
        key="SANJINDAO",
        declaration_phase="SANJINDAO_DECLARED",
        multiplier=3,
        multiplier_status=EvidenceStatus.CONFIRMED,
        settlement_rule_id="sanjindao_settlement",
        settlement_ready=False,
        note="One-shot third-gold trigger and x3 are confirmed; payment/dealer flow remain unknown.",
    ),
    "EIGHT_FLOWER_YOU": SpecialOutcomeProfile(
        key="EIGHT_FLOWER_YOU",
        declaration_phase="EIGHT_FLOWER_YOU_DECLARED",
        multiplier=2,
        multiplier_status=EvidenceStatus.WORKING,
        settlement_rule_id="eight_flower_real_multiplier",
        settlement_ready=True,
        project_rule=True,
        note="Project provisional x2; real-room multiplier still awaits direct evidence.",
    ),
    "YOUJIN": SpecialOutcomeProfile(
        key="YOUJIN",
        declaration_phase=None,
        multiplier=4,
        multiplier_status=EvidenceStatus.CONFIRMED,
        settlement_rule_id="youjin_trigger",
        settlement_ready=False,
        note="x4 observed; executable trigger/state-machine edge cases remain incomplete.",
    ),
    "DOUBLE_YOU": SpecialOutcomeProfile(
        key="DOUBLE_YOU",
        declaration_phase=None,
        multiplier=8,
        multiplier_status=EvidenceStatus.CONFIRMED,
        settlement_rule_id="double_you_entry",
        settlement_ready=False,
        note="x8 confirmed; executable entry/state-machine edge cases remain incomplete.",
    ),
    "TRIPLE_YOU": SpecialOutcomeProfile(
        key="TRIPLE_YOU",
        declaration_phase=None,
        multiplier=16,
        multiplier_status=EvidenceStatus.CONFIRMED,
        settlement_rule_id="triple_you_sequence",
        settlement_ready=False,
        note="x16 and +608 example confirmed; full upgrade state machine remains incomplete.",
    ),
    "ROB_KONG_HU": SpecialOutcomeProfile(
        key="ROB_KONG_HU",
        declaration_phase="ROB_KONG_HU_DECLARED",
        multiplier=None,
        multiplier_status=EvidenceStatus.UNKNOWN,
        settlement_rule_id="ROB_KONG_SCORING_UNKNOWN",
        settlement_ready=False,
    ),
    "GANG_HU": SpecialOutcomeProfile(
        key="GANG_HU",
        declaration_phase="HU_DECLARED",
        multiplier=None,
        multiplier_status=EvidenceStatus.UNKNOWN,
        settlement_rule_id="GANG_HU_SCORING_UNKNOWN",
        settlement_ready=False,
    ),
}

SPECIAL_OUTCOMES = MappingProxyType(_SPECIAL_OUTCOMES)


def special_outcome_profile(key):
    try:
        return SPECIAL_OUTCOMES[key]
    except KeyError as exc:
        raise ValueError(f"Unknown special outcome profile: {key}") from exc
