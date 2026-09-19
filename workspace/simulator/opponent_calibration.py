"""Offline calibration of the public ordinary deal-in probability estimator.

Production agents still receive only PlayerObservation.  Calibration labels are
obtained from the Environment response window: after a predicted discard, the
next opponent decision is labelled positive only when AFTER_DISCARD exposes a
legal HU.  The recorder never reads the opponent concealed hand or wall order.
"""
from collections import Counter
from dataclasses import asdict, dataclass

from huian._legacy import env
from workspace.ai import (AgentDecision, ShantenAgent, TenpaiRiskTieBreakAgent,
                          estimate_ordinary_deal_in_probabilities,
                          estimate_tenpai_wait_risk_scores,
                          is_ordinary_ron_tenpai)
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


@dataclass(frozen=True)
class TenpaiRiskCalibrationSample:
    hand_seed: int
    decision_index: int
    actor_seat: int
    tile: str
    risk_score: float
    actual_deal_in: bool
    template_samples: int
    matching_templates: int
    generation_attempts: int
    opponent_open_melds: int
    opponent_concealed_count: int
    wall_remaining: int


@dataclass(frozen=True)
class TenpaiRiskBin:
    lower: float
    upper: float
    count: int
    mean_score: float | None
    observed_deal_in_rate: float | None


@dataclass(frozen=True)
class TenpaiRiskCalibrationReport:
    hands_attempted: int
    hand_status_counts: dict[str, int]
    labelled_discards: int
    positive_deal_ins: int
    censored_discards: int
    prevalence: float | None
    mean_score: float | None
    mean_score_positive: float | None
    mean_score_negative: float | None
    auc: float | None
    mean_generation_attempts: float | None
    bins: tuple[TenpaiRiskBin, ...]
    samples: tuple[TenpaiRiskCalibrationSample, ...]

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class _PendingRiskScore:
    hand_seed: int
    decision_index: int
    actor_seat: int
    tile: str
    risk_score: float
    template_samples: int
    matching_templates: int
    generation_attempts: int
    opponent_open_melds: int
    opponent_concealed_count: int
    wall_remaining: int


class TenpaiRiskCalibrationRecorder:
    """Passive recorder for a non-probabilistic tenpai-conditioned risk score."""

    def __init__(self, *, hand_seed, template_samples=16):
        if type(hand_seed) is not int:
            raise ValueError("hand_seed must be an integer")
        if type(template_samples) is not int or template_samples <= 0:
            raise ValueError("template_samples must be a positive integer")
        self.hand_seed = hand_seed
        self.template_samples = template_samples
        self.samples = []
        self.pending = None
        self.decision_index = 0
        self.censored_discards = 0

    def observe_turn(self, observation, legal_actions):
        pending = self.pending
        if pending is None or observation.seat == pending.actor_seat:
            return
        actual = (
            observation.phase == "AFTER_DISCARD"
            and any(action.type == env.ActionType.HU for action in legal_actions)
        )
        self.samples.append(TenpaiRiskCalibrationSample(
            hand_seed=pending.hand_seed,
            decision_index=pending.decision_index,
            actor_seat=pending.actor_seat,
            tile=pending.tile,
            risk_score=pending.risk_score,
            actual_deal_in=actual,
            template_samples=pending.template_samples,
            matching_templates=pending.matching_templates,
            generation_attempts=pending.generation_attempts,
            opponent_open_melds=pending.opponent_open_melds,
            opponent_concealed_count=pending.opponent_concealed_count,
            wall_remaining=pending.wall_remaining,
        ))
        self.pending = None

    def record_discard(self, observation, tile):
        if self.pending is not None:
            raise RuntimeError("previous risk score has not been labelled")
        model_seed = (
            self.hand_seed * 1_000_033
            + self.decision_index * 2
            + observation.seat
        )
        estimate = estimate_tenpai_wait_risk_scores(
            observation, (tile,), samples=self.template_samples,
            seed=model_seed)[0]
        self.pending = _PendingRiskScore(
            hand_seed=self.hand_seed,
            decision_index=self.decision_index,
            actor_seat=observation.seat,
            tile=tile,
            risk_score=estimate.risk_score,
            template_samples=estimate.templates_used,
            matching_templates=estimate.matching_templates,
            generation_attempts=estimate.generation_attempts,
            opponent_open_melds=estimate.opponent_open_melds,
            opponent_concealed_count=estimate.opponent_concealed_count,
            wall_remaining=observation.wall_remaining,
        )
        self.decision_index += 1

    def finish_hand(self):
        if self.pending is not None:
            self.censored_discards += 1
            self.pending = None


