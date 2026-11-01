"""Evidence-safe simulator bridges for the confirmed staged opening API.

The target room does not derive Gold from dice.  The current player-confirmed
rule is that the system randomly selects Gold after excluding flower tiles.
The real random distribution/RNG remains unknown.

``run_staged_opening`` keeps the explicit-candidate compatibility path used by
replay fixtures. ``run_random_staged_opening`` is the target-room simulator
bridge: it chooses only from nonflower wall entries with a seeded local RNG so
simulation is reproducible. Uniform choice is a SIMULATOR_CONVENTION, not a
claim about the room's server-side distribution.
"""
from dataclasses import replace
import hashlib
import json
import random

from huian._legacy import env
from huian.environment import HuianEnvironment

from .core import Simulator, make_wall


OPEN_GOLD_RANDOM_EVIDENCE_ID = "player_confirmed_open_gold_random_20261007_v1"


def simulator_random_gold_candidate(wall, *, seed=None):
    """Choose one nonflower wall entry for deterministic simulation only.

    The target-room fact is only SYSTEM_RANDOM over a flower-excluded pool.
    Uniform sampling and this local PRNG are simulator conventions; they do not
    model, predict or claim the server's unknown distribution/RNG.
    """
    candidates = tuple(
        index for index, tile in enumerate(wall)
        if tile not in env.FLOWERS
    )
    if not candidates:
        raise ValueError("No nonflower tile is available for random Gold selection")
    wall_index = random.Random(seed).choice(candidates)
    return wall_index, wall[wall_index], len(candidates)


def run_staged_opening(
        *, seed=None, wall=None, dealer=0, current_dealer_base=10,
        candidate_indices=(), max_steps=100, environment_factory=HuianEnvironment):
    """Run only the confirmed opening through Gold or a forced terminal.

    This explicit-candidate function is retained for replay/compatibility
    fixtures. Callers provide wall indices interpreted against the current wall
    at the moment each candidate is consumed. It never derives a target-room
    Gold position from dice.
    """
    if type(dealer) is not int or dealer not in (0, 1):
        raise ValueError("dealer must be seat 0 or 1")
    if (type(current_dealer_base) is not int
            or current_dealer_base < 0):
        raise ValueError("current_dealer_base must be a nonnegative integer")
    if type(max_steps) is not int or max_steps <= 0:
        raise ValueError("max_steps must be a positive integer")
    indices = tuple(candidate_indices)
    if any(type(index) is not int for index in indices):
        raise ValueError("candidate_indices must contain only integers")

    tiles = make_wall(seed) if wall is None else list(wall)
    wall_hash = hashlib.sha256(json.dumps(tiles).encode()).hexdigest()
    game = environment_factory(max_steps=max_steps)
    game.reset(wall=tiles, dealer=dealer)
    initial_hash = game.state.state_hash()
    game.begin_confirmed_opening()

    def finish(status, stop_reason=None):
        return Simulator._result(
            game,
            seed=seed,
            status=status,
            stop_reason=stop_reason,
            simulation_only=True,
            real_scoring=True,
            config={
                "opening_mode": "STAGED_EXPLICIT_CANDIDATES",
                "candidate_indices": list(indices),
                "current_dealer_base": current_dealer_base,
            },
            initial_state_hash=initial_hash,
            wall_hash=wall_hash,
        )

    if game.state.phase == "OPENING_EIGHT_FLOWER_CHOICE":
        return finish("NEEDS_INPUT", "opening_eight_flower_choice")

    for wall_index in indices:
        if game.state.phase != "OPENING_GOLD_PENDING":
            break
        game.reveal_opening_candidate(
            wall_index=wall_index,
            current_dealer_base=current_dealer_base,
        )
        if game.is_terminal():
            return finish("COMPLETED")
        if game.state.phase == "OPENING_POST_GOLD_PENDING":
            return finish("READY")

    if game.state.phase == "OPENING_GOLD_PENDING":
        return finish("NEEDS_INPUT", "opening_candidate_required")
    if game.is_terminal():
        return finish("COMPLETED")
    return finish("READY")


def run_random_staged_opening(
        *, seed=None, random_seed=None, wall=None, dealer=0,
        current_dealer_base=10, max_steps=100,
        environment_factory=HuianEnvironment):
    """Run staged opening with a seeded simulator-only random Gold choice.

    Player-confirmed target-room facts:
    - the system selects Gold randomly;
    - flowers are excluded before selection;
    - dice/wall-stack mapping is not the Gold-selection mechanism.

    Unknown target-room facts:
    - probability distribution/weighting;
    - RNG implementation, seed and predictability.

    For deterministic tests this helper uses a local uniform PRNG over the
    current nonflower wall entries. That sampling policy is explicitly a
    ``SIMULATOR_CONVENTION_ONLY`` and must not be reused to predict live Gold.
    """
    selector_seed = seed if random_seed is None else random_seed
    tiles = make_wall(seed) if wall is None else list(wall)

    probe = environment_factory(max_steps=max_steps)
    probe.reset(wall=tiles, dealer=dealer)
    probe.begin_confirmed_opening()

    if probe.state.phase == "OPENING_EIGHT_FLOWER_CHOICE":
        result = run_staged_opening(
            seed=seed,
            wall=tiles,
            dealer=dealer,
            current_dealer_base=current_dealer_base,
            candidate_indices=(),
            max_steps=max_steps,
            environment_factory=environment_factory,
        )
        config = dict(result.config or {})
        config.update({
            "opening_mode": "STAGED_SYSTEM_RANDOM_NONFLOWER",
            "selection_evidence_id": OPEN_GOLD_RANDOM_EVIDENCE_ID,
            "target_selection": "SYSTEM_RANDOM",
            "target_candidate_pool": "NONFLOWER_TILES_ONLY",
            "target_distribution": "UNKNOWN",
            "simulator_sampling": "SEEDED_UNIFORM_NONFLOWER",
            "simulator_sampling_status": "SIMULATOR_CONVENTION_ONLY",
            "random_seed": selector_seed,
        })
        return replace(result, config=config)

    if probe.state.phase != "OPENING_GOLD_PENDING":
        raise ValueError("Random Gold selection requires OPENING_GOLD_PENDING")

    wall_index, selected_tile, candidate_pool_size = simulator_random_gold_candidate(
        probe.state.wall, seed=selector_seed
    )
    result = run_staged_opening(
        seed=seed,
        wall=tiles,
        dealer=dealer,
        current_dealer_base=current_dealer_base,
        candidate_indices=(wall_index,),
        max_steps=max_steps,
        environment_factory=environment_factory,
    )
    config = dict(result.config or {})
    config.update({
        "opening_mode": "STAGED_SYSTEM_RANDOM_NONFLOWER",
        "selection_evidence_id": OPEN_GOLD_RANDOM_EVIDENCE_ID,
        "target_selection": "SYSTEM_RANDOM",
        "target_candidate_pool": "NONFLOWER_TILES_ONLY",
        "target_distribution": "UNKNOWN",
        "simulator_sampling": "SEEDED_UNIFORM_NONFLOWER",
        "simulator_sampling_status": "SIMULATOR_CONVENTION_ONLY",
        "random_seed": selector_seed,
        "candidate_pool_size": candidate_pool_size,
        "selected_wall_index": wall_index,
        "selected_tile": selected_tile,
    })
    return replace(result, config=config)
