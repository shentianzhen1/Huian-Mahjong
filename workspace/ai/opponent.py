"""Public-information Monte Carlo opponent model for ordinary discard Hu.

The estimator never reads the real opponent concealed hand or future wall order.
It samples plausible concealed base-tile hands from the physically unseen tile
pool implied by the acting player hand plus public rivers/melds, then evaluates
ordinary discard-Hu structure under the target single-gold/two-gold limits.

This models only the ordinary subset. Youjin/Sanjindao/Qiangjin and other
special-state permissions are deliberately outside this probability.
"""
from collections import Counter
from dataclasses import dataclass
from random import Random

from huian._legacy import env
from huian.rules import HuianRules
from huian.rules.config import EvidenceStatus
from huian.rules.context import HuContext, WinSource
from huian.rules.observed_settlement import HuianObservedSettlementPlugin
from .shanten import ordinary_shanten


@dataclass(frozen=True)
class OrdinaryDealInEstimate:
    tile: str
    samples: int
    winning_samples: int
    probability: float
    opponent_concealed_count: int
    opponent_open_melds: int


def _base_public_counter(observation):
    known = Counter(tile for tile in observation.hand if tile in env.BASE_TILES)
    for river in observation.discards:
        known.update(tile for tile in river if tile in env.BASE_TILES)
    for melds in observation.melds:
        for _, tiles in melds:
            known.update(tile for tile in tiles if tile in env.BASE_TILES)
    for tile in env.BASE_TILES:
        if known[tile] > 4:
            raise ValueError("known physical copies of a base tile cannot exceed four")
    return known


def _ordinary_discard_hu(sampled_hand, discard, gold_tile, open_melds):
    if discard == gold_tile:
        return False
    completed = (*sampled_hand, discard)
    gold_count = completed.count(gold_tile) if gold_tile is not None else 0
    # Target-room ordinary discard-Hu restrictions.
    if gold_count in (1, 2):
        return False
    return ordinary_shanten(
        completed, gold_tile=gold_tile, open_melds=open_melds) == -1



def is_ordinary_ron_tenpai(hand, *, gold_tile, open_melds):
    """Return whether a concealed hand has any legal ordinary Ron wait.

    This is a structural truth helper used by offline calibration/tests. It is
    not called by production agents with hidden opponent information.
    """
    hand = tuple(hand)
    if type(open_melds) is not int or not 0 <= open_melds <= 5:
        raise ValueError("open_melds must be an integer between zero and five")
    counts = Counter(hand)
    return any(
        counts[tile] < 4
        and _ordinary_discard_hu(hand, tile, gold_tile, open_melds)
        for tile in env.BASE_TILES
        if tile != gold_tile
    )

def estimate_ordinary_deal_in_probabilities(
        observation, candidate_tiles, *, samples=64, seed=0):
    """Estimate immediate ordinary discard-Hu probability for candidates.

    One common set of sampled opponent hands is reused for every candidate to
    reduce comparison noise. The probability is conditional on a simple
    uniform unseen-tile prior, not a claim about the real opponent strategy.
    """
    if type(samples) is not int or samples <= 0:
        raise ValueError("samples must be a positive integer")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    candidates = tuple(dict.fromkeys(candidate_tiles))
    if not candidates:
        raise ValueError("candidate_tiles must be nonempty")
    own = Counter(observation.hand)
    for tile in candidates:
        if tile not in env.BASE_TILES:
            raise ValueError("deal-in candidates must be base tiles")
        if own[tile] <= 0:
            raise ValueError("deal-in candidate must be in the acting hand")

    opponent = 1 - observation.seat
    open_melds = len(observation.melds[opponent])
    if not 0 <= open_melds <= 5:
        raise ValueError("opponent open meld count must be between zero and five")
    concealed_count = (5 - open_melds) * 3 + 1

    known = _base_public_counter(observation)
    unseen_pool = []
    for tile in env.BASE_TILES:
        unseen_pool.extend([tile] * (4 - known[tile]))
    if concealed_count > len(unseen_pool):
        raise ValueError("public state leaves too few unseen tiles for opponent hand")

    rng = Random(seed)
    sampled_hands = tuple(
        tuple(rng.sample(unseen_pool, concealed_count))
        for _ in range(samples)
    )
    estimates = []
    for tile in candidates:
        wins = sum(
            _ordinary_discard_hu(
                hand, tile, observation.gold_tile, open_melds)
            for hand in sampled_hands
        )
        estimates.append(OrdinaryDealInEstimate(
            tile=tile, samples=samples, winning_samples=wins,
            probability=wins / samples,
            opponent_concealed_count=concealed_count,
            opponent_open_melds=open_melds,
        ))
    return tuple(estimates)


@dataclass(frozen=True)
class TenpaiWaitRiskEstimate:
    """Relative wait danger under an explicit tenpai-template prior.

    ``risk_score`` is NOT an absolute deal-in probability. It is the fraction
    of accepted synthetic tenpai templates that can ordinary-Ron the candidate.
    """

    tile: str
    risk_score: float
    matching_templates: int
    templates_used: int
    generation_attempts: int
    opponent_concealed_count: int
    opponent_open_melds: int

    @property
    def is_deal_in_probability(self):
        return False


