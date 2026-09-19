"""Fixed-region profiles for a single reviewed game-window geometry."""
from dataclasses import dataclass, field
import json
from pathlib import Path


REGION_NAMES = ("hand_region", "draw_region", "gold_region")


def _box(value, name):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(f"{name} must be [x, y, width, height]")
    if any(isinstance(part, bool) or not isinstance(part, int) for part in value):
        raise ValueError(f"{name} must contain integers")
    x, y, width, height = value
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise ValueError(f"{name} must be inside the source image")
    return x, y, width, height


@dataclass(frozen=True)
class ROIProfile:
    source_size: tuple[int, int]
    regions: dict[str, tuple[int, int, int, int]]
    slots: dict[str, tuple[tuple[int, int, int, int], ...]] = field(default_factory=dict)
    calibrated: bool = False
    name: str = "unnamed"
    region_modes: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        width, height = _box((0, 0, *self.source_size), "source_size")[-2:]
        if set(self.regions) != set(REGION_NAMES):
            raise ValueError(f"regions must be exactly {REGION_NAMES}")
        normalized = {}
        for region, value in self.regions.items():
            x, y, box_width, box_height = _box(value, region)
            if x + box_width > width or y + box_height > height:
                raise ValueError(f"{region} exceeds source_size")
            normalized[region] = (x, y, box_width, box_height)
        object.__setattr__(self, "regions", normalized)
        normalized_slots = {}
        for region, values in self.slots.items():
            if region not in REGION_NAMES:
                raise ValueError(f"Unknown slot region: {region}")
            _, _, region_width, region_height = normalized[region]
            slots = tuple(_box(value, f"{region} slot") for value in values)
            if any(x + box_width > region_width or y + box_height > region_height
                   for x, y, box_width, box_height in slots):
                raise ValueError(f"{region} slot exceeds its region")
            normalized_slots[region] = slots
        object.__setattr__(self, "slots", normalized_slots)
        normalized_modes = {}
        for region in REGION_NAMES:
            mode = self.region_modes.get(region, "tile")
            if mode not in ("tile", "marker"):
                raise ValueError(
                    f"{region} mode must be 'tile' or 'marker', got {mode!r}"
                )
            normalized_modes[region] = mode
        unknown_modes = set(self.region_modes) - set(REGION_NAMES)
        if unknown_modes:
            raise ValueError(
                f"Unknown region mode keys: {sorted(unknown_modes)}"
            )
        object.__setattr__(self, "region_modes", normalized_modes)

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            source_size=tuple(data["source_size"]),
            regions={name: tuple(value) for name, value in data["regions"].items()},
            slots={name: tuple(tuple(slot) for slot in values)
                   for name, values in data.get("slots", {}).items()},
            calibrated=bool(data.get("calibrated", False)),
            name=data.get("name", Path(path).stem),
            region_modes=data.get("region_modes", {}),
        )

    def save(self, path):
        payload = {
            "version": "tiles_v0_1", "name": self.name,
            "source_size": list(self.source_size), "calibrated": self.calibrated,
            "regions": {name: list(value) for name, value in self.regions.items()},
            "slots": {name: [list(slot) for slot in values]
                      for name, values in self.slots.items()},
            "region_modes": dict(self.region_modes),
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def region_mode(self, region):
        if region not in REGION_NAMES:
            raise ValueError(f"Unknown region: {region}")
        return self.region_modes[region]

    def crop(self, image, region):
        if not self.calibrated:
            raise ValueError("ROI profile is not calibrated; select regions from a real screenshot first")
        if image.size != self.source_size:
            raise ValueError(f"ROI profile requires {self.source_size}, got {image.size}")
        x, y, width, height = self.regions[region]
        return image.crop((x, y, x + width, y + height))

    def crop_slots(self, image, region):
        crop = self.crop(image, region)
        return tuple(crop.crop((x, y, x + width, y + height))
                     for x, y, width, height in self.slots.get(region, ()))
