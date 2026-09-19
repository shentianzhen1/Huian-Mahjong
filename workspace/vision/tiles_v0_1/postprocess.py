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



@dataclass(frozen=True)
class SlotStability:
    region: str
    slot: int
    frames_seen: int
    voted_tile: str
    agreement: float
    mean_confidence: float
    stable: bool


@dataclass(frozen=True)
class TemporalStabilityReport:
    slots: tuple[SlotStability, ...]
    stable_slots: int
    total_slots: int
    stable_fraction: float
    minimum_agreement: float
    minimum_frames: int
    safe_for_executor: bool = False


def evaluate_temporal_stability(
        frame_predictions, *, minimum_agreement=0.80, minimum_frames=3):
    """Measure slot-level prediction stability across aligned consecutive frames.

    This is intentionally separate from accuracy: repeated agreement can still
    be consistently wrong. The report is therefore never executor-safe by
    itself and must be combined with an independently labelled accuracy report.
    """
    if isinstance(minimum_agreement, bool) or not isinstance(
            minimum_agreement, (int, float)):
        raise ValueError("minimum_agreement must be numeric")
    if not 0 <= minimum_agreement <= 1:
        raise ValueError("minimum_agreement must be between 0 and 1")
    if isinstance(minimum_frames, bool) or not isinstance(minimum_frames, int):
        raise ValueError("minimum_frames must be an integer")
    if minimum_frames <= 0:
        raise ValueError("minimum_frames must be positive")

    per_slot = defaultdict(list)
    for frame_index, predictions in enumerate(frame_predictions):
        seen_keys = set()
        for prediction in predictions:
            if prediction.slot is None:
                raise ValueError(
                    "temporal stability requires explicit aligned slot indices")
            key = (prediction.region, prediction.slot)
            if key in seen_keys:
                raise ValueError(
                    f"duplicate prediction for {prediction.region} slot "
                    f"{prediction.slot} in frame {frame_index}")
            seen_keys.add(key)
            per_slot[key].append(prediction)

    slots = []
    for (region, slot), predictions in sorted(per_slot.items()):
        counts = Counter(item.tile_id for item in predictions)
        confidence_sums = defaultdict(float)
        for item in predictions:
            confidence_sums[item.tile_id] += item.confidence
        voted_tile = max(
            counts,
            key=lambda tile_id: (
                counts[tile_id],
                confidence_sums[tile_id],
                tile_id,
            ),
        )
        matching = [item for item in predictions if item.tile_id == voted_tile]
        frames_seen = len(predictions)
        agreement = len(matching) / frames_seen
        mean_confidence = (
            sum(item.confidence for item in matching) / len(matching)
        )
        stable = (
            frames_seen >= minimum_frames
            and agreement >= minimum_agreement
        )
        slots.append(SlotStability(
            region=region,
            slot=slot,
            frames_seen=frames_seen,
            voted_tile=voted_tile,
            agreement=agreement,
            mean_confidence=mean_confidence,
            stable=stable,
        ))

    stable_slots = sum(item.stable for item in slots)
    total_slots = len(slots)
    return TemporalStabilityReport(
        slots=tuple(slots),
        stable_slots=stable_slots,
        total_slots=total_slots,
        stable_fraction=(
            stable_slots / total_slots if total_slots else 0.0
        ),
        minimum_agreement=float(minimum_agreement),
        minimum_frames=minimum_frames,
        safe_for_executor=False,
    )
