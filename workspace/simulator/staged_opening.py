"""Evidence-safe simulator bridge for the confirmed staged opening API.

This module never derives a live Gold position from dice.  Callers must provide
one or more explicit wall indices, each interpreted against the current wall at
the moment that candidate is consumed.  A flower candidate leaves the opening
in ``OPENING_GOLD_PENDING`` so another explicit index is required.
"""
from dataclasses import asdict
import hashlib
import json

from huian.environment import HuianEnvironment

from .core import Simulator, make_wall


def run_staged_opening(
        *, seed=None, wall=None, dealer=0, current_dealer_base=10,
        candidate_indices=(), max_steps=100, environment_factory=HuianEnvironment):
    """Run only the confirmed opening through Gold or a forced terminal.

    The function deliberately stops with ``NEEDS_INPUT`` when the opening needs
    a player choice (pre-Gold eight flowers) or when no more explicit Gold
    candidate indices are supplied.  It does not invent a dice mapping,
    direction, stack count or random target-room distribution.
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