class CalibratingTenpaiRiskShantenAgent:
    """Unchanged V0.3 decisions plus passive tenpai-risk scoring."""

    def __init__(self, recorder, *, seed=None):
        if not isinstance(recorder, TenpaiRiskCalibrationRecorder):
            raise TypeError("recorder must be TenpaiRiskCalibrationRecorder")
        self.recorder = recorder
        self.policy = ShantenAgent(seed=seed)

    def choose_decision(self, observation, legal_actions):
        self.recorder.observe_turn(observation, legal_actions)
        decision = self.policy.choose_decision(observation, legal_actions)
        if decision.action.type == env.ActionType.DISCARD:
            self.recorder.record_discard(observation, decision.action.tile)
        return decision


def _auc_risk(samples):
    positives = [item.risk_score for item in samples if item.actual_deal_in]
    negatives = [item.risk_score for item in samples if not item.actual_deal_in]
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


def summarize_tenpai_risk_calibration(
        samples, *, hands_attempted=0, hand_status_counts=None,
        censored_discards=0):
    samples = tuple(samples)
    if type(hands_attempted) is not int or hands_attempted < 0:
        raise ValueError("hands_attempted must be a nonnegative integer")
    if type(censored_discards) is not int or censored_discards < 0:
        raise ValueError("censored_discards must be a nonnegative integer")
    for item in samples:
        if not isinstance(item, TenpaiRiskCalibrationSample):
            raise TypeError("samples must contain TenpaiRiskCalibrationSample")
        if not 0.0 <= item.risk_score <= 1.0:
            raise ValueError("risk scores must be in [0, 1]")
    positives = sum(item.actual_deal_in for item in samples)
    prevalence = positives / len(samples) if samples else None

    edges = (0.0, 0.01, 0.05, 0.10, 0.25, 0.50, 1.0000001)
    bins = []
    for lower, upper in zip(edges, edges[1:]):
        members = [item for item in samples
                   if lower <= item.risk_score < upper]
        bins.append(TenpaiRiskBin(
            lower=lower, upper=min(upper, 1.0), count=len(members),
            mean_score=_mean(item.risk_score for item in members),
            observed_deal_in_rate=_mean(
                1.0 if item.actual_deal_in else 0.0 for item in members),
        ))

    return TenpaiRiskCalibrationReport(
        hands_attempted=hands_attempted,
        hand_status_counts=dict(sorted((hand_status_counts or {}).items())),
        labelled_discards=len(samples),
        positive_deal_ins=int(positives),
        censored_discards=censored_discards,
        prevalence=prevalence,
        mean_score=_mean(item.risk_score for item in samples),
        mean_score_positive=_mean(
            item.risk_score for item in samples if item.actual_deal_in),
        mean_score_negative=_mean(
            item.risk_score for item in samples if not item.actual_deal_in),
        auc=_auc_risk(samples),
        mean_generation_attempts=_mean(
            item.generation_attempts for item in samples),
        bins=tuple(bins),
        samples=samples,
    )


def run_tenpai_risk_calibration(
        seeds=range(20), *, template_samples=16, max_steps=1000, simulator=None):
    """Run unchanged V0.3-vs-V0.3 hands and evaluate relative wait-risk ranking."""
    seeds = tuple(seeds)
    if not seeds or any(type(seed) is not int for seed in seeds):
        raise ValueError("seeds must be a nonempty iterable of integers")
    if type(max_steps) is not int or max_steps <= 0:
        raise ValueError("max_steps must be a positive integer")
    if type(template_samples) is not int or template_samples <= 0:
        raise ValueError("template_samples must be a positive integer")
    simulator = simulator if simulator is not None else Simulator()
    status_counts = Counter()
    all_samples = []
    censored = 0
    for seed in seeds:
        recorder = TenpaiRiskCalibrationRecorder(
            hand_seed=seed, template_samples=template_samples)
        agents = (
            CalibratingTenpaiRiskShantenAgent(recorder, seed=seed * 2),
            CalibratingTenpaiRiskShantenAgent(recorder, seed=seed * 2 + 1),
        )
        result = simulator.run_normal_hand(
            seed=seed, agents=agents, max_steps=max_steps)
        recorder.finish_hand()
        status_counts[result.status] += 1
        all_samples.extend(recorder.samples)
        censored += recorder.censored_discards
    return summarize_tenpai_risk_calibration(
        all_samples, hands_attempted=len(seeds),
        hand_status_counts=status_counts, censored_discards=censored)


