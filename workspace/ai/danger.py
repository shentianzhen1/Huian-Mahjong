"""Public-information discard risk proxies for Huian two-player Mahjong.

This module deliberately does not output a deal-in probability. It only measures
how many copies of the tile being discarded are still unseen after accounting for
the acting player concealed hand and all public rivers/melds.

Fewer unseen copies means fewer physical copies can be in the opponent concealed
hand. This is a transparent risk proxy, not a complete opponent model.
"""
from collections import Counter
from dataclasses import dataclass

from huian._legacy import env


@dataclass(frozen=True)
class PublicDangerEstimate:
    tile: str
    risk_units: int
    unseen_copies: int
    own_copies: int
    public_copies: int
    opponent_discard_copies: int

    @property
    def is_probability(self):
        return False


def _public_counts(observation):
    counts = Counter()
    for river in observation.discards:
        counts.update(tile for tile in river if tile in env.BASE_TILES)
    for melds in observation.melds:
        for _, tiles in melds:
            counts.update(tile for tile in tiles if tile in env.BASE_TILES)
    return counts


def estimate_discard_danger(observation, tile):
    """Return a deterministic public-information risk proxy for a discard.

    risk_units currently equals the number of physically unseen copies.
    Opponent discards are recorded only as diagnostics; they are not treated
    as furiten/safe-tile evidence in Huian rules.
    """
    if tile not in env.BASE_TILES:
        raise ValueError("danger estimate requires a base tile")
    own = Counter(observation.hand)
    if own[tile] <= 0:
        raise ValueError("discard tile must be in the acting player hand")

    public = _public_counts(observation)
    for base in env.BASE_TILES:
        if own[base] + public[base] > 4:
            raise ValueError("own concealed plus public visible copies exceed four")

    unseen = 4 - own[tile] - public[tile]
    opponent = 1 - observation.seat
    opponent_discard_copies = observation.discards[opponent].count(tile)
    return PublicDangerEstimate(
        tile=tile,
        risk_units=unseen,
        unseen_copies=unseen,
        own_copies=own[tile],
        public_copies=public[tile],
        opponent_discard_copies=opponent_discard_copies,
    )
