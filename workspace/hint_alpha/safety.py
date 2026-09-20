"""Fail-closed advisory gate for the internal Hint Alpha build."""
from dataclasses import dataclass
from enum import Enum

from huian.rules import DEFAULT_RULE_SNAPSHOT, EvidenceStatus


class AdvisoryState(str, Enum):
    READY = "READY"
    VISION_PENDING = "VISION_PENDING"
    VISION_UNTRUSTED = "VISION_UNTRUSTED"
    RULE_UNKNOWN = "RULE_UNKNOWN"
    RULE_NOT_CONFIRMED = "RULE_NOT_CONFIRMED"
    NO_LEGAL_ACTIONS = "NO_LEGAL_ACTIONS"
    ERROR = "ERROR"


@dataclass(frozen=True)
class AdvisoryGateResult:
    state: AdvisoryState
    allowed: bool
    reasons: tuple[str, ...] = ()
    rule_snapshot_id: str = DEFAULT_RULE_SNAPSHOT.fingerprint

    @property
    def display_text(self):
        if self.allowed:
            return "可提供提示"
        return "；".join(self.reasons) if self.reasons else self.state.value


class AdvisoryGate:
    """Suppress advice whenever the observed state or required rule is uncertain."""

    def __init__(self, minimum_vision_confidence=0.80, snapshot=DEFAULT_RULE_SNAPSHOT):
        if isinstance(minimum_vision_confidence, bool) or not isinstance(
            minimum_vision_confidence, (int, float)
        ):
            raise ValueError("minimum_vision_confidence must be numeric")
        if not 0 <= float(minimum_vision_confidence) <= 1:
            raise ValueError("minimum_vision_confidence must be between 0 and 1")
        self.minimum_vision_confidence = float(minimum_vision_confidence)
        self.snapshot = snapshot

    def evaluate(
        self,
        *,
        vision_confidence,
        vision_issues=(),
        unresolved_rules=(),
        required_rules=(),
        has_legal_actions=True,
    ):
        unresolved_rules = tuple(dict.fromkeys(unresolved_rules or ()))
        if unresolved_rules:
            return AdvisoryGateResult(
                AdvisoryState.RULE_UNKNOWN,
                False,
                tuple(f"规则未闭环：{rule_id}" for rule_id in unresolved_rules),
                self.snapshot.fingerprint,
            )

        unconfirmed = []
        for rule_id in tuple(dict.fromkeys(required_rules or ())):
            record = self.snapshot.get(rule_id)
            if record.status != EvidenceStatus.CONFIRMED:
                unconfirmed.append(f"{rule_id}={record.status.value}")
        if unconfirmed:
            return AdvisoryGateResult(
                AdvisoryState.RULE_NOT_CONFIRMED,
                False,
                tuple(f"规则非CONFIRMED：{item}" for item in unconfirmed),
                self.snapshot.fingerprint,
            )

        if vision_confidence is None:
            return AdvisoryGateResult(
                AdvisoryState.VISION_PENDING,
                False,
                ("等待稳定识别",),
                self.snapshot.fingerprint,
            )

        issues = tuple(dict.fromkeys(vision_issues or ()))
        if float(vision_confidence) < self.minimum_vision_confidence or issues:
            reasons = []
            if float(vision_confidence) < self.minimum_vision_confidence:
                reasons.append(
                    f"识别置信度 {float(vision_confidence):.2f} "
                    f"< {self.minimum_vision_confidence:.2f}"
                )
            reasons.extend(f"识别问题：{issue}" for issue in issues)
            return AdvisoryGateResult(
                AdvisoryState.VISION_UNTRUSTED,
                False,
                tuple(reasons),
                self.snapshot.fingerprint,
            )

        if not has_legal_actions:
            return AdvisoryGateResult(
                AdvisoryState.NO_LEGAL_ACTIONS,
                False,
                ("当前没有可信合法动作集合",),
                self.snapshot.fingerprint,
            )

        return AdvisoryGateResult(
            AdvisoryState.READY,
            True,
            (),
            self.snapshot.fingerprint,
        )
