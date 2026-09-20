"""Prediction-vs-observation audit for fan and terminal settlement."""
from dataclasses import asdict, dataclass

from huian.rules.dealer_base import MATCH_TOTAL_SCORE


@dataclass(frozen=True)
class FanBreakdownItem:
    label: str
    fan: int
    rule_id: str | None = None

    def __post_init__(self):
        if not self.label:
            raise ValueError("fan label must not be empty")
        if isinstance(self.fan, bool) or not isinstance(self.fan, int) or self.fan < 0:
            raise ValueError("fan must be a nonnegative integer")


@dataclass(frozen=True)
class SettlementPrediction:
    current_dealer_base: int
    fan_total: int
    multiplier: int
    fan_breakdown: tuple[FanBreakdownItem, ...] = ()
    outcome: str | None = None

    def __post_init__(self):
        for name, value in (
            ("current_dealer_base", self.current_dealer_base),
            ("fan_total", self.fan_total),
            ("multiplier", self.multiplier),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.multiplier < 1:
            raise ValueError("multiplier must be positive")
        if self.fan_breakdown:
            item_total = sum(item.fan for item in self.fan_breakdown)
            if item_total != self.fan_total:
                raise ValueError("fan_breakdown does not sum to fan_total")

    @property
    def predicted_net(self):
        return (self.current_dealer_base + self.fan_total) * self.multiplier


@dataclass(frozen=True)
class ObservedSettlement:
    winner: int
    scores_before: tuple[int, int] | None
    scores_after: tuple[int, int] | None
    displayed_fan: int | None = None
    displayed_multiplier: int | None = None

    def __post_init__(self):
        if self.winner not in (0, 1):
            raise ValueError("winner must be seat 0 or 1")
        for name, pair in (("scores_before", self.scores_before), ("scores_after", self.scores_after)):
            if pair is None:
                continue
            if (
                not isinstance(pair, tuple)
                or len(pair) != 2
                or any(isinstance(value, bool) or not isinstance(value, int) for value in pair)
            ):
                raise ValueError(f"{name} must be a two-integer tuple or None")
        for name, value in (
            ("displayed_fan", self.displayed_fan),
            ("displayed_multiplier", self.displayed_multiplier),
        ):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{name} must be a nonnegative integer or None")

    @property
    def observed_net(self):
        if self.scores_before is None or self.scores_after is None:
            return None
        return self.scores_after[self.winner] - self.scores_before[self.winner]


@dataclass(frozen=True)
class SettlementAuditResult:
    status: str
    prediction: SettlementPrediction
    observation: ObservedSettlement
    predicted_net: int
    observed_net: int | None
    net_match: bool | None
    fan_match: bool | None
    multiplier_match: bool | None
    differences: tuple[str, ...]
    unresolved_rules: tuple[str, ...] = ()

    def to_dict(self):
        return asdict(self)


def _scores_physical(pair):
    return (
        pair is not None
        and all(0 <= value <= MATCH_TOTAL_SCORE for value in pair)
        and sum(pair) == MATCH_TOTAL_SCORE
    )


def audit_settlement(prediction, observation, *, unresolved_rules=()):
    if not isinstance(prediction, SettlementPrediction):
        raise TypeError("prediction must be SettlementPrediction")
    if not isinstance(observation, ObservedSettlement):
        raise TypeError("observation must be ObservedSettlement")
    unresolved = tuple(dict.fromkeys(unresolved_rules or ()))
    if unresolved:
        return SettlementAuditResult(
            status="UNSUPPORTED",
            prediction=prediction,
            observation=observation,
            predicted_net=prediction.predicted_net,
            observed_net=observation.observed_net,
            net_match=None,
            fan_match=None,
            multiplier_match=None,
            differences=tuple(f"规则未闭环：{item}" for item in unresolved),
            unresolved_rules=unresolved,
        )

    if not _scores_physical(observation.scores_before) or not _scores_physical(
        observation.scores_after
    ):
        return SettlementAuditResult(
            status="UNREADABLE",
            prediction=prediction,
            observation=observation,
            predicted_net=prediction.predicted_net,
            observed_net=observation.observed_net,
            net_match=None,
            fan_match=None,
            multiplier_match=None,
            differences=("结算前后比分未形成可信2000分守恒读数",),
        )

    observed_net = observation.observed_net
    loser = 1 - observation.winner
    zero_sum = (
        observation.scores_after[loser] - observation.scores_before[loser]
        == -observed_net
    )
    differences = []
    net_match = zero_sum and observed_net == prediction.predicted_net
    if not zero_sum:
        differences.append("实际比分变化不是零和")
    if observed_net != prediction.predicted_net:
        differences.append(
            f"净分预测{prediction.predicted_net}，实际{observed_net}"
        )

    fan_match = None
    if observation.displayed_fan is not None:
        fan_match = observation.displayed_fan == prediction.fan_total
        if not fan_match:
            differences.append(
                f"番数预测{prediction.fan_total}，界面{observation.displayed_fan}"
            )

    multiplier_match = None
    if observation.displayed_multiplier is not None:
        multiplier_match = observation.displayed_multiplier == prediction.multiplier
        if not multiplier_match:
            differences.append(
                f"倍率预测×{prediction.multiplier}，界面×{observation.displayed_multiplier}"
            )

    return SettlementAuditResult(
        status="MATCH" if not differences else "MISMATCH",
        prediction=prediction,
        observation=observation,
        predicted_net=prediction.predicted_net,
        observed_net=observed_net,
        net_match=net_match,
        fan_match=fan_match,
        multiplier_match=multiplier_match,
        differences=tuple(differences),
    )