@dataclass(frozen=True)
class TenpaiStateCalibrationSample:
    """One discard-decision snapshot with a hidden-truth tenpai label.

    Predictor features come only from PlayerObservation. The actual tenpai
    label comes from the simulator-truth state supplied to the offline observer.
    """

    hand_seed: int
    decision_index: int
    actor_seat: int
    actual_opponent_tenpai: bool
    wall_remaining: int
    actor_discards: int
    opponent_discards: int
    total_discards: int
    opponent_open_melds: int
    opponent_flowers: int
    actor_is_dealer: bool


class TenpaiStateRecorder:
    """Offline-only recorder using simulator truth for labels, never features."""

    def __init__(self, *, hand_seed):
        if type(hand_seed) is not int:
            raise ValueError("hand_seed must be an integer")
        self.hand_seed = hand_seed
        self.samples = []
        self.decision_index = 0

    def observe_decision(self, truth_state, observation, legal_actions):
        if not any(action.type == env.ActionType.DISCARD for action in legal_actions):
            return
        opponent = 1 - observation.seat
        open_melds = len(observation.melds[opponent])
        actual = is_ordinary_ron_tenpai(
            truth_state.hands[opponent],
            gold_tile=truth_state.gold_tile,
            open_melds=open_melds,
        )
        self.samples.append(TenpaiStateCalibrationSample(
            hand_seed=self.hand_seed,
            decision_index=self.decision_index,
            actor_seat=observation.seat,
            actual_opponent_tenpai=actual,
            wall_remaining=observation.wall_remaining,
            actor_discards=len(observation.discards[observation.seat]),
            opponent_discards=len(observation.discards[opponent]),
            total_discards=sum(len(river) for river in observation.discards),
            opponent_open_melds=open_melds,
            opponent_flowers=len(observation.flowers[opponent]),
            actor_is_dealer=(observation.dealer == observation.seat),
        ))
        self.decision_index += 1


