"""Offline calibration of the public ordinary deal-in probability estimator.

Production agents still receive only PlayerObservation.  Calibration labels are
obtained from the Environment response window: after a predicted discard, the
next opponent decision is labelled positive only when AFTER_DISCARD exposes a
legal HU.  The recorder never reads the opponent concealed hand or wall order.
"""
from collections import Counter
from dataclasses import asdict, dataclass

from huian._legacy import env
from workspace.ai import (AgentDecision, ShantenAgent,
                          estimate_ordinary_deal_in_probabilities)
from .core import Simulator


@dataclass(frozen=True)
class DealInCalibrationSample:
    hand_seed: int
    decision_index: int
    actor_seat: int
    tile: str
    predicted_probability: float
    actual_deal_in: bool
    mc_samples: int
    winning_samples: int
    opponent_open_melds: int
    opponent_concealed_count: int
    wall_remaining: int


@dataclass(frozen=True)
class DealInCalibrationBin:
    lower: float
    upper: float
    count: int
    mean_prediction: float | None
    observed_rate: float | None


@dataclass(frozen=True)
class DealInCalibrationReport:
    hands_attempted: int
    hand_status_counts: dict[str, int]
    labelled_discards: int
    positive_deal_ins: int
    censored_discards: int
    prevalence: float | None
    mean_prediction: float | None
    mean_prediction_positive: float | None
    mean_prediction_negative: float | None
    brier_score: float | None
    constant_base_rate_brier: float | None
    auc: float | None
    bins: tuple[DealInCalibrationBin, ...]
    samples: tuple[DealInCalibrationSample, ...]

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class _PendingPrediction:
    hand_seed: int
    decision_index: int
    actor_seat: int
    tile: str
    probability: float
    mc_samples: int
    winning_samples: int
    opponent_open_melds: int
    opponent_concealed_count: int
    wall_remaining: int


class DealInCalibrationRecorder:
    """Shared by both seats so a discard prediction can be labelled next turn."""

    def __init__(self, *, hand_seed, mc_samples=32):
        if type(hand_seed) is not int:
            raise ValueError("hand_seed must be an integer")
        if type(mc_samples) is not int or mc_samples <= 0:
            raise ValueError("mc_samples must be a positive integer")
        self.hand_seed = hand_seed
        self.mc_samples = mc_samples
        self.samples = []
        self.pending = None
        self.decision_index = 0
        self.censored_discards = 0

    def observe_turn(self, observation, legal_actions):
        """Label the other seat previous discard at its response boundary."""
        pending = self.pending
        if pending is None or observation.seat == pending.actor_seat:
            return
        actual = (
            observation.phase == "AFTER_DISCARD"
            and any(action.type == env.ActionType.HU for action in legal_actions)
        )
        self.samples.append(DealInCalibrationSample(
            hand_seed=pending.hand_seed,
            decision_index=pending.decision_index,
            actor_seat=pending.actor_seat,
            tile=pending.tile,
            predicted_probability=pending.probability,
            actual_deal_in=actual,
            mc_samples=pending.mc_samples,
            winning_samples=pending.winning_samples,
            opponent_open_melds=pending.opponent_open_melds,
            opponent_concealed_count=pending.opponent_concealed_count,
            wall_remaining=pending.wall_remaining,
        ))
        self.pending = None

    def record_discard(self, observation, tile):
        if self.pending is not None:
            raise RuntimeError("previous discard prediction has not been labelled")
        mc_seed = (
            self.hand_seed * 1_000_003
            + self.decision_index * 2
            + observation.seat
        )
        estimate = estimate_ordinary_deal_in_probabilities(
            observation, (tile,), samples=self.mc_samples, seed=mc_seed)[0]
        self.pending = _PendingPrediction(
            hand_seed=self.hand_seed,
            decision_index=self.decision_index,
            actor_seat=observation.seat,
            tile=tile,
            probability=estimate.probability,
            mc_samples=estimate.samples,
            winning_samples=estimate.winning_samples,
            opponent_open_melds=estimate.opponent_open_melds,
            opponent_concealed_count=estimate.opponent_concealed_count,
            wall_remaining=observation.wall_remaining,
        )
        self.decision_index += 1

    def finish_hand(self):
        if self.pending is not None:
            self.censored_discards += 1
            self.pending = None


class CalibratingShantenAgent:
    """V0.3 policy plus passive prediction logging; decisions remain V0.3."""

    def __init__(self, recorder, *, seed=None):
        if not isinstance(recorder, DealInCalibrationRecorder):
            raise TypeError("recorder must be DealInCalibrationRecorder")
        self.recorder = recorder
        self.policy = ShantenAgent(seed=seed)

    def choose_decision(self, observation, legal_actions):
        self.recorder.observe_turn(observation, legal_actions)
        decision = self.policy.choose_decision(observation, legal_actions)
        if decision.action.type == env.ActionType.DISCARD:
            self.recorder.record_discard(observation, decision.action.tile)
        return decision


