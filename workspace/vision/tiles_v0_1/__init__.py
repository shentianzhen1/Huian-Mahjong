"""Offline, review-first recognition prototype for Huian tile regions.

This package does not construct a GameState, call Rules, or operate a UI.
"""

from .postprocess import ObservationConstraints, TilePrediction, validate_observation
from .roi import REGION_NAMES, ROIProfile
from .taxonomy import TILE_CLASSES

__all__ = [
    "ObservationConstraints", "REGION_NAMES", "ROIProfile", "TILE_CLASSES",
    "TilePrediction", "validate_observation",
]
