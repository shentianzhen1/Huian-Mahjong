"""Hash-verified, private-development asset intake; never a Runtime label loader.

The recovered-crop input records a prior pixel audit. This module rechecks
file identities, not that prior transformation's pixels or Mahjong legality.
No source paths or package pixels are published in the resulting JSON.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re


CLIENT_TILES = tuple(
    [f"P{i}" for i in range(1, 10)]
    + [f"S{i}" for i in range(1, 10)]
    + [f"M{i}" for i in range(1, 10)]
    + ["E", "SOUTH", "W", "N", "R", "G", "B"]
    + [f"F{i}" for i in range(1, 9)]
)
STANDARD_TILES = frozenset(CLIENT_TILES[:34])
_SHA = re.compile(r"^[0-9a-f]{64}$")


def client_tile_to_project(value: int) -> str:
    """Explicit client artwork encoding; this does not add or infer game rules."""
    if type(value) is not int or not 0 <= value < len(CLIENT_TILES):
        raise ValueError("client tile ID must be an integer in 0..41")
    return CLIENT_TILES[value]


def _digest(value: object) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise ValueError("expected a lowercase SHA-256 digest")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verified_file(row: dict, path_key: str, hash_key: str, cache: dict) -> str:
    raw = row.get(path_key)
    if not isinstance(raw, str) or not Path(raw).is_absolute():
        raise ValueError(f"{path_key} must be an absolute private file path")
    path = Path(raw)
    expected = _digest(row.get(hash_key))
    stat = path.stat()
    key = (str(path.resolve()), stat.st_size, stat.st_mtime_ns)
    if key not in cache:
        cache[key] = _sha256(path)
    if cache[key] != expected:
        raise ValueError(f"{path_key} SHA-256 mismatch")
    return expected


def _group(value: object) -> str | None:
    if value is None or value == "UNKNOWN":
        return None
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_.-]+", value) is None:
        raise ValueError("match group must be an opaque identifier or UNKNOWN")
    return value


def source_group_coverage(rows: list[dict], sources: list[dict]) -> dict:
    """Audit real visual regions without treating sessions or package art as matches.

    A named group with unresolved cross-registry independence stays provisional.
    Only explicit confirmed-distinct provenance can count as qualified support.
    This output is diagnostic; it does not grant a Runtime capability.
    """
    index = {}
    group_claims = defaultdict(set)
    for source in sources:
        digest = _digest(source.get("source_sha256"))
        if digest in index:
            raise ValueError("duplicate source SHA")
        if source.get("kind") not in {"video", "image", "package"}:
            raise ValueError("unknown source kind")
        group = _group(source.get("original_match_group"))
        if group is not None and source["kind"] != "package":
            group_claims[group].add(source.get("independent_from_other_registered_matches", "UNKNOWN"))
        index[digest] = source
    if any(len(claims) > 1 for claims in group_claims.values()):
        raise ValueError("conflicting independence claims for one match group")
    buckets = defaultdict(lambda: {
        "labels": 0, "sessions": set(), "groups": set(), "qualified": set(),
        "unknown": set(), "provisional": set(),
    })
    excluded_package_labels = 0
    for row in rows:
        digest = _digest(row.get("source_sha256"))
        if digest not in index:
            raise ValueError("label source SHA is not registered in the input")
        source = index[digest]
        if source["kind"] == "package":
            excluded_package_labels += 1
            continue
        tile = row.get("tile_id")
        if tile not in STANDARD_TILES:
            raise ValueError("real identity support must use a standard tile")
        region = row.get("region")
        region = "draw_visual" if region == "draw_region" else region
        if region not in {"hand_region", "draw_visual", "gold_region", "meld_region"}:
            raise ValueError("unknown visual region")
        bucket = buckets[(region, tile)]
        bucket["labels"] += 1
        if row.get("source_session"):
            bucket["sessions"].add(str(row["source_session"]))
        group = _group(source.get("original_match_group"))
        if group is None:
            bucket["unknown"].add(digest)
        else:
            bucket["groups"].add(group)
            if source.get("independent_from_other_registered_matches") == "CONFIRMED_DISTINCT":
                bucket["qualified"].add(group)
            else:
                bucket["provisional"].add(group)
    return {
        "regions": {
            region: {
                tile: {
                    "reviewed_crop_count": stats["labels"],
                    "stored_session_count": len(stats["sessions"]),
                    "named_match_groups": sorted(stats["groups"]),
                    "qualified_distinct_match_group_count": len(stats["qualified"]),
                    "provisional_match_groups": sorted(stats["provisional"]),
                    "unknown_source_sha256s": sorted(stats["unknown"]),
                    "two_match_support_demonstrated": len(stats["qualified"]) >= 2,
                }
                for (item_region, tile), stats in sorted(buckets.items())
                if item_region == region
            }
            for region in sorted({key[0] for key in buckets})
        },
        "package_labels_excluded_from_real_support": excluded_package_labels,
        "runtime_admission": False,
    }


def build_intake(package_rows: list[dict], crop_rows: list[dict], sources: list[dict]) -> dict:
    """Check the private packet, then return path-free development metadata."""
    if not all(isinstance(rows, list) for rows in (package_rows, crop_rows, sources)):
        raise ValueError("manifest inputs must be lists")
    cache = {}
    package_assets = []
    seen_tiles = set()
    for row in package_rows:
        tile = client_tile_to_project(row.get("client_id"))
        if row.get("project_tile") != tile:
            raise ValueError("client/project tile encoding mismatch")
        if tile in seen_tiles:
            raise ValueError("duplicate package tile")
        if row.get("runtime_admission") is not False:
            raise ValueError("package art must explicitly forbid runtime admission")
        seen_tiles.add(tile)
        hashes = {
            "asset_sha256": _verified_file(row, "derived_image", "derived_sha256", cache),
            "atlas_sha256": _verified_file(row, "atlas", "atlas_sha256", cache),
            "metadata_sha256": _verified_file(row, "metadata", "metadata_sha256", cache),
        }
        package_assets.append({
            "tile_id": tile, "client_id": row["client_id"], **hashes,
            "role": "package_artwork_development", "approved": False,
            "independent_original_match_support": 0,
        })
    if seen_tiles != set(CLIENT_TILES):
        raise ValueError("package artwork requires all 34 standard + 8 flower classes")

    verified_sources = []
    source_shas = set()
    for row in sources:
        digest = _verified_file(row, "local_path", "source_sha256", cache)
        if digest in source_shas:
            raise ValueError("duplicate source SHA")
        source_shas.add(digest)
        verified_sources.append({
            "source_sha256": digest, "kind": row.get("kind"),
            "original_match_group": _group(row.get("original_match_group")) or "UNKNOWN",
            "match_group_authority": row.get("match_group_authority", "existing_source_record"),
            "independent_from_other_registered_matches": row.get(
                "independent_from_other_registered_matches", "UNKNOWN"
            ),
        })
    real_assets = []
    label_indexes = {}
    seen_assets = set()
    for row in crop_rows:
        if row.get("status") != "PIXEL_EXACT_FROM_SHA_VERIFIED_SOURCE" or row.get("pixel_exact") is not True:
            raise ValueError("crop requires a prior successful source pixel audit")
        if row.get("runtime_admitted") is not False or row.get("formal_promotion_evidence") is not False:
            raise ValueError("recovered packet must stay development-only")
        digest = _digest(row.get("source_sha256"))
        if digest not in source_shas:
            raise ValueError("crop references an unverified source")
        asset_hash = _verified_file(row, "restored_image", "restored_asset_sha256", cache)
        if asset_hash != _digest(row.get("current_asset_sha256")):
            raise ValueError("restored/current asset identity mismatch")
        declared = row.get("declared_asset_sha256")
        if declared is not None and asset_hash != _digest(declared):
            raise ValueError("restored/declared asset identity mismatch")
        label_manifest_hash = _verified_file(
            row, "source_label_manifest", "source_label_manifest_sha256", cache
        )
        identifier = row.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("crop ID is required")
        if identifier in seen_assets:
            raise ValueError("duplicate crop ID")
        seen_assets.add(identifier)
        if label_manifest_hash not in label_indexes:
            labels = {}
            for line in Path(row["source_label_manifest"]).read_text(encoding="utf-8-sig").splitlines():
                if not line.strip():
                    continue
                reviewed = json.loads(line)
                key = reviewed.get("id") or reviewed.get("image")
                if not isinstance(key, str) or not key:
                    raise ValueError("reviewed label requires an ID or image")
                if key in labels:
                    raise ValueError("ambiguous duplicate reviewed label ID")
                labels[key] = reviewed
            label_indexes[label_manifest_hash] = labels
        reviewed = label_indexes[label_manifest_hash].get(identifier)
        if reviewed is None or reviewed.get("approved") is False or reviewed.get("status") in {"rejected", "pending"} or not (reviewed.get("approved") is True or reviewed.get("status") == "approved"):
            raise ValueError("crop must reference an approved reviewed label")
        expected = {
            "tile_id": reviewed.get("tile_id"), "region": reviewed.get("region"),
            "source_sha256": reviewed.get("sha256", reviewed.get("source_sha256")),
            "source_session": reviewed.get("source_session"),
            "source_frame": reviewed.get("source_frame"),
            "template_image": reviewed.get("image"),
            "crop_bbox": reviewed.get("crop_bbox", reviewed.get("bbox")),
        }
        for field, value in expected.items():
            if row.get(field) != value:
                raise ValueError(f"crop/reviewed label {field} mismatch")
        bbox = expected["crop_bbox"]
        if not isinstance(bbox, list) or len(bbox) != 4 or any(type(v) is not int for v in bbox) or min(bbox[:2]) < 0 or min(bbox[2:]) <= 0:
            raise ValueError("reviewed crop bbox must be nonnegative with positive dimensions")
        if reviewed.get("asset_sha256") is not None and _digest(reviewed["asset_sha256"]) != asset_hash:
            raise ValueError("crop/reviewed label asset SHA mismatch")
        real_assets.append({
            "id_sha256": hashlib.sha256(identifier.encode()).hexdigest(),
            "tile_id": row["tile_id"], "region": row["region"],
            "source_sha256": digest, "source_session": row.get("source_session"),
            "source_frame": row.get("source_frame"), "asset_sha256": asset_hash,
            "source_label_manifest_sha256": label_manifest_hash,
            "role": "recovered_reviewed_development_crop", "approved": False,
            "prior_pixel_audit": "reported_success; file identity rechecked by this intake",
        })
    coverage = source_group_coverage(real_assets, verified_sources)
    return {
        "schema_version": "huian_development_asset_intake_v0_1",
        "package_assets": sorted(package_assets, key=lambda row: row["client_id"]),
        "real_assets": sorted(real_assets, key=lambda row: row["id_sha256"]),
        "sources": sorted(verified_sources, key=lambda row: row["source_sha256"]),
        "source_coverage": coverage,
        "counts": {"package_standard_classes": 34, "package_flower_classes": 8,
                   "real_crops": len(real_assets), "verified_source_files": len(verified_sources)},
        "runtime_admission": False, "formal_promotion_evidence": False,
        "safe_for_hint": False, "safe_for_executor": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-map", required=True)
    parser.add_argument("--recovery-manifest", required=True)
    parser.add_argument("--source-records", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    inputs = [json.loads(Path(p).read_text(encoding="utf-8")) for p in (
        args.package_map, args.recovery_manifest, args.source_records
    )]
    result = build_intake(*inputs)
    # Exclusive creation avoids overwriting a previous evidence bundle.
    with Path(args.output).open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
