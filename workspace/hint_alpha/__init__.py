"""Internal Hint Alpha V0.1 advisory application.

The package is intentionally non-executing: it may capture, recognize, advise,
record evidence, and audit settlement, but it never clicks the game UI.
"""

from .advisor import HintAdvisor, HintDecision
from .current_snapshot_advisor import (
    DiscardShantenHint,
    EffectiveTileHint,
    SnapshotShantenHint,
    analyze_snapshot_shanten,
)
from .current_snapshot_danger import (
    SnapshotDangerHint,
    SnapshotDangerItem,
    analyze_snapshot_danger,
)
from .evidence import EvidenceSession
from .safety import AdvisoryGate, AdvisoryGateResult, AdvisoryState
from .settlement_audit import (
    FanBreakdownItem,
    ObservedSettlement,
    SettlementAuditResult,
    SettlementPrediction,
    audit_settlement,
)

__all__ = [
    "AdvisoryGate",
    "AdvisoryGateResult",
    "AdvisoryState",
    "DiscardShantenHint",
    "EffectiveTileHint",
    "EvidenceSession",
    "FanBreakdownItem",
    "HintAdvisor",
    "HintDecision",
    "SnapshotDangerHint",
    "SnapshotDangerItem",
    "SnapshotShantenHint",
    "ObservedSettlement",
    "SettlementAuditResult",
    "SettlementPrediction",
    "analyze_snapshot_danger",
    "analyze_snapshot_shanten",
    "audit_settlement",
]