@dataclass(frozen=True)
class PublicTenpaiProbabilityModel:
    """Transparent empirical P(opponent tenpai | public phase/open melds)."""

    wall_bucket_size: int
    prior_strength: float
    min_cell_count: int
    global_probability: float
    wall_rates: dict
    wall_counts: dict
    wall_positives: dict
    cell_rates: dict
    cell_counts: dict
    cell_positives: dict

    def _wall_bucket(self, wall_remaining):
        return max(0, (wall_remaining - 16) // self.wall_bucket_size)

    def predict(self, *, wall_remaining, opponent_open_melds):
        if type(wall_remaining) is not int or wall_remaining < 0:
            raise ValueError("wall_remaining must be a nonnegative integer")
        if type(opponent_open_melds) is not int or not 0 <= opponent_open_melds <= 5:
            raise ValueError("opponent_open_melds must be an integer from zero to five")
        bucket = self._wall_bucket(wall_remaining)
        cell = (bucket, opponent_open_melds)
        if self.cell_counts.get(cell, 0) >= self.min_cell_count:
            return self.cell_rates[cell]
        return self.wall_rates.get(bucket, self.global_probability)


@dataclass(frozen=True)
class TenpaiProbabilityBin:
    lower: float
    upper: float
    count: int
    mean_prediction: float | None
    observed_rate: float | None


@dataclass(frozen=True)
class TenpaiProbabilityCell:
    wall_bucket: int
    opponent_open_melds: int | None
    count: int
    positives: int
    probability: float


@dataclass(frozen=True)
class TenpaiStateCalibrationReport:
    train_hands_attempted: int
    test_hands_attempted: int
    train_status_counts: dict[str, int]
    test_status_counts: dict[str, int]
    train_samples: int
    test_samples: int
    train_prevalence: float
    test_prevalence: float
    mean_prediction: float
    mean_prediction_positive: float | None
    mean_prediction_negative: float | None
    brier_score: float
    constant_train_rate_brier: float
    auc: float | None
    bins: tuple[TenpaiProbabilityBin, ...]
    wall_cells: tuple[TenpaiProbabilityCell, ...]
    meld_cells: tuple[TenpaiProbabilityCell, ...]

    def to_dict(self):
        return asdict(self)


def _tenpai_wall_bucket(wall_remaining, bucket_size):
    return max(0, (wall_remaining - 16) // bucket_size)


def fit_public_tenpai_probability_model(
        samples, *, wall_bucket_size=16, prior_strength=8.0,
        min_cell_count=30):
    """Fit a smoothed, inspectable public-state probability table."""
    samples = tuple(samples)
    if not samples:
        raise ValueError("samples must be nonempty")
    if type(wall_bucket_size) is not int or wall_bucket_size <= 0:
        raise ValueError("wall_bucket_size must be a positive integer")
    if isinstance(prior_strength, bool) or prior_strength <= 0:
        raise ValueError("prior_strength must be positive")
    if type(min_cell_count) is not int or min_cell_count <= 0:
        raise ValueError("min_cell_count must be a positive integer")
    if any(not isinstance(item, TenpaiStateCalibrationSample) for item in samples):
        raise TypeError("samples must contain TenpaiStateCalibrationSample")

    positives = sum(item.actual_opponent_tenpai for item in samples)
    global_probability = positives / len(samples)
    wall_counts = Counter()
    wall_positives = Counter()
    cell_counts = Counter()
    cell_positives = Counter()
    for item in samples:
        bucket = _tenpai_wall_bucket(item.wall_remaining, wall_bucket_size)
        cell = (bucket, item.opponent_open_melds)
        wall_counts[bucket] += 1
        cell_counts[cell] += 1
        if item.actual_opponent_tenpai:
            wall_positives[bucket] += 1
            cell_positives[cell] += 1

    def smooth(pos, count):
        return (
            pos + prior_strength * global_probability
        ) / (count + prior_strength)

    wall_rates = {
        bucket: smooth(wall_positives[bucket], count)
        for bucket, count in wall_counts.items()
    }
    cell_rates = {
        cell: smooth(cell_positives[cell], count)
        for cell, count in cell_counts.items()
    }
    return PublicTenpaiProbabilityModel(
        wall_bucket_size=wall_bucket_size,
        prior_strength=float(prior_strength),
        min_cell_count=min_cell_count,
        global_probability=global_probability,
        wall_rates=dict(wall_rates),
        wall_counts=dict(wall_counts),
        wall_positives=dict(wall_positives),
        cell_rates=dict(cell_rates),
        cell_counts=dict(cell_counts),
        cell_positives=dict(cell_positives),
    )


def _auc_from_predictions(predictions, labels):
    rows = sorted(zip(predictions, labels), key=lambda item: item[0])
    positive_count = sum(labels)
    negative_count = len(labels) - positive_count
    if not positive_count or not negative_count:
        return None
    positive_rank_sum = 0.0
    index = 0
    rank = 1
    while index < len(rows):
        end = index + 1
        while end < len(rows) and rows[end][0] == rows[index][0]:
            end += 1
        average_rank = (rank + (rank + end - index - 1)) / 2
        positive_rank_sum += average_rank * sum(
            label for _, label in rows[index:end])
        rank += end - index
        index = end
    return (
        positive_rank_sum - positive_count * (positive_count + 1) / 2
    ) / (positive_count * negative_count)


def evaluate_public_tenpai_probability_model(
        model, samples, *, train_hands_attempted=0, test_hands_attempted=0,
        train_status_counts=None, test_status_counts=None):
    """Evaluate a fitted table on held-out public-state samples."""
    if not isinstance(model, PublicTenpaiProbabilityModel):
        raise TypeError("model must be PublicTenpaiProbabilityModel")
    samples = tuple(samples)
    if not samples:
        raise ValueError("samples must be nonempty")
    if any(not isinstance(item, TenpaiStateCalibrationSample) for item in samples):
        raise TypeError("samples must contain TenpaiStateCalibrationSample")

    labels = [1 if item.actual_opponent_tenpai else 0 for item in samples]
    predictions = [
        model.predict(
            wall_remaining=item.wall_remaining,
            opponent_open_melds=item.opponent_open_melds)
        for item in samples
    ]
    test_prevalence = sum(labels) / len(labels)
    brier = _mean(
        (prediction - label) ** 2
        for prediction, label in zip(predictions, labels))
    constant_brier = _mean(
        (model.global_probability - label) ** 2 for label in labels)

    edges = (0.0, 0.05, 0.10, 0.20, 0.40, 0.60, 0.80, 1.0000001)
    bins = []
    for lower, upper in zip(edges, edges[1:]):
        members = [
            (prediction, label)
            for prediction, label in zip(predictions, labels)
            if lower <= prediction < upper
        ]
        bins.append(TenpaiProbabilityBin(
            lower=lower,
            upper=min(upper, 1.0),
            count=len(members),
            mean_prediction=_mean(prediction for prediction, _ in members),
            observed_rate=_mean(label for _, label in members),
        ))

    wall_cells = tuple(
        TenpaiProbabilityCell(
            wall_bucket=bucket,
            opponent_open_melds=None,
            count=model.wall_counts[bucket],
            positives=model.wall_positives.get(bucket, 0),
            probability=model.wall_rates[bucket],
        )
        for bucket in sorted(model.wall_counts)
    )
    meld_cells = tuple(
        TenpaiProbabilityCell(
            wall_bucket=bucket,
            opponent_open_melds=melds,
            count=model.cell_counts[(bucket, melds)],
            positives=model.cell_positives.get((bucket, melds), 0),
            probability=model.cell_rates[(bucket, melds)],
        )
        for bucket, melds in sorted(model.cell_counts)
        if model.cell_counts[(bucket, melds)] >= model.min_cell_count
    )

    return TenpaiStateCalibrationReport(
        train_hands_attempted=train_hands_attempted,
        test_hands_attempted=test_hands_attempted,
        train_status_counts=dict(sorted((train_status_counts or {}).items())),
        test_status_counts=dict(sorted((test_status_counts or {}).items())),
        train_samples=sum(model.wall_counts.values()),
        test_samples=len(samples),
        train_prevalence=model.global_probability,
        test_prevalence=test_prevalence,
        mean_prediction=_mean(predictions),
        mean_prediction_positive=_mean(
            prediction for prediction, label in zip(predictions, labels) if label),
        mean_prediction_negative=_mean(
            prediction for prediction, label in zip(predictions, labels) if not label),
        brier_score=brier,
        constant_train_rate_brier=constant_brier,
        auc=_auc_from_predictions(predictions, labels),
        bins=tuple(bins),
        wall_cells=wall_cells,
        meld_cells=meld_cells,
    )


def collect_tenpai_state_samples(
        seeds=range(20), *, max_steps=1000, simulator=None):
    """Collect hidden-truth tenpai labels on unchanged CurrentAgent-style play."""
    seeds = tuple(seeds)
    if not seeds or any(type(seed) is not int for seed in seeds):
        raise ValueError("seeds must be a nonempty iterable of integers")
    if type(max_steps) is not int or max_steps <= 0:
        raise ValueError("max_steps must be a positive integer")
    simulator = simulator if simulator is not None else Simulator()
    status_counts = Counter()
    rows = []
    for seed in seeds:
        recorder = TenpaiStateRecorder(hand_seed=seed)
        agents = (
            TenpaiRiskTieBreakAgent(seed=seed * 2, template_samples=32),
            TenpaiRiskTieBreakAgent(seed=seed * 2 + 1, template_samples=32),
        )
        result = simulator.run_normal_hand(
            seed=seed,
            agents=agents,
            max_steps=max_steps,
            decision_observer=recorder.observe_decision,
        )
        status_counts[result.status] += 1
        rows.extend(recorder.samples)
    return tuple(rows), dict(sorted(status_counts.items()))


def run_public_tenpai_probability_calibration(
        train_seeds, test_seeds, *, max_steps=1000, simulator=None,
        wall_bucket_size=16, prior_strength=8.0, min_cell_count=30):
    """Fit on one seed set and evaluate public tenpai probability held out."""
    train_seeds = tuple(train_seeds)
    test_seeds = tuple(test_seeds)
    if set(train_seeds) & set(test_seeds):
        raise ValueError("train_seeds and test_seeds must be disjoint")
    simulator = simulator if simulator is not None else Simulator()
    train, train_status = collect_tenpai_state_samples(
        train_seeds, max_steps=max_steps, simulator=simulator)
    test, test_status = collect_tenpai_state_samples(
        test_seeds, max_steps=max_steps, simulator=simulator)
    model = fit_public_tenpai_probability_model(
        train,
        wall_bucket_size=wall_bucket_size,
        prior_strength=prior_strength,
        min_cell_count=min_cell_count,
    )
    report = evaluate_public_tenpai_probability_model(
        model,
        test,
        train_hands_attempted=len(train_seeds),
        test_hands_attempted=len(test_seeds),
        train_status_counts=train_status,
        test_status_counts=test_status,
    )
    return model, report
