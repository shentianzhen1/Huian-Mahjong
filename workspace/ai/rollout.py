"""Public-information multi-step rollout candidate for Huian ordinary play.

V0.14 is deliberately an experimental candidate, not CurrentAgent.  It never
reads the real opponent concealed hand or future wall order.  Hidden draws are
sampled from the physical unseen pool implied by the acting player's hand and
public table.

The first implementation is intentionally narrow:
- keep minimum ordinary shanten as a hard constraint;
- shortlist up to a few best immediate ordinary candidates;
- use common-random-number rollouts for every candidate;
- simulate own draw -> best discard -> hidden opponent draw depletion -> own draw;
- stop/ignore a rollout when the acting player samples Jin because special-Jin
  EV is not complete yet;
- CHI/PENG and all unsupported action classes fall back to promoted V0.10.

This is ordinary offense search, not a claim of full Mahjong EV.
"""
from collections import Counter
from dataclasses import dataclass
import random

from huian._legacy import env
from .baseline import AgentDecision, MeldAwareShantenAgent
from .shanten import (analyze_effective_tiles, best_discard,
                      min_shanten_discards, ordinary_shanten)


@dataclass(frozen=True)
class PublicRolloutEstimate:
    discard: str
    samples_requested: int
    samples_completed: int
    skipped_gold_samples: int
    wins_within_horizon: int
    mean_final_shanten: float
    mean_final_live_copies: float
    mean_final_effective_types: float

    @property
    def win_rate(self):
        if not self.samples_completed:
            return 0.0
        return self.wins_within_horizon / self.samples_completed


def _public_tiles(observation):
    tiles = []
    for river in observation.discards:
        tiles.extend(tile for tile in river if tile in env.BASE_TILES)
    for melds in observation.melds:
        for _, meld_tiles in melds:
            tiles.extend(tile for tile in meld_tiles if tile in env.BASE_TILES)
    return tuple(tiles)


def _unseen_pool(observation):
    """Return physical base tiles not in own concealed hand or public zones."""
    own = Counter(observation.hand)
    public = Counter(_public_tiles(observation))
    pool = []
    for tile in env.BASE_TILES:
        capacity = 3 if tile == observation.gold_tile else 4
        remaining = capacity - own[tile] - public[tile]
        if remaining < 0:
            raise ValueError("known copies exceed physical tile capacity")
        pool.extend([tile] * remaining)
    return tuple(pool)


def _sample_hidden_sequences(pool, *, samples, own_draws, seed):
    """Sample common hidden sequences.

    Between two acting-player draws there is one hidden opponent draw.  We do
    not inspect or model that concealed tile beyond its physical depletion.
    """
    hidden_steps = own_draws * 2 - 1
    if hidden_steps <= 0 or len(pool) < hidden_steps:
        raise RuntimeError("not enough unseen tiles for rollout horizon")
    rng = random.Random(seed)
    return tuple(
        tuple(rng.sample(pool, hidden_steps))
        for _ in range(samples)
    )


def estimate_public_rollouts(
        observation, candidate_discards, *, samples=24, own_draws=2, seed=0):
    """Compare discard candidates by sampled public-information future offense."""
    if type(samples) is not int or samples <= 0:
        raise ValueError("samples must be a positive integer")
    if type(own_draws) is not int or not 1 <= own_draws <= 3:
        raise ValueError("own_draws must be an integer between 1 and 3")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")

    candidates = tuple(dict.fromkeys(candidate_discards))
    if not candidates:
        raise ValueError("candidate_discards must be non-empty")
    if any(tile not in observation.hand for tile in candidates):
        raise ValueError("every rollout discard must be in the acting hand")
    if observation.gold_tile in candidates:
        raise ValueError("gold discard is outside ordinary rollout scope")

    open_melds = len(observation.melds[observation.seat])
    public = _public_tiles(observation)
    pool = _unseen_pool(observation)
    sequences = _sample_hidden_sequences(
        pool, samples=samples, own_draws=own_draws, seed=seed)

    out = []
    for discard in candidates:
        starting_hand = list(observation.hand)
        starting_hand.remove(discard)
        wins = completed = skipped_gold = 0
        shanten_sum = live_sum = type_sum = 0.0

        for sequence in sequences:
            # Any own future Jin draw would require special-state EV. Because
            # common sequences are shared by every candidate, dropping these
            # samples does not create candidate-specific hidden information.
            own_sequence = tuple(sequence[index] for index in range(0, len(sequence), 2))
            if (observation.gold_tile is not None
                    and observation.gold_tile in own_sequence):
                skipped_gold += 1
                continue

            hand = list(starting_hand)
            visible_extra = [discard]
            terminal = False
            for draw_index in range(own_draws):
                draw = sequence[2 * draw_index]
                hand.append(draw)
                if ordinary_shanten(
                        hand, observation.gold_tile, open_melds) == -1:
                    terminal = True
                    wins += 1
                    break

                choice = best_discard(
                    hand,
                    gold_tile=observation.gold_tile,
                    open_melds=open_melds,
                    visible_tiles=(*public, *visible_extra),
                )
                hand.remove(choice.discard)
                visible_extra.append(choice.discard)

            completed += 1
            if terminal:
                shanten_sum -= 1.0
                continue

            final = analyze_effective_tiles(
                hand,
                gold_tile=observation.gold_tile,
                open_melds=open_melds,
                visible_tiles=(*public, *visible_extra),
            )
            shanten_sum += final.shanten
            live_sum += final.total_live_copies
            type_sum += len(final.effective_tiles)

        if not completed:
            raise RuntimeError("all rollout samples entered unsupported gold branches")
        out.append(PublicRolloutEstimate(
            discard=discard,
            samples_requested=samples,
            samples_completed=completed,
            skipped_gold_samples=skipped_gold,
            wins_within_horizon=wins,
            mean_final_shanten=shanten_sum / completed,
            mean_final_live_copies=live_sum / completed,
            mean_final_effective_types=type_sum / completed,
        ))
    return tuple(out)