@dataclass(frozen=True)
class TenpaiWaitLossEstimate:
    """Score-aware relative loss under the same tenpai-template prior.

    ``loss_index`` averages confirmed ordinary-Ron loss across every accepted
    synthetic tenpai template, counting non-matching templates as zero loss.
    It is conditional on the opponent already being in tenpai and therefore is
    NOT an absolute expected loss / EV.
    """

    tile: str
    risk_score: float
    loss_index: float | None
    mean_loss_if_hit: float | None
    matching_templates: int
    scored_matching_templates: int
    templates_used: int
    generation_attempts: int
    opponent_concealed_count: int
    opponent_open_melds: int
    unresolved_reason: str | None = None

    @property
    def is_absolute_ev(self):
        return False

    @property
    def complete(self):
        return self.loss_index is not None and self.unresolved_reason is None


@dataclass(frozen=True)
class _PublicMeld:
    kind: str
    tiles: tuple[str, ...]


_MELD_TEMPLATES = tuple(
    [(tile, tile, tile) for tile in env.BASE_TILES]
    + [
        (f"{suit}{start}", f"{suit}{start + 1}", f"{suit}{start + 2}")
        for suit in "MPS"
        for start in range(1, 8)
    ]
)


def _sample_tenpai_template(rng, unseen_counts, gold_tile, open_melds):
    concealed_melds = 5 - open_melds
    pair_tile = rng.choice(env.BASE_TILES)
    completed = [pair_tile, pair_tile]
    for _ in range(concealed_melds):
        completed.extend(rng.choice(_MELD_TEMPLATES))
    counts = Counter(completed)
    if any(count > 4 for count in counts.values()):
        return None

    removed_index = rng.randrange(len(completed))
    completed.pop(removed_index)
    prehand = tuple(completed)
    pre_counts = Counter(prehand)
    if any(pre_counts[tile] > unseen_counts[tile] for tile in pre_counts):
        return None
    if ordinary_shanten(prehand, gold_tile=gold_tile, open_melds=open_melds) != 0:
        return None
    return prehand


def estimate_tenpai_wait_risk_scores(
        observation, candidate_tiles, *, samples=32, seed=0,
        max_attempt_factor=200):
    """Score candidate discards against public-info-compatible tenpai templates.

    This intentionally conditions on the opponent already being in ordinary
    tenpai. It therefore fixes the fatal prior of uniform unseen-hand sampling
    but does not estimate how likely the opponent is to be tenpai. The returned
    value is a relative risk feature and must not be called a deal-in probability.
    """
    if type(samples) is not int or samples <= 0:
        raise ValueError("samples must be a positive integer")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(max_attempt_factor) is not int or max_attempt_factor <= 0:
        raise ValueError("max_attempt_factor must be a positive integer")
    candidates = tuple(dict.fromkeys(candidate_tiles))
    if not candidates:
        raise ValueError("candidate_tiles must be nonempty")
    own = Counter(observation.hand)
    for tile in candidates:
        if tile not in env.BASE_TILES:
            raise ValueError("risk candidates must be base tiles")
        if own[tile] <= 0:
            raise ValueError("risk candidate must be in the acting hand")

    opponent = 1 - observation.seat
    open_melds = len(observation.melds[opponent])
    if not 0 <= open_melds <= 5:
        raise ValueError("opponent open meld count must be between zero and five")
    concealed_count = (5 - open_melds) * 3 + 1

    known = _base_public_counter(observation)
    unseen_counts = Counter({
        tile: 4 - known[tile] for tile in env.BASE_TILES
    })
    if sum(unseen_counts.values()) < concealed_count:
        raise ValueError("public state leaves too few unseen tiles for opponent hand")

    rng = Random(seed)
    accepted = []
    attempts = 0
    max_attempts = samples * max_attempt_factor
    while len(accepted) < samples and attempts < max_attempts:
        attempts += 1
        hand = _sample_tenpai_template(
            rng, unseen_counts, observation.gold_tile, open_melds)
        if hand is not None:
            accepted.append(hand)
    if not accepted:
        raise RuntimeError("could not generate a public-compatible tenpai template")

    estimates = []
    for tile in candidates:
        matches = sum(
            _ordinary_discard_hu(
                hand, tile, observation.gold_tile, open_melds)
            for hand in accepted
        )
        estimates.append(TenpaiWaitRiskEstimate(
            tile=tile,
            risk_score=matches / len(accepted),
            matching_templates=matches,
            templates_used=len(accepted),
            generation_attempts=attempts,
            opponent_concealed_count=concealed_count,
            opponent_open_melds=open_melds,
        ))
    return tuple(estimates)


