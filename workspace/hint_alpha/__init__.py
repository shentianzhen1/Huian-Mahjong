"""Internal Hint Alpha V0.1 advisory application.

The package is intentionally non-executing: it may capture, recognize, advise,
record evidence, and audit settlement, but it never clicks the game UI.
"""

from .advisor import HintAdvisor, HintDecision
from .evidence import EvidenceSession
from .safety import AdvisoryGate, AdvisoryGateResult, AdvisoryState
from .timeline_bridge import build_timeline_draft, load_closed_session, write_timeline_draft
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
    "EvidenceSession",
    "FanBreakdownItem",
    "HintAdvisor",
    "HintDecision",
    "ObservedSettlement",
    "SettlementAuditResult",
    "SettlementPrediction",
    "audit_settlement",
    "build_timeline_draft",
    "load_closed_session",
    "write_timeline_draft",
]
