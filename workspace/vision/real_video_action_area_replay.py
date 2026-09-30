"""Private source-scoped replay for #69 action-area onset candidates.

The manifest and output contain source identifiers / exact frame indexes and
must stay in ``data/issue69_private``.  Results are development candidates,
never Runtime actions, tile identities or formal promotion evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import deque
import argparse
import hashlib
import json
from pathlib import Path
import re

from workspace.vision.public_action_area_onset import (
    ActionAreaProfile, collapse_action_area_onset_candidates,
    probe_action_area_onset,
)
from workspace.vision.public_meld_gap_onset import SourceScopedOpticalFrame

SCHEMA_VERSION = "source_action_area_geometry_v0_1"
_SHA = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class ActionAreaManifest:
    source_session: str
    source_sha256: str
    frame_size: tuple[int, int]
    reviewed_frame_span: tuple[int, int]
    profiles: tuple[ActionAreaProfile, ...]
    minimum_event_separation_frames: int
    development_only: bool
    excluded_from_formal_promotion: bool

    def __post_init__(self) -> None:
        if (not self.source_session or not _SHA.fullmatch(self.source_sha256)):
            raise ValueError("exact source session and SHA256 required")
        if (len(self.frame_size) != 2
                or any(type(v) is not int or v <= 0 for v in self.frame_size)):
            raise ValueError("frame_size must be positive [width, height]")
        if (len(self.reviewed_frame_span) != 2
                or any(type(v) is not int for v in self.reviewed_frame_span)
                or self.reviewed_frame_span[0] < 0
                or self.reviewed_frame_span[1] < self.reviewed_frame_span[0]):
            raise ValueError("reviewed_frame_span must be increasing")
        if ({profile.actor for profile in self.profiles}
                != {"player", "opponent"} or len(self.profiles) != 2):
            raise ValueError("one action-area profile required per actor")
        if (type(self.minimum_event_separation_frames) is not int
                or self.minimum_event_separation_frames < 2):
            raise ValueError("minimum event separation must be integer >= 2")
        if not self.development_only or not self.excluded_from_formal_promotion:
            raise ValueError("source replay must remain development-only")


def _pair(value, name: str, *, allow_zero: bool = False) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must contain two numbers")
    pair = tuple(float(v) for v in value)
    if ((pair[0] < 0 if allow_zero else pair[0] <= 0)
            or pair[1] < pair[0]):
        raise ValueError(f"invalid {name}")
    return pair


def _region(value, name: str) -> tuple[float, float, float, float]:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f"{name} must contain four numbers")
    region = tuple(float(v) for v in value)
    x, y, width, height = region
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
        raise ValueError(f"invalid normalized {name}")
    return region


def load_action_area_manifest(path: str | Path) -> ActionAreaManifest:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported action-area manifest")
    profiles = []
    for row in data.get("profiles", ()):
        profiles.append(ActionAreaProfile(
            actor=row["actor"],
            onset_region=_region(row["onset_region"], "onset_region"),
            confirmation_region=_region(row["confirmation_region"], "confirmation_region"),
            width_ratio=_pair(row["width_ratio"], "width_ratio"),
            height_ratio=_pair(row["height_ratio"], "height_ratio"),
            area_ratio=_pair(row["area_ratio"], "area_ratio"),
            aspect_ratio=_pair(row.get("aspect_ratio", [.65, 2.5]), "aspect_ratio"),
            centroid_motion_ratio=_pair(
                row.get("centroid_motion_ratio", [0, 1]),
                "centroid_motion_ratio", allow_zero=True,
            ),
        ))
    return ActionAreaManifest(
        source_session=data["source_session"],
        source_sha256=data["source_sha256"],
        frame_size=tuple(data["frame_size"]),
        reviewed_frame_span=tuple(data["reviewed_frame_span"]),
        profiles=tuple(profiles),
        minimum_event_separation_frames=data.get("minimum_event_separation_frames", 12),
        development_only=data.get("development_only") is True,
        excluded_from_formal_promotion=data.get("excluded_from_formal_promotion") is True,
    )


def scan_decoded_action_area_frames(frames, manifest: ActionAreaManifest) -> dict:
    """Scan ordered ``(frame_index, BGR ndarray)`` values from one source."""
    if not isinstance(manifest, ActionAreaManifest):
        raise ValueError("validated ActionAreaManifest required")
    queue = deque(maxlen=3)
    raw = {profile.actor: [] for profile in manifest.profiles}
    decoded = 0
    expected = None
    for frame_index, pixels in frames:
        if type(frame_index) is not int or (expected is not None and frame_index != expected):
            raise ValueError("decoded frames must be strictly contiguous")
        expected = frame_index + 1
        if not manifest.reviewed_frame_span[0] <= frame_index <= manifest.reviewed_frame_span[1]:
            raise ValueError("decoded frame outside reviewed span")
        height, width = pixels.shape[:2]
        if (width, height) != manifest.frame_size:
            raise ValueError("decoded frame resolution does not match manifest")
        queue.append(SourceScopedOpticalFrame(
            manifest.source_session, manifest.source_sha256, 0, frame_index,
            hashlib.sha256(pixels.tobytes()).hexdigest(), pixels, True, True,
        ))
        decoded += 1
        if len(queue) < 3:
            continue
        for profile in manifest.profiles:
            candidate = probe_action_area_onset(
                *queue, profile=profile,
                action_regions_independently_verified=True,
                source_frames_unobscured=True,
            )
            if candidate.status == "ACTION_AREA_ONSET_CANDIDATE_ONLY":
                raw[profile.actor].append(candidate)
    collapsed = {
        actor: collapse_action_area_onset_candidates(
            values,
            minimum_event_separation_frames=manifest.minimum_event_separation_frames,
        ) if values else ()
        for actor, values in raw.items()
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "development_only": True,
        "source_session": manifest.source_session,
        "source_sha256": manifest.source_sha256,
        "frames_decoded": decoded,
        "raw_candidate_counts": {actor: len(values) for actor, values in raw.items()},
        "collapsed_candidate_counts": {actor: len(values) for actor, values in collapsed.items()},
        "candidates": [
            {"frame": item.first_visible_frame,
             "region_actor_hint": item.region_actor_hint,
             "tile": "UNKNOWN", "action_kind": "UNKNOWN"}
            for actor in ("player", "opponent") for item in collapsed.get(actor, ())
        ],
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_executor": False,
    }


def replay_action_areas(video_path: str | Path, manifest_path: str | Path) -> dict:
    import cv2

    video_path = Path(video_path)
    manifest = load_action_area_manifest(manifest_path)
    actual_sha = hashlib.sha256(video_path.read_bytes()).hexdigest()
    if actual_sha != manifest.source_sha256:
        raise ValueError("video SHA256 does not match action-area manifest")
    first, last = manifest.reviewed_frame_span
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError("video could not be opened")

    def decoded():
        index = 0
        try:
            while True:
                ok, pixels = capture.read()
                if not ok:
                    break
                if first <= index <= last:
                    yield index, pixels
                if index >= last:
                    break
                index += 1
        finally:
            capture.release()

    result = scan_decoded_action_area_frames(decoded(), manifest)
    if result["frames_decoded"] != last - first + 1:
        raise ValueError("reviewed video frame span was not fully decoded")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True,
                        help="PRIVATE trace; never commit source identifiers/frames")
    args = parser.parse_args()
    result = replay_action_areas(args.video, args.manifest)
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps({
        "frames_decoded": result["frames_decoded"],
        "collapsed_candidate_counts": result["collapsed_candidate_counts"],
        "safe_for_runtime": result["safe_for_runtime"],
    }))


if __name__ == "__main__":
    main()