def _confirmed_ordinary_ron_loss(observation, sampled_hand, discard):
    """Return acting player's positive loss for one synthetic ordinary Ron.

    None means the structural win exists but some score input is not backed by
    CONFIRMED evidence or match dealer-base context is unavailable.
    """
    context = observation.match_context
    if context is None:
        return None
    opponent = 1 - observation.seat
    melds = tuple(
        _PublicMeld(kind, tuple(tiles))
        for kind, tiles in observation.melds[opponent]
    )
    completed = [*sampled_hand, discard]
    rules = HuianRules()
    hu_context = HuContext(WinSource.DISCARD, winning_tile=discard)
    hu_result = rules.analyze_hu(
        completed,
        observation.gold_tile,
        open_melds=len(melds),
        win_context=hu_context,
    )
    if not hu_result.legal:
        return None
    try:
        fan_result = rules.aggregate_fan(
            completed,
            melds=melds,
            flowers=observation.flowers[opponent],
            gold_tile=observation.gold_tile,
            hu_result=hu_result,
        )
    except ValueError:
        # Synthetic tenpai templates can occasionally produce solver
        # decompositions outside FanAggregator's auditable scoring shape.
        # Never relax Rules/FanAggregator to accommodate model-generated data;
        # mark this template unscored so V0.7 falls back to V0.6.
        return None
    if not fan_result.complete:
        return None
    if any(component.status != EvidenceStatus.CONFIRMED
           for component in fan_result.components):
        return None
    settlement = HuianObservedSettlementPlugin().settle(
        winner=opponent,
        current_dealer_base=context.current_dealer_base,
        winner_fan=fan_result.fan,
        win_type="PINGHU",
    )
    loss = -settlement.rewards[observation.seat]
    if loss < 0:
        raise ValueError("ordinary Ron loss must be nonnegative for the discarder")
    return loss


def estimate_tenpai_wait_loss_scores(
        observation, candidate_tiles, *, samples=32, seed=0,
        max_attempt_factor=200):
    """Rank exact-offense-tie discards by tenpai-conditioned score exposure.

    This reuses the public-information tenpai-template prior, but for each
    matching ordinary-Ron template it computes the confirmed target-room Pinghu
    loss from the current dealer base and the sampled winner's auditable fan.

    The returned ``loss_index`` is conditional on a tenpai-template prior.
    It must not be displayed or consumed as an absolute expected loss.
    """
    if observation.match_context is None:
        raise ValueError("score-aware tenpai loss requires match_context")
    if type(samples) is not int or samples <= 0:
        raise ValueError("samples must be a positive integer")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(max_attempt_factor) is not int or max_attempt_factor <= 0:
        raise ValueError("max_attempt_factor must be a positive integer")
    candidates = tuple(dict.fromkeys(candidate_tiles))
    if not candidates:
        raise ValueError("candidate_tiles must be nonempty")
    own = Counter(observation.hand)
    for tile in candidates:
        if tile not in env.BASE_TILES:
            raise ValueError("loss candidates must be base tiles")
        if own[tile] <= 0:
            raise ValueError("loss candidate must be in the acting hand")

    opponent = 1 - observation.seat
    open_melds = len(observation.melds[opponent])
    if not 0 <= open_melds <= 5:
        raise ValueError("opponent open meld count must be between zero and five")
    concealed_count = (5 - open_melds) * 3 + 1

    known = _base_public_counter(observation)
    unseen_counts = Counter({
        tile: 4 - known[tile] for tile in env.BASE_TILES
    })
    if sum(unseen_counts.values()) < concealed_count:
        raise ValueError("public state leaves too few unseen tiles for opponent hand")

    rng = Random(seed)
    accepted = []
    attempts = 0
    max_attempts = samples * max_attempt_factor
    while len(accepted) < samples and attempts < max_attempts:
        attempts += 1
        hand = _sample_tenpai_template(
            rng, unseen_counts, observation.gold_tile, open_melds)
        if hand is not None:
            accepted.append(hand)
    if not accepted:
        raise RuntimeError("could not generate a public-compatible tenpai template")

    estimates = []
    for tile in candidates:
        matches = 0
        scored = 0
        total_loss = 0
        unresolved = None
        for hand in accepted:
            if not _ordinary_discard_hu(
                    hand, tile, observation.gold_tile, open_melds):
                continue
            matches += 1
            loss = _confirmed_ordinary_ron_loss(observation, hand, tile)
            if loss is None:
                unresolved = "unconfirmed_or_incomplete_ordinary_score"
                continue
            scored += 1
            total_loss += loss

        complete = scored == matches
        loss_index = (
            total_loss / len(accepted)
            if complete else None
        )
        mean_loss_if_hit = (
            total_loss / matches
            if complete and matches else (0.0 if complete else None)
        )
        estimates.append(TenpaiWaitLossEstimate(
            tile=tile,
            risk_score=matches / len(accepted),
            loss_index=loss_index,
            mean_loss_if_hit=mean_loss_if_hit,
            matching_templates=matches,
            scored_matching_templates=scored,
            templates_used=len(accepted),
            generation_attempts=attempts,
            opponent_concealed_count=concealed_count,
            opponent_open_melds=open_melds,
            unresolved_reason=(None if complete else unresolved),
        ))
    return tuple(estimates)
