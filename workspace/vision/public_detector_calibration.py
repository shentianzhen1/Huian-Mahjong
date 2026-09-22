"""Development calibration manifest for public Mahjong UI detectors.

This module validates archived real-frame calibration records without pretending
that unlabeled pixel regions are already known. It is intentionally separate
from formal source-disjoint Runtime Vision promotion evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable


SCHEMA_VERSION = "public_detector_calibration_v0_1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
ACTORS = frozenset({"player", "opponent", "system"})
TARGETS = frozenset({
    "discard",
    "meld",
    "hand_reference",
    "youjin_state",
    "settlement",
})
STATUSES = frozenset({"fact_locked_bbox_pending", "bbox_reviewed", "fact_only"})


def _strings(value: Any, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        raise ValueError(f"{name} must be a sequence")
    result = tuple(str(item) for item in value)
    if any(not item for item in result):
        raise ValueError(f"{name} contains an empty string")
    return result


def _bbox(value: Any) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    try:
        values = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise ValueError("bbox must be null or four numbers") from exc
    if len(values) != 4:
        raise ValueError("bbox must contain x, y, width, height")
    x, y, width, height = values
    if (
        x < 0
        or y < 0
        or width <= 0
        or height <= 0
        or x + width > 1.000001
        or y + height > 1.000001
    ):
        raise ValueError("bbox must be normalized inside the image")
    return values


@dataclass(frozen=True)
class CalibrationSample:
    sample_id: str
    source_session: str
    source_sha256: str
    image_path: str
    image_sha256: str
    frame_index: int
    time_ms: int
    actor: str
    target: str
    expected_tile: str | None = None
    expected_tiles: tuple[str, ...] = ()
    bbox: tuple[float, float, float, float] | None = None
    status: str = "fact_locked_bbox_pending"
    observation: str = ""
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.sample_id or not self.source_session:
            raise ValueError("sample_id and source_session are required")
        for name in ("source_sha256", "image_sha256"):
            value = str(getattr(self, name)).lower()
            if not _SHA256.fullmatch(value):
                raise ValueError(f"{name} must be a SHA256 hex digest")
            object.__setattr__(self, name, value)
        if not self.image_path or Path(self.image_path).is_absolute():
            raise ValueError("image_path must be a nonempty repository-relative path")
        if isinstance(self.frame_index, bool) or not isinstance(self.frame_index, int) or self.frame_index < 0:
            raise ValueError("frame_index must be a nonnegative integer")
        if isinstance(self.time_ms, bool) or not isinstance(self.time_ms, int) or self.time_ms < 0:
            raise ValueError("time_ms must be a nonnegative integer")
        if self.actor not in ACTORS:
            raise ValueError(f"unsupported actor: {self.actor}")
        if self.target not in TARGETS:
            raise ValueError(f"unsupported target: {self.target}")
        if self.status not in STATUSES:
            raise ValueError(f"unsupported status: {self.status}")
        if self.expected_tile == "":
            raise ValueError("expected_tile cannot be empty")
        object.__setattr__(
            self,
            "expected_tiles",
            _strings(self.expected_tiles, "expected_tiles"),
        )
        object.__setattr__(self, "bbox", _bbox(self.bbox))
        object.__setattr__(self, "notes", _strings(self.notes, "notes"))

        if self.status == "bbox_reviewed" and self.bbox is None:
            raise ValueError("bbox_reviewed requires bbox")
        if self.target == "discard" and not self.expected_tile:
            raise ValueError("discard sample requires expected_tile")
        if self.target == "meld" and len(self.expected_tiles) not in {3, 4}:
            raise ValueError("meld sample requires 3 or 4 expected_tiles")


@dataclass(frozen=True)
class CalibrationManifest:
    samples: tuple[CalibrationSample, ...]
    excluded_from_formal_promotion: bool
    development_only_reason: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        object.__setattr__(self, "samples", tuple(self.samples))
        ids = [sample.sample_id for sample in self.samples]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate sample_id")
        if not self.excluded_from_formal_promotion:
            raise ValueError(
                "archived reviewed frames must stay excluded from formal promotion"
            )
        if not self.development_only_reason:
            raise ValueError("development_only_reason is required")


def sample_from_dict(row: dict[str, Any]) -> CalibrationSample:
    return CalibrationSample(
        sample_id=row["sample_id"],
        source_session=row["source_session"],
        source_sha256=row["source_sha256"],
        image_path=row["image_path"],
        image_sha256=row["image_sha256"],
        frame_index=row["frame_index"],
        time_ms=row["time_ms"],
        actor=row["actor"],
        target=row["target"],
        expected_tile=row.get("expected_tile"),
        expected_tiles=tuple(row.get("expected_tiles", ())),
        bbox=row.get("bbox"),
        status=row.get("status", "fact_locked_bbox_pending"),
        observation=row.get("observation", ""),
        notes=tuple(row.get("notes", ())),
    )


def manifest_from_dict(data: dict[str, Any]) -> CalibrationManifest:
    return CalibrationManifest(
        samples=tuple(sample_from_dict(row) for row in data.get("samples", ())),
        excluded_from_formal_promotion=bool(
            data.get("excluded_from_formal_promotion")
        ),
        development_only_reason=str(data.get("development_only_reason", "")),
        schema_version=data.get("schema_version", SCHEMA_VERSION),
    )


def load_manifest(path: str | Path) -> CalibrationManifest:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest root must be an object")
    return manifest_from_dict(data)


def readiness_report(manifest: CalibrationManifest) -> dict[str, Any]:
    by_target = Counter(sample.target for sample in manifest.samples)
    bbox_ready = Counter(
        sample.target for sample in manifest.samples if sample.bbox is not None
    )
    sessions_by_target: dict[str, set[str]] = {
        target: set() for target in TARGETS
    }
    for sample in manifest.samples:
        sessions_by_target[sample.target].add(sample.source_session)

    return {
        "schema_version": manifest.schema_version,
        "samples": len(manifest.samples),
        "source_sessions": len({sample.source_session for sample in manifest.samples}),
        "by_target": dict(sorted(by_target.items())),
        "bbox_ready_by_target": dict(sorted(bbox_ready.items())),
        "source_sessions_by_target": {
            target: len(sessions)
            for target, sessions in sorted(sessions_by_target.items())
            if sessions
        },
        "public_tile_detector_bbox_ready": (
            bbox_ready["discard"] >= 5
            and len(sessions_by_target["discard"]) >= 2
            and bbox_ready["meld"] >= 5
            and len(sessions_by_target["meld"]) >= 2
        ),
        "formal_promotion_eligible": False,
        "formal_promotion_reason": (
            "archived reviewed development evidence; source-disjoint promotion "
            "requires a separate untouched batch"
        ),
    }


def verify_repository_files(
    manifest: CalibrationManifest,
    repository_root: str | Path,
) -> tuple[str, ...]:
    """Return deterministic file-integrity problems for committed evidence frames."""
    root = Path(repository_root)
    issues: list[str] = []
    for sample in manifest.samples:
        path = root / sample.image_path
        if not path.is_file():
            issues.append(f"{sample.sample_id}:missing_file")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != sample.image_sha256:
            issues.append(f"{sample.sample_id}:sha256_mismatch")
    return tuple(issues)


def pending_bbox_samples(
    manifest: CalibrationManifest,
    *,
    targets: Iterable[str] = ("discard", "meld"),
) -> tuple[CalibrationSample, ...]:
    targets = frozenset(targets)
    unknown = targets - TARGETS
    if unknown:
        raise ValueError(f"unknown calibration targets: {sorted(unknown)}")
    return tuple(
        sample
        for sample in manifest.samples
        if sample.target in targets and sample.bbox is None
    )


def bbox_review_template(manifest: CalibrationManifest) -> dict[str, Any]:
    """Create a small manual-review payload without inventing pixel coordinates."""
    return {
        "schema_version": "public_detector_bbox_review_v0_1",
        "instructions": (
            "Review the committed image and fill normalized bbox=[x,y,width,height] "
            "around the public tile/group target. Do not infer hidden tiles. "
            "Keep replay-overlay occlusion notes explicit."
        ),
        "samples": [
            {
                "sample_id": sample.sample_id,
                "image_path": sample.image_path,
                "actor": sample.actor,
                "target": sample.target,
                "expected_tile": sample.expected_tile,
                "expected_tiles": list(sample.expected_tiles),
                "observation": sample.observation,
                "bbox": None,
                "reviewer": None,
                "notes": list(sample.notes),
            }
            for sample in pending_bbox_samples(manifest)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate/report Public Detector development calibration"
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--bbox-template")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    report = readiness_report(manifest)
    report["file_integrity_issues"] = list(
        verify_repository_files(manifest, args.repository_root)
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.bbox_template:
        output = Path(args.bbox_template)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(bbox_review_template(manifest), ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
