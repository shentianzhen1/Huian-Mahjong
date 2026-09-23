"""Private, source-locked river identity review audit (#69).

Adjudication is a separate step from the machine-generated, *unlabeled* crop
queue. This module neither guesses a tile nor ingests the frozen action truth.
A reviewer can propose labels, but only a separately signed-off decision may
be counted as approved *development* evidence. No results enter runtime Vision.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
from typing import Any

from workspace.vision.real_video_public_probe import source_sha256
from workspace.vision.source_river_geometry import load_river_manifest
from workspace.vision.tiles_v0_1.taxonomy import HONORS, SUITED

SCHEMA_VERSION = "source_river_review_audit_v0_1"
DECISION_SCHEMA = "source_river_review_decisions_v0_1"
QUEUE_SCHEMA = "source_river_review_queue_v0_1"
_STATUSES = frozenset({"pending", "proposed", "approved", "rejected"})
_TILES = frozenset(SUITED) | frozenset(HONORS)
_SHA = re.compile(r"^[0-9a-f]{64}$")
_PNG = b"\x89PNG\r\n\x1a\n"
_DECISION_FIELDS = frozenset({
    "review_id", "status", "tile_id", "same_physical_tile_as", "evidence_frames",
    "reviewer", "notes",
})


def _read_object(path: Path, label: str) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object")
    return data


def _valid_digest(value: Any) -> bool:
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def _private_path(base: Path, relative: Any) -> Path:
    if (not isinstance(relative, str) or not relative or Path(relative).is_absolute()
            or Path(relative).name != relative or not relative.endswith(".png")):
        raise ValueError("crop_file must be one local PNG basename")
    path = (base / relative).resolve()
    if path.parent != base.resolve():
        raise ValueError("crop must remain in the private queue directory")
    return path


def _png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or not data.startswith(_PNG) or data[12:16] != b"IHDR":
        raise ValueError("crop must have a valid PNG header")
    width, height = struct.unpack(">II", data[16:24])
    if width == 0 or height == 0 or width > 10000 or height > 10000:
        raise ValueError("invalid crop PNG dimensions")
    return width, height


def verify_source_crops(
    video: str | Path, candidates: dict[str, dict[str, Any]],
    queue_directory: Path, frame_size: tuple[int, int],
) -> None:
    """Compare lossless PNG crops to the *actual decoded source frames*.

    Queue hashes alone cannot establish that the crops originated from the
    recording: somebody could replace both a PNG and its declared digest.
    Decode each distinct frame once, never inspect frozen event truth.
    """
    import cv2  # optional Vision dependency, lazily loaded
    import numpy as np
    from PIL import Image

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("cannot decode original video for source pixel verification")
    try:
        if (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))) != tuple(frame_size):
            raise ValueError("source frame dimensions mismatch")
        frames: dict[int, Any] = {}
        for row in candidates.values():
            index = row["frame"]
            if index not in frames:
                if not cap.set(cv2.CAP_PROP_POS_FRAMES, index):
                    raise ValueError("could not seek to source evidence frame")
                ok, bgr = cap.read()
                if not ok:
                    raise ValueError("source evidence frame is missing")
                frames[index] = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            x, y, w, h = row["normalized_bbox"]
            width, height = frame_size
            left, top = round(x * width), round(y * height)
            right, bottom = round((x + w) * width), round((y + h) * height)
            original = frames[index][top:bottom, left:right]
            with Image.open(_private_path(queue_directory, row["crop_file"])) as png:
                actual = np.asarray(png.convert("RGB"))
            if original.shape != actual.shape or not np.array_equal(original, actual):
                raise ValueError("crop pixels do not match decoded original video: " + row["review_id"])
    finally:
        cap.release()


def audit_review(
    *, queue_path: str | Path, decisions_path: str | Path,
    source_video: str | Path, manifest_path: str | Path,
    verify_pixels: bool = True,
) -> dict[str, Any]:
    """Validate source/crop integrity + reviewed decisions; emit counts only.

    `approved` requires an explicit external reviewer and source-frame checks.
    Nothing here verifies who the reviewer is, predicts actions, imports frozen
    truth, or changes runtime identity. All source labels stay private.
    """
    queue_path = Path(queue_path).resolve()
    decisions_path = Path(decisions_path).resolve()
    manifest = load_river_manifest(manifest_path)
    queue = _read_object(queue_path, "queue")
    review = _read_object(decisions_path, "decisions")
    if queue.get("schema_version") != QUEUE_SCHEMA or queue.get("review_kind") != "private_unlabeled_development_geometry":
        raise ValueError("unsupported private unlabeled review queue")
    if queue.get("formal_promotion_evidence") is not False or queue.get("safe_for_executor") is not False or queue.get("label_reuse_forbidden") is not True:
        raise ValueError("queue must preserve development-only/Executor-off gates")
    if (queue.get("source_session") != manifest.source_session
            or queue.get("source_sha256") != manifest.source_sha256
            or not _valid_digest(queue.get("source_sha256"))):
        raise ValueError("queue source lineage mismatch")
    frame_span = queue.get("frame_range")
    if (not isinstance(frame_span, list) or len(frame_span) != 2
            or any(type(x) is not int for x in frame_span)
            or frame_span[0] > frame_span[1]
            or (manifest.reviewed_frame_span is not None and (
                frame_span[0] < manifest.reviewed_frame_span[0]
                or frame_span[1] > manifest.reviewed_frame_span[1]
            ))):
        raise ValueError("queue exceeds explicitly reviewed source interval")
    if source_sha256(Path(source_video)) != manifest.source_sha256:
        raise ValueError("source video SHA256 mismatch")

    queue_digest = hashlib.sha256(queue_path.read_bytes()).hexdigest()
    if (review.get("schema_version") != DECISION_SCHEMA
            or review.get("queue_sha256") != queue_digest
            or review.get("source_session") != manifest.source_session
            or review.get("source_sha256") != manifest.source_sha256
            or review.get("excluded_from_formal_promotion") is not True
            or review.get("review_kind") != "development_visual_review"):
        raise ValueError("decision provenance or development gate mismatch")
    if not isinstance(queue.get("candidates"), list) or not isinstance(review.get("decisions"), list):
        raise ValueError("queue candidates and decisions must be arrays")

    candidates: dict[str, dict[str, Any]] = {}
    for row in queue["candidates"]:
        if not isinstance(row, dict):
            raise ValueError("invalid queue candidate")
        rid = row.get("review_id")
        frame = row.get("frame")
        if (not isinstance(rid, str) or not rid or rid in candidates
                or type(frame) is not int or not frame_span[0] <= frame <= frame_span[1]
                or row.get("screen_side_actor") not in {"player", "opponent"}
                or row.get("review_status") != "pending"
                or any(row.get(k) is not None for k in ("tile_id", "turn_actor", "action_kind"))):
            raise ValueError("queue must contain unique, unlabeled, source-scoped candidates")
        if row.get("crop_file") != rid + ".png" or not _valid_digest(row.get("crop_sha256")):
            raise ValueError("crop name/hash missing or inconsistent")
        image = _private_path(queue_path.parent, row["crop_file"])
        content = image.read_bytes()
        if hashlib.sha256(content).hexdigest() != row["crop_sha256"]:
            raise ValueError("private crop SHA256 mismatch: " + rid)
        width, height = _png_dimensions(content)
        bbox = row.get("normalized_bbox")
        if (not isinstance(bbox, list) or len(bbox) != 4
                or any(type(v) not in (int, float) for v in bbox)
                or not all(0 <= float(v) <= 1 for v in bbox)
                or bbox[2] <= 0 or bbox[3] <= 0
                or bbox[0] + bbox[2] > 1 or bbox[1] + bbox[3] > 1
                or abs(width - round(bbox[2] * manifest.frame_size[0])) > 1
                or abs(height - round(bbox[3] * manifest.frame_size[1])) > 1):
            raise ValueError("crop dimensions inconsistent with tracked source geometry")
        from_zone = manifest.zone(row["screen_side_actor"])
        if (not from_zone.contains(tuple(bbox)) or not from_zone.single(tuple(bbox))
                or row.get("geometry_kind") not in {"single_face", "river_split_face"}):
            raise ValueError("crop geometry lies outside source-reviewed river zone")
        candidates[rid] = row

    if type(verify_pixels) is not bool:
        raise ValueError("verify_pixels must be a boolean")
    if verify_pixels:
        verify_source_crops(source_video, candidates, queue_path.parent, manifest.frame_size)

    decisions: dict[str, dict[str, Any]] = {}
    for row in review["decisions"]:
        if not isinstance(row, dict) or set(row) - _DECISION_FIELDS:
            raise ValueError("decision contains invalid fields (no action or turn labels allowed)")
        rid = row.get("review_id")
        status = row.get("status")
        if not isinstance(rid, str) or rid not in candidates or rid in decisions or status not in _STATUSES:
            raise ValueError("invalid or duplicate review decision")
        tile = row.get("tile_id")
        repeat = row.get("same_physical_tile_as")
        reviewer = row.get("reviewer")
        evidence = row.get("evidence_frames", [])
        if not isinstance(evidence, list) or any(type(f) is not int or not frame_span[0] <= f <= frame_span[1] for f in evidence):
            raise ValueError("evidence_frames must be source-reviewed integer frames")
        if status in {"pending", "rejected"} and (tile is not None or repeat is not None):
            raise ValueError("pending/rejected decisions must not assign identity or repeat")
        if status in {"proposed", "approved"} and tile not in _TILES:
            raise ValueError("identity must be one of the 34 standard project tile classes")
        if status == "approved":
            if (not isinstance(reviewer, str) or not reviewer.strip()
                    or candidates[rid]["frame"] not in evidence):
                raise ValueError("approved label requires explicit reviewer and source frame evidence")
        elif reviewer not in (None, ""):
            raise ValueError("unapproved labels must not carry a signed-off reviewer")
        if repeat is not None:
            prior = candidates.get(repeat)
            current = candidates[rid]
            if (not isinstance(repeat, str) or prior is None or repeat == rid
                    or prior["screen_side_actor"] != current["screen_side_actor"]
                    or prior["frame"] >= current["frame"]):
                raise ValueError("repeat must refer to a prior same-actor candidate")
            if status == "approved" and (prior["frame"] not in evidence
                                         or current["frame"] not in evidence):
                raise ValueError("confirmed repeats need both source frames reviewed")
        decisions[rid] = row
    for rid, row in decisions.items():
        if row.get("status") == "approved" and row.get("same_physical_tile_as") is not None:
            anchor = decisions.get(row["same_physical_tile_as"])
            if (anchor is None or anchor["status"] != "approved"
                    or anchor.get("tile_id") != row["tile_id"]
                    or anchor.get("same_physical_tile_as") is not None):
                raise ValueError("confirmed repeat requires matching approved unique anchor")

    statuses = Counter(decisions.get(rid, {}).get("status", "pending") for rid in candidates)
    approved_unique = sum(row["status"] == "approved" and row.get("same_physical_tile_as") is None
                          for row in decisions.values())
    approved_repeats = sum(row["status"] == "approved" and row.get("same_physical_tile_as") is not None
                           for row in decisions.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "development_only": True,
        "source_disjoint_holdout": False,
        "formal_promotion_evidence": False,
        "runtime_identity_ready": False,
        "safe_for_executor": False,
        "source_pixels_verified": verify_pixels,
        "total_candidates": len(candidates),
        "statuses": {status: statuses[status] for status in sorted(_STATUSES)},
        "approved_unique_tiles": approved_unique if verify_pixels else 0,
        "approved_repeat_tracks": approved_repeats if verify_pixels else 0,
        "signed_off_but_source_pixels_unverified": (
            approved_unique + approved_repeats if not verify_pixels else 0
        ),
        "action_predictions": 0,
        "note": "Private review integrity only; no tiles, crops, video, reviewer identities, or action truth in this summary.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", required=True)
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--video", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    print(json.dumps(audit_review(queue_path=args.queue, decisions_path=args.decisions,
                                  source_video=args.video, manifest_path=args.manifest),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