def _mean(values):
    values = tuple(values)
    return sum(values) / len(values) if values else None


def _auc(samples):
    positives = [item.predicted_probability for item in samples if item.actual_deal_in]
    negatives = [item.predicted_probability for item in samples if not item.actual_deal_in]
    if not positives or not negatives:
        return None
    score = 0.0
    for positive in positives:
        for negative in negatives:
            if positive > negative:
                score += 1.0
            elif positive == negative:
                score += 0.5
    return score / (len(positives) * len(negatives))


def summarize_deal_in_calibration(samples, *, hands_attempted=0,
                                  hand_status_counts=None, censored_discards=0):
    samples = tuple(samples)
    if type(hands_attempted) is not int or hands_attempted < 0:
        raise ValueError("hands_attempted must be a nonnegative integer")
    if type(censored_discards) is not int or censored_discards < 0:
        raise ValueError("censored_discards must be a nonnegative integer")
    for item in samples:
        if not isinstance(item, DealInCalibrationSample):
            raise TypeError("samples must contain DealInCalibrationSample")
        if not 0.0 <= item.predicted_probability <= 1.0:
            raise ValueError("predicted probabilities must be in [0, 1]")
    labels = [1.0 if item.actual_deal_in else 0.0 for item in samples]
    predictions = [item.predicted_probability for item in samples]
    positives = sum(int(label) for label in labels)
    prevalence = positives / len(samples) if samples else None
    brier = (_mean((prediction - label) ** 2
                   for prediction, label in zip(predictions, labels))
             if samples else None)
    base_brier = (_mean((prevalence - label) ** 2 for label in labels)
                  if samples else None)

    edges = (0.0, 0.01, 0.05, 0.10, 0.25, 0.50, 1.0000001)
    bins = []
    for lower, upper in zip(edges, edges[1:]):
        members = [item for item in samples
                   if lower <= item.predicted_probability < upper]
        bins.append(DealInCalibrationBin(
            lower=lower, upper=min(upper, 1.0), count=len(members),
            mean_prediction=_mean(item.predicted_probability for item in members),
            observed_rate=_mean(1.0 if item.actual_deal_in else 0.0
                                for item in members),
        ))

    return DealInCalibrationReport(
        hands_attempted=hands_attempted,
        hand_status_counts=dict(sorted((hand_status_counts or {}).items())),
        labelled_discards=len(samples),
        positive_deal_ins=positives,
        censored_discards=censored_discards,
        prevalence=prevalence,
        mean_prediction=_mean(predictions),
        mean_prediction_positive=_mean(
            item.predicted_probability for item in samples if item.actual_deal_in),
        mean_prediction_negative=_mean(
            item.predicted_probability for item in samples if not item.actual_deal_in),
        brier_score=brier,
        constant_base_rate_brier=base_brier,
        auc=_auc(samples),
        bins=tuple(bins),
        samples=samples,
    )


def run_ordinary_deal_in_calibration(
        seeds=range(20), *, mc_samples=32, max_steps=1000, simulator=None):
    """Run V0.3-vs-V0.3 hands and calibrate chosen-discard risk predictions."""
    seeds = tuple(seeds)
    if not seeds or any(type(seed) is not int for seed in seeds):
        raise ValueError("seeds must be a nonempty iterable of integers")
    if type(max_steps) is not int or max_steps <= 0:
        raise ValueError("max_steps must be a positive integer")
    if type(mc_samples) is not int or mc_samples <= 0:
        raise ValueError("mc_samples must be a positive integer")
    simulator = simulator if simulator is not None else Simulator()
    status_counts = Counter()
    all_samples = []
    censored = 0
    for seed in seeds:
        recorder = DealInCalibrationRecorder(
            hand_seed=seed, mc_samples=mc_samples)
        agents = (
            CalibratingShantenAgent(recorder, seed=seed * 2),
            CalibratingShantenAgent(recorder, seed=seed * 2 + 1),
        )
        result = simulator.run_normal_hand(
            seed=seed, agents=agents, max_steps=max_steps)
        recorder.finish_hand()
        status_counts[result.status] += 1
        all_samples.extend(recorder.samples)
        censored += recorder.censored_discards
    return summarize_deal_in_calibration(
        all_samples, hands_attempted=len(seeds),
        hand_status_counts=status_counts, censored_discards=censored)