class PublicRolloutAgent(MeldAwareShantenAgent):
    """Experimental V0.14 candidate: two-own-draw public-information rollout.

    This does not replace CurrentAgent V0.10.  It broadens search only inside
    the minimum-shanten discard frontier and falls back to V0.10 for claims,
    Jin-in-hand states, single-candidate frontiers, or unsupported rollouts.
    """

    def __init__(self, seed=None, template_samples=32, *,
                 rollout_samples=24, own_draws=2, candidate_limit=4):
        super().__init__(seed=seed, template_samples=template_samples)
        if type(rollout_samples) is not int or rollout_samples <= 0:
            raise ValueError("rollout_samples must be a positive integer")
        if type(own_draws) is not int or not 1 <= own_draws <= 3:
            raise ValueError("own_draws must be an integer between 1 and 3")
        if type(candidate_limit) is not int or candidate_limit < 2:
            raise ValueError("candidate_limit must be an integer >= 2")
        self.rollout_samples = rollout_samples
        self.own_draws = own_draws
        self.candidate_limit = candidate_limit
        self._rollout_index = 0

    def _next_rollout_seed(self):
        value = self.seed * 1_000_003 + 700_001 + self._rollout_index
        self._rollout_index += 1
        return value

    @staticmethod
    def _rollout_key(estimate):
        return (
            -estimate.wins_within_horizon,
            estimate.mean_final_shanten,
            -estimate.mean_final_live_copies,
            -estimate.mean_final_effective_types,
        )

    def choose_decision(self, observation, legal_actions):
        if not legal_actions:
            raise ValueError("No legal actions")

        # Always compute V0.10 at the same decision point.  Besides providing a
        # conservative fallback, this advances V0.6/V0.10 risk RNG consistently.
        baseline = super().choose_decision(observation, legal_actions)
        actions = sorted(legal_actions, key=self._key)

        # Keep wins, claim response logic, KONG and special actions on V0.10.
        if baseline.action.type.value in ("HU", "ROB_KONG_HU"):
            return baseline
        if any(action.type in (
                env.ActionType.CHI, env.ActionType.PENG,
                env.ActionType.MING_GANG, env.ActionType.AN_GANG,
                env.ActionType.ADD_KONG, env.ActionType.YOUJIN,
        ) for action in actions):
            return AgentDecision(
                baseline.action,
                f"{baseline.reason}; public_rollout_v0.14 gated_off_nonordinary_actions",
            )

        discards = [action for action in actions
                    if action.type == env.ActionType.DISCARD]
        if len(discards) < 2:
            return baseline
        if (observation.gold_tile is not None
                and observation.gold_tile in observation.hand):
            return AgentDecision(
                baseline.action,
                f"{baseline.reason}; public_rollout_v0.14 gated_off_gold_in_hand",
            )

        legal_by_tile = {action.tile: action for action in discards}
        frontier = min_shanten_discards(
            observation.hand,
            gold_tile=observation.gold_tile,
            open_melds=len(observation.melds[observation.seat]),
            visible_tiles=_public_tiles(observation),
            allowed_discards=tuple(legal_by_tile),
        )
        if len(frontier) <= 1:
            return baseline

        # Search more broadly than V0.8/V0.9 exact-offense ties, but keep the
        # immediate minimum-shanten constraint and cap branching for tractability.
        shortlist = tuple(sorted(
            frontier,
            key=lambda item: (
                -item.total_live_copies,
                -len(item.effective_tiles),
                env.BASE_TILES.index(item.discard),
            ),
        )[:self.candidate_limit])
        candidates = tuple(item.discard for item in shortlist)

        try:
            estimates = estimate_public_rollouts(
                observation,
                candidates,
                samples=self.rollout_samples,
                own_draws=self.own_draws,
                seed=self._next_rollout_seed(),
            )
        except (RuntimeError, ValueError):
            return AgentDecision(
                baseline.action,
                f"{baseline.reason}; public_rollout_v0.14 fallback=rollout_unavailable",
            )

        by_tile = {item.discard: item for item in estimates}
        best_key = min(self._rollout_key(item) for item in estimates)
        finalists = tuple(
            tile for tile in candidates
            if self._rollout_key(by_tile[tile]) == best_key
        )
        if baseline.action.tile in finalists:
            chosen = baseline.action.tile
        else:
            chosen = min(finalists, key=env.BASE_TILES.index)
        estimate = by_tile[chosen]
        alternatives = ",".join(
            f"{tile}:win={by_tile[tile].wins_within_horizon}/"
            f"{by_tile[tile].samples_completed},"
            f"s={by_tile[tile].mean_final_shanten:.3f},"
            f"live={by_tile[tile].mean_final_live_copies:.2f}"
            for tile in candidates
        )
        return AgentDecision(
            legal_by_tile[chosen],
            f"DISCARD {chosen}: public_rollout_v0.14_candidate "
            f"(horizon_own_draws={self.own_draws}, "
            f"samples={estimate.samples_completed}/"
            f"{estimate.samples_requested}, "
            f"gold_cutoffs={estimate.skipped_gold_samples}, "
            f"win_rate={estimate.win_rate:.3f}, "
            f"final_shanten={estimate.mean_final_shanten:.3f}, "
            f"final_live={estimate.mean_final_live_copies:.2f}, "
            f"final_types={estimate.mean_final_effective_types:.2f}; "
            f"candidates=[{alternatives}]); "
            f"public unseen-pool sampling only; no real opponent hand/wall order",
        )
