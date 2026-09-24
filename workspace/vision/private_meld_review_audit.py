"""PRIVATE existing-video public meld review packet integrity audit.

A reviewer may propose identities in a separate PRIVATE sidecar only AFTER
source-video hash, exact decoded frame and face crop pixels are verified.
This module never returns approved tile IDs, action truths or promotion
evidence, and must never ingest the packet into Runtime, Hint or Executor.

Neither private video SHA values nor original image pixels belong in GitHub.
"""
from __future__ import annotations

from collections import Counter
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
from typing import Any
from zipfile import ZipFile


_SCHEMA = "private_existing_evidence_review_v0_1"
_REGISTRY_SCHEMA = "private_meld_sources_v0_1"
_CROP = re.compile(r"^[a-zA-Z0-9_-]+[.]png$")
_SHA = re.compile(r"^[0-9a-f]{64}$")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_private_source_registry(path: str | Path) -> dict[str, dict[str, str]]:
    """Independent local SHA/match mapping; never commit this registry."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if (not isinstance(data, dict)
            or data.get("schema_version") != _REGISTRY_SCHEMA
            or not isinstance(data.get("sources"), list)
            or not data["sources"]):
        raise ValueError("invalid private source registry")
    by_clip: dict[str, dict[str, str]] = {}
    by_sha: dict[str, str] = {}
    for source in data["sources"]:
        if not isinstance(source, dict) or set(source) != {
            "clip", "sha256", "match_group"
        }:
            raise ValueError("private source entry has invalid fields")
        clip, sha, group = (
            source["clip"], source["sha256"], source["match_group"]
        )
        if (not isinstance(clip, str) or Path(clip).name != clip
                or not clip.endswith((".mp4", ".mov"))
                or not isinstance(sha, str) or not _SHA.fullmatch(sha)
                or not isinstance(group, str) or not group.strip()
                or clip in by_clip):
            raise ValueError("invalid duplicate/source clip or SHA")
        if sha in by_sha and by_sha[sha] != group:
            raise ValueError("same video SHA assigned different matches")
        by_clip[clip] = source
        by_sha[sha] = group
    return by_clip


def audit_private_meld_packet(
    archive: str | Path,
    source_dir: str | Path,
    registry_path: str | Path,
) -> dict[str, Any]:
    """Fail closed on any failed source/crop checksum or provenance conflict.

    Source images are decoded with the same millisecond seeking used when
    exporting the existing 36-crop private packet. Do NOT claim frame-accurate
    correctness for an extraction made by some other seeking policy.
    """
    registry = load_private_source_registry(registry_path)
    with ZipFile(archive) as z:
        infos = z.infolist()
        names = [item.filename for item in infos]
        if (len(names) != len(set(names)) or "manifest.json" not in names
                or len(names) > 5000
                or any(item.file_size > 4 * 1024 * 1024 for item in infos)
                or any(item.filename != "manifest.json"
                       and not _CROP.fullmatch(item.filename) for item in infos)):
            raise ValueError("unsafe, duplicate or oversized archive member")
        manifest = json.loads(z.read("manifest.json"))
        if (not isinstance(manifest, dict)
                or manifest.get("schema_version") != _SCHEMA
                or manifest.get("development_only") is not True
                or manifest.get("source_disjoint_holdout") is not False
                or manifest.get("requires_human_review") is not True
                or manifest.get("identity_accuracy") is not None
                or not isinstance(manifest.get("groups"), list)
                or not manifest["groups"]
                or manifest.get("extracted_group_count") != len(manifest["groups"])):
            raise ValueError("private packet must be unapproved development evidence")

        # Check ALL file references, group provenance and video hashes BEFORE
        # decoding the first frame, or computing any test/promotion metric.
        seen_faces: set[str] = set()
        source_uses: dict[str, str] = {}
        for group in manifest["groups"]:
            if (not isinstance(group, dict)
                    or group.get("human_approved") is not False
                    or group.get("formal_promotion_evidence") is not False
                    or group.get("tile_identity_policy") != "UNKNOWN"
                    or not isinstance(group.get("faces"), list)
                    or len(group["faces"]) != 3):
                raise ValueError("unreviewed three-face group contract violated")
            clip = group.get("clip")
            known = registry.get(clip) if isinstance(clip, str) else None
            if (known is None or known["sha256"] != group.get("source_video_sha256")
                    or known["match_group"] != group.get("match_group")):
                raise ValueError("source SHA/match registry mismatch")
            source_uses[clip] = known["sha256"]
            for index, face in enumerate(group["faces"]):
                if (not isinstance(face, dict)
                        or face.get("index") != index
                        or face.get("tile_id") != "UNKNOWN"
                        or face.get("review_status") != "pending_human_adjudication"):
                    raise ValueError("individual face not pending/UNKNOWN")
                name = face.get("relative_crop_file")
                if (not isinstance(name, str) or not _CROP.fullmatch(name)
                        or name in seen_faces or name not in names):
                    raise ValueError("missing, duplicate or unsafe face crop")
                seen_faces.add(name)
        if set(names) != seen_faces | {"manifest.json"}:
            raise ValueError("archive includes unreferenced or missing crops")
        if manifest.get("extracted_face_slots") != len(seen_faces):
            raise ValueError("declared face count mismatch")
        for clip, digest in source_uses.items():
            source_file = Path(source_dir) / clip
            if not source_file.is_file() or _sha(source_file) != digest:
                raise ValueError("local video SHA256 mismatch BEFORE decode")

        import cv2
        import numpy as np
        from PIL import Image

        verified = 0
        frame_cache: dict[tuple[str, float], tuple[Any, int]] = {}
        match_counts: Counter[str] = Counter()
        for group in manifest["groups"]:
            clip = group["clip"]
            t = group.get("time_seconds")
            frame_size = group.get("frame_resolution")
            frame_num = group.get("frame_index_approx")
            bbox = group.get("group_pixel_bbox")
            if (type(t) not in (float, int) or t < 0
                    or type(frame_num) is not int or frame_num < 0
                    or not isinstance(frame_size, list)
                    or len(frame_size) != 2
                    or any(type(v) is not int or v <= 0 for v in frame_size)
                    or not isinstance(bbox, list) or len(bbox) != 4
                    or any(type(v) is not int for v in bbox)):
                raise ValueError("source frame/crop geometry fields invalid")
            key = (clip, float(t))
            if key not in frame_cache:
                cap = cv2.VideoCapture(str(Path(source_dir) / clip))
                if not cap.isOpened():
                    raise ValueError("source video cannot be decoded")
                try:
                    if not cap.set(cv2.CAP_PROP_POS_MSEC, float(t) * 1000):
                        raise ValueError("cannot seek reviewed frame")
                    good, bgr = cap.read()
                    if not good:
                        raise ValueError("cannot decode reviewed frame")
                    actual_index = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
                finally:
                    cap.release()
                frame_cache[key] = (bgr, actual_index)
            bgr, actual_index = frame_cache[key]
            height, width = bgr.shape[:2]
            if ([width, height] != frame_size
                    or abs(actual_index - frame_num) > 2):
                raise ValueError("frame resolution/index mismatch")
            gx, gy, gw, gh = bbox
            if (gx < 0 or gy < 0 or gw < 30 or gh < 24
                    or gx + gw > width or gy + gh > height
                    or not 0.50 <= (gw / 3) / gh <= 0.72):
                raise ValueError("not a regular public three-face group")
            expected_x = gx
            for face in group["faces"]:
                coords = face.get("pixel_bbox")
                if (not isinstance(coords, list) or len(coords) != 4
                        or any(type(v) is not int for v in coords)):
                    raise ValueError("invalid face pixel bbox")
                x, y, w, h = coords
                if x != expected_x or y != gy or h != gh or w <= 0:
                    raise ValueError("overlap/gap/incorrect face partition")
                expected_x = x + w
                source_pixels = cv2.cvtColor(
                    bgr[y:y + h, x:x + w], cv2.COLOR_BGR2RGB
                )
                with Image.open(BytesIO(z.read(face["relative_crop_file"]))) as image:
                    if image.format != "PNG":
                        raise ValueError("face crop must be lossless PNG")
                    cropped = np.asarray(image.convert("RGB"))
                if not np.array_equal(cropped, source_pixels):
                    raise ValueError("private crop pixels differ from decoded source")
                verified += 1
            if expected_x != gx + gw:
                raise ValueError("face partition does not cover group")
            match_counts[group["match_group"]] += 1
        return {
            "schema_version": "private_meld_source_pixel_audit_v0_1",
            "source_clips_verified": len(source_uses),
            "original_matches": len(match_counts),
            "source_verified_groups": sum(match_counts.values()),
            "source_verified_faces": verified,
            "per_match_group_counts": dict(sorted(match_counts.items())),
            "approved_identities": 0,
            "source_disjoint_holdout": False,
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--videos", required=True)
    parser.add_argument("--private-registry", required=True)
    args = parser.parse_args()
    result = audit_private_meld_packet(
        args.archive, args.videos, args.private_registry
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
