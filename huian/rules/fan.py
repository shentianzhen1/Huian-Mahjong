"""Evidence-aware Huian fan aggregation.

V0.1 only aggregates components supported by target-room evidence. It never
turns unresolved fan items into zero. The result separates the audited known
subtotal from a complete fan total.
"""
from dataclasses import dataclass

from huian._legacy import core
from .config import EvidenceStatus
from .context import KongKind, WinSource


@dataclass(frozen=True)
class FanComponent:
    category: str
    fan: int
    detail: str
    status: EvidenceStatus
    evidence: str


@dataclass(frozen=True)
class FanResult:
    """Fan audit for one hand."""

    fan: int | None
    accounted_fan: int
    components: tuple[FanComponent, ...]
    unresolved: tuple[str, ...]
    candidate_fans: tuple[int, ...]
    decomposition_count: int
    decomposition_fans: tuple[int, ...]

    @property
    def complete(self):
        return self.fan is not None and not self.unresolved


class FanAggregator:
    """Aggregate target-room winner fan without guessing missing rules."""

    def __init__(self, rules):
        self.rules = rules

    @staticmethod
    def _component(category, fan, detail, status, evidence):
        return FanComponent(category, fan, detail, status, evidence)

    def _base_components(self, hand, melds, flowers, gold_tile):
        components = []
        unresolved = []

        gold_count = hand.count(gold_tile) if gold_tile is not None else 0
        if gold_count:
            components.append(self._component(
                "gold", gold_count, f"{gold_tile} x{gold_count} @ 1 fan each",
                EvidenceStatus.CONFIRMED,
                "Player/replay confirmation 2026-09-18: every gold is 1 fan; "
                "wildcard use does not consume or add fan",
            ))

        flowers = tuple(flowers)
        if any(tile not in core.FLOWERS for tile in flowers):
            raise ValueError("flowers must contain only flower tiles")
        if len(set(flowers)) != len(flowers):
            raise ValueError("A physical flower tile cannot appear twice")
        if flowers:
            components.append(self._component(
                "flowers", len(flowers), f"{len(flowers)} flower tile(s) x1",
                EvidenceStatus.CONFIRMED,
                "Direct target-room settlements and player confirmation: each flower is 1 fan",
            ))
        # Player confirmation 2026-09-18: flowers are strictly linear at
        # 1 fan each. Complete four-flower groups add nothing extra; if an
        # eight-flower special win is declined, the ordinary fan remains 8.
        # Special-win eligibility belongs to the state machine, not FanAggregator.

        for meld in melds:
            kind = getattr(meld, "kind", None)
            tiles = tuple(getattr(meld, "tiles", ()))
            if kind == "CHI":
                continue
            if kind == "PENG":
                if len(tiles) != 3 or len(set(tiles)) != 1:
                    raise ValueError("PENG must contain three identical tiles")
                tile = tiles[0]
                if tile not in core.BASE_TILES:
                    raise ValueError("PENG requires a normal tile")
                if core.is_honor(tile):
                    components.append(self._component(
                        "honor_peng", 1, f"{tile} honor Peng",
                        EvidenceStatus.HIGH_CONFIDENCE,
                        "Huian in-game rule page: honor Peng = 1 fan",
                    ))
                else:
                    unresolved.append("exposed_triplet_fan")
                continue
            if kind in ("MING_GANG", "AN_GANG", "ADDED_GANG"):
                if len(tiles) != 4 or len(set(tiles)) != 1:
                    raise ValueError("Kong meld must contain four identical tiles")
                info = self.rules.kong_fan(KongKind(kind), tiles[0])
                components.append(self._component(
                    "kong", info.fan, f"{kind}:{tiles[0]}",
                    info.status, info.evidence,
                ))
                continue
            raise ValueError(f"Unsupported meld kind for fan aggregation: {kind!r}")

        return components, unresolved

    def _concealed_components(self, decomposition, hu_result):
        components = []
        for group in decomposition.groups:
            if len(group) != 3:
                raise ValueError("Hu decomposition groups must contain three positions")
            if "GOLD" in group or len(set(group)) != 1:
                continue
            tile = group[0]
            if tile not in core.BASE_TILES:
                raise ValueError("Invalid tile in Hu decomposition")
            # Player confirmation 2026-09-18: when an opponent discard is the
            # third matching tile that completes this triplet for Pinghu, that
            # triplet is not an An-Ke and receives no concealed-triplet fan.
            if (hu_result.context.source == WinSource.DISCARD
                    and hu_result.context.winning_tile == tile):
                continue
            fan = 2 if core.is_honor(tile) else 1
            components.append(self._component(
                "concealed_triplet", fan,
                f"{tile}{tile}{tile}",
                EvidenceStatus.CONFIRMED,
                ("b3892b34/direct target-room settlement: "
                 + ("honor concealed triplet = 2 fan"
                    if core.is_honor(tile)
                    else "suited concealed triplet = 1 fan")),
            ))
        return components

    @staticmethod
    def _component_signature(components):
        return tuple(sorted(
            (c.category, c.fan, c.detail, c.status.value)
            for c in components
        ))

    def aggregate(self, hand, melds=(), flowers=(), gold_tile=None, *,
                  hu_result=None):
        """Aggregate one legal ordinary/Youjin-compatible structural hand."""
        hand = list(hand)
        melds = tuple(melds)
        flowers = tuple(flowers)
        self.rules._validate_hand(hand, gold_tile)

        if hu_result is None:
            hu_result = self.rules.analyze_hu(
                hand, gold_tile, open_melds=len(melds), max_decompositions=64
            )
        if not hu_result.legal or not hu_result.decompositions:
            raise ValueError("Fan aggregation requires a legal structural Hu")
        if hu_result.gold_tile != gold_tile:
            raise ValueError("HuResult gold tile disagrees with aggregation input")
        if hu_result.open_melds != len(melds):
            raise ValueError("HuResult open-meld count disagrees with melds")

        base_components, base_unresolved = self._base_components(
            hand, melds, flowers, gold_tile
        )

        candidates = []
        signatures = []
        component_sets = []
        for decomposition in hu_result.decompositions:
            components = tuple(base_components + self._concealed_components(decomposition, hu_result))
            candidate_fan = sum(item.fan for item in components)
            candidates.append(candidate_fan)
            signatures.append(self._component_signature(components))
            component_sets.append(components)

        unresolved = list(dict.fromkeys(base_unresolved))
        decomposition_ambiguous = (
            hu_result.may_be_truncated
            or len(set(signatures)) > 1
            or len(set(candidates)) > 1
        )
        if decomposition_ambiguous:
            unresolved.append("decomposition_scoring")

        if decomposition_ambiguous:
            components = tuple(base_components)
            accounted = sum(item.fan for item in components)
        else:
            components = component_sets[0]
            accounted = candidates[0]

        unresolved = tuple(dict.fromkeys(unresolved))
        fan = accounted if not unresolved else None
        return FanResult(
            fan=fan,
            accounted_fan=accounted,
            components=components,
            unresolved=unresolved,
            candidate_fans=tuple(sorted(set(candidates))),
            decomposition_count=len(hu_result.decompositions),
            decomposition_fans=tuple(candidates),
        )
