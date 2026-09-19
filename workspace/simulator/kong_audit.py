"""Passive collection of public-information kong opportunity projections."""
from collections import Counter
from dataclasses import asdict, dataclass

from workspace.ai.kong import analyze_kong_actions


@dataclass(frozen=True)
class KongAuditSummary:
    decisions_observed: int
    opportunities: int
    by_action_type: dict[str, int]
    by_relation: dict[str, int]
    by_blocker: dict[str, int]
    unblocked: int

    def to_dict(self):
        return asdict(self)


class KongAuditRecorder:
    """A ``Simulator.decision_observer`` that never changes agent decisions."""

    def __init__(self):
        self.decisions_observed = 0
        self.opportunities = []

    def observe_decision(self, _truth, observation, legal_actions):
        self.decisions_observed += 1
        self.opportunities.extend(analyze_kong_actions(observation, legal_actions))

    def summary(self):
        by_action = Counter(item.action_type for item in self.opportunities)
        by_relation = Counter(item.structural_relation for item in self.opportunities)
        by_blocker = Counter(
            blocker for item in self.opportunities for blocker in item.blockers)
        return KongAuditSummary(
            decisions_observed=self.decisions_observed,
            opportunities=len(self.opportunities),
            by_action_type=dict(sorted(by_action.items())),
            by_relation=dict(sorted(by_relation.items())),
            by_blocker=dict(sorted(by_blocker.items())),
            unblocked=sum(not item.blockers for item in self.opportunities),
        )
