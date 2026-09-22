"""Development-only public geometry channel profiles.

Profiles narrow the broad Public Tile Detector candidate set. They are derived
from already-reviewed target-room frames and therefore remain development
evidence only. A profile is not an action classifier.

In particular, actor_policy/action_policy="external" means downstream temporal
evidence must provide those semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from workspace.vision.public_candidate_tracker import CandidateChannel
from workspace.vision.public_tile_detector import (
    PublicGeometryCandidate,
    PublicGeometryFrame,
)


SCHEMA_VERSION = "public_channel_profiles_v0_1"
ACTOR_POLICIES = frozenset({"external", "player", "opponent", "system"})
ACTION_POLICIES = frozenset({"external", "none"})


def _bbox(value: Any) -> tuple[float, float, float, float]:
    try:
        items = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise ValueError("zone must contain four numeric values") from exc
    if len(items) != 4:
        raise ValueError("zone must contain x, y, width, height")
    x, y, width, height = items
    if (
        x < 0
        or y < 0
        or width <= 0
        or height <= 0
        or x + width > 1.000001
        or y + height > 1.000001
    ):
        raise ValueError("zone must be normalized inside the frame")
    return items


def _strings(value: Any, name: str) -> tuple[str, ...]:
    if isinstance(value, str):
        raise ValueError(f"{name} must be a sequence")
    result = tuple(str(item) for item in (value or ()))
    if any(not item for item in result):
        raise ValueError(f"{name} contains an empty value")
    return result


@dataclass(frozen=True)
class PublicChannelProfile:
    name: str
    geometry_kinds: tuple[str, ...]
    zones: tuple[tuple[float, float, float, float], ...]
    minimum_zone_coverage: float
    semantic_scope: str
    actor_policy: str
    action_policy: str
    development_only: bool
    evidence_sample_ids: tuple[str, ...]
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name or not self.semantic_scope:
            raise ValueError("channel name and semantic_scope are required")
        object.__setattr__(
            self,
            "geometry_kinds",
            _strings(self.geometry_kinds, "geometry_kinds"),
        )
        if not self.geometry_kinds:
            raise ValueError("channel profile requires geometry_kinds")
        object.__setattr__(
            self,
            "zones",
            tuple(_bbox(zone) for zone in self.zones),
        )
        if not self.zones:
            raise ValueError(
                "development channel profile requires at least one reviewed zone"
            )
        if not 0 < float(self.minimum_zone_coverage) <= 1:
            raise ValueError("minimum_zone_coverage must be within (0, 1]")
        object.__setattr__(
            self,
            "minimum_zone_coverage",
            float(self.minimum_zone_coverage),
        )
        if self.actor_policy not in ACTOR_POLICIES:
            raise ValueError(f"unsupported actor_policy: {self.actor_policy}")
        if self.action_policy not in ACTION_POLICIES:
            raise ValueError(f"unsupported action_policy: {self.action_policy}")
        if not self.development_only:
            raise ValueError("reviewed channel profiles must remain development_only")
        object.__setattr__(
            self,
            "evidence_sample_ids",
            _strings(self.evidence_sample_ids, "evidence_sample_ids"),
        )
        if not self.evidence_sample_ids:
            raise ValueError("channel profile requires evidence_sample_ids")
        object.__setattr__(self, "notes", _strings(self.notes, "notes"))

    def to_candidate_channel(self) -> CandidateChannel:
        return CandidateChannel(
            name=self.name,
            geometry_kinds=self.geometry_kinds,
            zones=self.zones,
            minimum_zone_coverage=self.minimum_zone_coverage,
        )

    def accepts_candidate(self, candidate: PublicGeometryCandidate) -> bool:
        # CandidateChannel only reads geometry_kind + normalized_bbox, which
        # PublicGeometryCandidate also exposes. Keep one acceptance definition.
        return self.to_candidate_channel().accepts(candidate)  # type: ignore[arg-type]


@dataclass(frozen=True)
class PublicChannelManifest:
    profiles: tuple[PublicChannelProfile, ...]
    excluded_from_formal_promotion: bool
    development_only_reason: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        object.__setattr__(self, "profiles", tuple(self.profiles))
        names = [profile.name for profile in self.profiles]
        if len(names) != len(set(names)):
            raise ValueError("duplicate channel profile name")
        if not self.excluded_from_formal_promotion:
            raise ValueError(
                "reviewed channel profiles cannot claim formal promotion eligibility"
            )
        if not self.development_only_reason:
            raise ValueError("development_only_reason is required")

    def profile(self, name: str) -> PublicChannelProfile:
        for profile in self.profiles:
            if profile.name == name:
                return profile
        raise KeyError(name)


@dataclass(frozen=True)
class ChannelCandidateAudit:
    profile_name: str
    candidate_count: int
    selected: tuple[PublicGeometryCandidate, ...]

    def to_dict(self) -> dict:
        return {
            "profile_name": self.profile_name,
            "candidate_count": self.candidate_count,
            "selected": [candidate.to_dict() for candidate in self.selected],
        }


def profile_from_dict(row: dict[str, Any]) -> PublicChannelProfile:
    return PublicChannelProfile(
        name=str(row["name"]),
        geometry_kinds=tuple(row.get("geometry_kinds", ())),
        zones=tuple(row.get("zones", ())),
        minimum_zone_coverage=float(row.get("minimum_zone_coverage", 0.5)),
        semantic_scope=str(row["semantic_scope"]),
        actor_policy=str(row["actor_policy"]),
        action_policy=str(row["action_policy"]),
        development_only=bool(row.get("development_only")),
        evidence_sample_ids=tuple(row.get("evidence_sample_ids", ())),
        notes=tuple(row.get("notes", ())),
    )


def manifest_from_dict(data: dict[str, Any]) -> PublicChannelManifest:
    return PublicChannelManifest(
        profiles=tuple(
            profile_from_dict(row)
            for row in data.get("profiles", ())
        ),
        excluded_from_formal_promotion=bool(
            data.get("excluded_from_formal_promotion")
        ),
        development_only_reason=str(
            data.get("development_only_reason", "")
        ),
        schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
    )


def load_channel_manifest(path: str | Path) -> PublicChannelManifest:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("channel manifest root must be an object")
    return manifest_from_dict(data)


def audit_detection(
    detection: PublicGeometryFrame,
    profile: PublicChannelProfile,
) -> ChannelCandidateAudit:
    selected = tuple(
        candidate
        for candidate in detection.candidates
        if profile.accepts_candidate(candidate)
    )
    return ChannelCandidateAudit(
        profile_name=profile.name,
        candidate_count=len(detection.candidates),
        selected=selected,
    )
