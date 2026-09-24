"""Issue #69: PRIVATE, development-only public-meld appearance diagnostic.

Requires a user-confirmed ZIP, its separately held confirmation declaration,
and the ORIGINAL VIDEO FILES. Before comparison, re-hash every referenced
video and compare all cropped face pixels with the decoded source frame.
No output tile IDs, actions, private hashes or frame pixels enter the report.
Already-inspected, tiny-source diagnostics are NOT blind accuracy or runtime
promotion.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

VALID_TILES = {
    *(f"{s}{n}" for s in "MPS" for n in range(1, 10)),
    "E", "SOUTH", "W", "N", "R", "G", "B",
}


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as src:
        for block in iter(lambda: src.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _normalized(values):
    import numpy as np
    vector = np.asarray(values, dtype=np.float32).ravel().copy()
    vector -= vector.mean()
    length = float(np.linalg.norm(vector))
    return (vector / length) if length > 1e-6 else None


def _features(image):
    """Two explicitly frozen exploratory features. No learned parameters."""
    import cv2
    import numpy as np
    from PIL import Image

    if image.mode != "RGB":
        image = image.convert("RGB")
    raw = np.asarray(
        image.convert("L").resize((32, 48), Image.Resampling.BILINEAR),
        np.float32,
    )
    baseline = _normalized(raw[2:-2, 2:-2])
    rgb = np.asarray(image)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    mask = ((hsv[:, :, 1] < 125) & (hsv[:, :, 2] > 120)).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    height, width = rgb.shape[:2]
    candidates = [
        s for s in stats[1:]
        if s[4] >= height * width * 0.19
        and s[2] >= width * 0.55
        and s[3] >= height * 0.38
    ]
    if not candidates:
        return baseline, None, "no_unambiguous_pale_face"
    if len(candidates) != 1:
        return baseline, None, "ambiguous_pale_faces"
    x, y, w, h = (int(v) for v in candidates[0][:4])
    inset_x = max(1, round(w * 0.04))
    inset_y = max(1, round(h * 0.04))
    face = rgb[
        y + inset_y:y + h - inset_y,
        x + inset_x:x + w - inset_x,
    ]
    if face.shape[0] < 12 or face.shape[1] < 12:
        return baseline, None, "face_too_small"
    gray = cv2.cvtColor(face, cv2.COLOR_RGB2GRAY)
    gray = cv2.resize(gray, (64, 96), interpolation=cv2.INTER_LINEAR)
    gray = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(4, 4)).apply(gray)
    hog = cv2.HOGDescriptor((64, 96), (16, 16), (8, 8), (8, 8), 9)
    normalized = _normalized(hog.compute(gray))
    if normalized is None:
        return baseline, None, "low_texture_face"
    return baseline, normalized, "pale_face_found"


def _check_source_crops(groups, videos_dir: Path, blob_by_face):
    """Byte-exact video AND lossless PNG-to-decoded-source provenance check."""
    import cv2
    import numpy as np
    from PIL import Image

    source_sha = {}
    sha_group = {}
    for group in groups:
        clip, sha, match = (
            group.get(k) for k in ("clip", "video_sha256", "match_group")
        )
        if (
            not isinstance(clip, str)
            or not clip.endswith((".mp4", ".mov"))
            or Path(clip).name != clip
            or not isinstance(sha, str)
            or len(sha) != 64
            or not isinstance(match, str)
            or not match
        ):
            raise ValueError("invalid private video provenance")
        if clip in source_sha and source_sha[clip] != (sha, match):
            raise ValueError("conflicting original-video match group")
        if sha in sha_group and sha_group[sha] != match:
            raise ValueError("identical source video cannot count as distinct match")
        source_sha[clip] = (sha, match)
        sha_group[sha] = match
    for clip, (sha, _) in source_sha.items():
        path = videos_dir / clip
        if not path.is_file() or _file_hash(path) != sha:
            raise ValueError("private original video SHA mismatch before decode")
    verified = 0
    for group in groups:
        cap = cv2.VideoCapture(str(videos_dir / group["clip"]))
        if not cap.isOpened():
            raise ValueError("private video decode unavailable")
        try:
            ms = float(group["timestamp_seconds"]) * 1000
            if ms < 0 or not cap.set(cv2.CAP_PROP_POS_MSEC, ms):
                raise ValueError("cannot seek original source frame")
            ok, bgr = cap.read()
            if (
                not ok
                or abs(
                    int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                    - 1 - group["frame_index"]
                ) > 2
            ):
                raise ValueError("decoded frame index differs from private approval")
        finally:
            cap.release()
        for face in group["faces"]:
            x, y, w, h = face["bbox"]
            if (
                min(x, y) < 0 or min(w, h) < 10
                or x + w > bgr.shape[1]
                or y + h > bgr.shape[0]
            ):
                raise ValueError(
                    "private cropped face bbox outside decoded frame"
                )
            cropped = cv2.cvtColor(
                bgr[y:y + h, x:x + w], cv2.COLOR_BGR2RGB
            )
            with Image.open(
                BytesIO(blob_by_face[face["crop_file"]])
            ) as img:
                if img.format != "PNG":
                    raise ValueError("source crop must be PNG")
                rgb = np.asarray(img.convert("RGB"))
            if not np.array_equal(rgb, cropped):
                raise ValueError(
                    "approved face pixels do not match decoded source"
                )
            verified += 1
    return len(source_sha), verified


def load_confirmed_private_faces(
    archive_path, declaration_path, videos_dir
):
    """Never skip explicit approval or original-video re-verification."""
    from PIL import Image

    declaration = json.loads(
        Path(declaration_path).read_text("utf-8")
    )
    if (
        declaration.get("user_explicitly_confirmed_all") is not True
        or declaration.get("schema_version")
        != "private_meld_review_user_confirmation_v0_1"
    ):
        raise ValueError("independent explicit user confirmation required")
    with ZipFile(archive_path) as archive:
        names = archive.namelist()
        if (
            len(names) != len(set(names)) or len(names) > 100
            or any(
                info.file_size > 4 * 1024 * 1024
                for info in archive.infolist()
            )
        ):
            raise ValueError(
                "unsafe ZIP member count, duplicates, or sizes"
            )
        expected_meta = {
            "private_approved_labels.json",
            "private_cross_match_baseline.json",
            "private_user_declaration.json",
            "reviewed_visual_sheet.jpg", "README.txt",
        }
        if not expected_meta.issubset(names):
            raise ValueError(
                "private approved package missing metadata"
            )
        approved = json.loads(
            archive.read("private_approved_labels.json")
        )
        embedded = json.loads(
            archive.read("private_user_declaration.json")
        )
        if (
            embedded != declaration
            or _hash(
                archive.read("reviewed_visual_sheet.jpg")
            ) != declaration.get("review_sheet_sha256")
            or approved.get("review_sheet_sha256")
            != declaration.get("review_sheet_sha256")
            or approved.get("source_packet_sha256")
            != declaration.get("source_packet_sha256")
            or approved.get("schema_version")
            != "private_existing_user_confirmed_public_faces_v0_1"
            or approved.get("development_only") is not True
            or approved.get("independent_blind_review") is not False
            or approved.get("source_disjoint_holdout") is not False
            or approved.get("formal_promotion_evidence") is not False
            or approved.get("safe_for_runtime") is not False
            or approved.get("safe_for_executor") is not False
            or approved.get("action_kind") != "UNKNOWN"
            or approved.get("actor") != "UNKNOWN"
        ):
            raise ValueError(
                "invalid private approval binding or unsafe label promotion"
            )
        groups = approved.get("groups")
        if (
            not isinstance(groups, list) or not groups
            or len(groups) != approved.get("approved_group_count")
            or [g["group_id"] for g in groups]
            != declaration.get("confirmed_group_ids")
        ):
            raise ValueError(
                "explicit approved group ID order mismatch"
            )
        blobs = {}
        labels = []
        for group in groups:
            faces = group.get("faces")
            if (
                not isinstance(faces, list) or len(faces) != 3
                or group.get("action_kind") != "UNKNOWN"
                or group.get("actor") != "UNKNOWN"
            ):
                raise ValueError(
                    "private group must remain geometry-only"
                )
            for i, face in enumerate(faces, 1):
                key = face.get("crop_file")
                if (
                    not isinstance(key, str)
                    or Path(key).name != key
                    or not key.endswith(".png")
                    or key in blobs
                    or face.get("face_index") != i
                    or face.get("approved_tile_id") not in VALID_TILES
                    or face.get("confirmation_status")
                    != "user_confirmed_from_visual_review_sheet"
                    or face.get("formal_promotion_evidence") is not False
                    or face.get("safe_for_runtime_identity") is not False
                    or face.get("safe_for_executor") is not False
                ):
                    raise ValueError(
                        "invalid or unconfirmed per-face private label"
                    )
                member = "approved_faces/" + key
                if member not in names:
                    raise ValueError("missing private face PNG")
                blob = archive.read(member)
                if _hash(blob) != face.get("crop_sha256"):
                    raise ValueError(
                        "approved private face SHA mismatch"
                    )
                blobs[key] = blob
                labels.append({
                    "match_group": group["match_group"],
                    "clip": group["clip"],
                    "tile_id": face["approved_tile_id"],
                    "image": Image.open(
                        BytesIO(blob)
                    ).convert("RGB"),
                })
        if set(names) != expected_meta | {
            "approved_faces/" + n for n in blobs
        }:
            raise ValueError("unreferenced private ZIP entry")
        if len(labels) != approved.get("approved_face_count"):
            raise ValueError("approved face count mismatch")
    source_count, face_count = _check_source_crops(
        groups, Path(videos_dir), blobs
    )
    if face_count != len(labels):
        raise ValueError("private video/crop count mismatch")
    match_count = len({
        q["match_group"] for q in labels
    })
    if match_count != approved.get("match_group_count"):
        raise ValueError("private original-match count mismatch")
    return labels, source_count, match_count


def compare_verified_private_faces(
    labels, source_clips, original_matches
):
    """Only two fixed diagnostics; blind/runtime promotion always disabled."""
    if original_matches != 2:
        raise ValueError(
            "exploratory comparison requires exactly two original matches"
        )
    rows = []
    for label in labels:
        raw, normalized, reason = _features(label["image"])
        rows.append({
            **{
                k: label[k]
                for k in ("match_group", "clip", "tile_id")
            },
            "raw_gray": raw,
            "face_hog": normalized,
            "face_region_status": reason,
        })
    grouped = Counter(x["match_group"] for x in rows)
    if len(grouped) != 2:
        raise ValueError(
            "duplicate or unknown original-match grouping"
        )
    gallery_group, query_group = (
        g for g, _ in grouped.most_common()
    )
    gallery = [
        x for x in rows if x["match_group"] == gallery_group
    ]
    queries = [
        x for x in rows if x["match_group"] == query_group
    ]
    out = {
        "schema_version":
            "private_public_face_normalization_development_v0_1",
        "previously_inspected": True,
        "user_confirmed_labels": len(rows),
        "source_clips_verified": source_clips,
        "original_matches": original_matches,
        "gallery_faces": len(gallery),
        "query_faces": len(queries),
        "query_class_absent_from_gallery": sum(
            not any(
                g["tile_id"] == q["tile_id"] for g in gallery
            )
            for q in queries
        ),
        "preprocessing_abstentions": Counter(
            x["face_region_status"] for x in rows
        ),
        "source_disjoint_holdout": False,
        "blind_accuracy": None,
        "runtime_prediction": "UNKNOWN",
        "eligible_shadow_queries": 0,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_executor": False,
        "features": {},
    }
    for key in ("raw_gray", "face_hog"):
        shared = []
        for q in queries:
            candidates = [
                g for g in gallery
                if g[key] is not None and q[key] is not None
            ]
            if not any(
                g["tile_id"] == q["tile_id"]
                for g in candidates
            ):
                continue
            ordered = sorted(
                candidates,
                key=lambda g: -float(q[key] @ g[key]),
            )
            first = next(
                i + 1 for i, g in enumerate(ordered)
                if g["tile_id"] == q["tile_id"]
            )
            shared.append(first)
        same = []
        for q in gallery:
            # Different clip here means another HAND, NOT another match.
            candidates = [
                g for g in gallery
                if g["clip"] != q["clip"]
                and g[key] is not None and q[key] is not None
            ]
            if not any(
                g["tile_id"] == q["tile_id"]
                for g in candidates
            ):
                continue
            best = max(
                candidates,
                key=lambda g: float(q[key] @ g[key]),
            )
            same.append(
                best["tile_id"] == q["tile_id"]
            )
        out["features"][key] = {
            "cross_original_match_eligible_queries": len(shared),
            "cross_original_match_true_class_ranks": shared,
            "same_original_match_other_clip_eligible": len(same),
            "same_original_match_other_clip_top1": sum(same),
            "source_disjoint_holdout": False,
            "formal_promotion_evidence": False,
        }
    out["preprocessing_abstentions"] = dict(
        sorted(out["preprocessing_abstentions"].items())
    )
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirmed-zip", required=True)
    parser.add_argument("--user-declaration", required=True)
    parser.add_argument("--existing-videos", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    repo_root = Path(__file__).resolve().parents[2]
    if output == repo_root or repo_root in output.parents:
        raise ValueError(
            "do not write private review reports to public checkout"
        )
    if output.exists():
        raise ValueError(
            "do not overwrite previously frozen private diagnostic"
        )
    labels, clips, matches = load_confirmed_private_faces(
        args.confirmed_zip, args.user_declaration,
        args.existing_videos,
    )
    report = compare_verified_private_faces(
        labels, clips, matches
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        "utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
