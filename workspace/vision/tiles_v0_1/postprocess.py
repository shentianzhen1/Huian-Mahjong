"""Observation-only validation; no GameState or action integration."""
from collections import Counter, defaultdict
from dataclasses import dataclass

from .taxonomy import category_for


@dataclass(frozen=True)
class TilePrediction:
    tile_id: str
    confidence: float
    region: str
    bbox: tuple[int, int, int, int]
    slot: int | None = None
    category: str | None = None

    def __post_init__(self):
        if self.category is None:
            object.__setattr__(self, "category", category_for(self.tile_id))


@dataclass(frozen=True)
class ObservationConstraints:
    confidence_threshold: float = 0.80
    expected_hand_count: int | None = None
    max_hand_count: int = 17
    max_draw_count: int = 1
    max_gold_count: int = 1
    max_physical_copies: int = 4


@dataclass(frozen=True)
class ValidationResult:
    accepted: tuple[TilePrediction, ...]
    rejected: tuple[TilePrediction, ...]
    issues: tuple[str, ...]


def validate_observation(predictions, constraints=ObservationConstraints()):
    accepted = tuple(item for item in predictions
                     if item.confidence >= constraints.confidence_threshold)
    rejected = tuple(item for item in predictions
                     if item.confidence < constraints.confidence_threshold)
    issues = []
    grouped = defaultdict(list)
    for item in accepted:
        grouped[item.region].append(item)
    hand_count = len(grouped["hand_region"])
    if constraints.expected_hand_count is not None and hand_count != constraints.expected_hand_count:
        issues.append(f"hand count {hand_count} != expected {constraints.expected_hand_count}")
    if hand_count > constraints.max_hand_count:
        issues.append(f"hand count {hand_count} exceeds {constraints.max_hand_count}")
    if len(grouped["draw_region"]) > constraints.max_draw_count:
        issues.append("draw region has more than one accepted tile")
    if len(grouped["gold_region"]) > constraints.max_gold_count:
        issues.append("gold region has more than one accepted tile")
    physical = Counter(item.tile_id for item in accepted
                       if item.region in ("hand_region", "draw_region"))
    for tile_id, count in sorted(physical.items()):
        if count > constraints.max_physical_copies:
            issues.append(f"{tile_id} appears {count} times, exceeds {constraints.max_physical_copies}")
    return ValidationResult(accepted, rejected, tuple(issues))


class MultiFrameVoter:
    """Reserved interface for later temporal smoothing of aligned tile slots."""

    def vote(self, frame_predictions):
        scores = defaultdict(lambda: defaultdict(float))
        counts = defaultdict(lambda: defaultdict(int))
        representatives = {}
        for predictions in frame_predictions:
            for index, prediction in enumerate(predictions):
                key = prediction.region, prediction.slot if prediction.slot is not None else index
                scores[key][prediction.tile_id] += prediction.confidence
                counts[key][prediction.tile_id] += 1
                representatives[key, prediction.tile_id] = prediction
        voted = []
        for key in sorted(scores):
            tile_id, total = max(scores[key].items(), key=lambda item: item[1])
            original = representatives[key, tile_id]
            confidence = total / counts[key][tile_id]
            voted.append(TilePrediction(tile_id, confidence, original.region,
                                        original.bbox, original.slot,
                                        original.category))
        return tuple(voted)
