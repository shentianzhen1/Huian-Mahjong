"""Restore a private development bank; never alter the supplied Runtime bank."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import zipfile

from workspace.vision.tiles_v0_1.labels import approved_labels
from workspace.vision.tiles_v0_1.taxonomy import HONORS, SUITED

MANIFESTS = ("support19m8_metadata.json", "support18_metadata.json")


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _valid_hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def restore_candidate(package, baseline, destination):
    package, baseline, destination = map(lambda p: Path(p).resolve(), (package, baseline, destination))
    if destination.exists():
        raise ValueError("destination must not exist; no files will be overwritten")
    if baseline == destination or baseline in destination.parents or destination in baseline.parents:
        raise ValueError("candidate and Runtime bank must be separate directories")
    if not (baseline / "labels.jsonl").is_file():
        raise ValueError("baseline must contain labels.jsonl")
    base_labels = approved_labels(baseline)
    existing = {r["image"] for r in base_labels}
    payloads, seen = [], set()
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate archive entry")
        manifests = [n for n in MANIFESTS if n in names]
        if len(manifests) != 1:
            raise ValueError("exactly one supported private metadata manifest is required")
        info = archive.getinfo(manifests[0])
        if info.file_size > 1024 * 1024:
            raise ValueError("manifest too large")
        rows = json.loads(archive.read(info))
        if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
            raise ValueError("manifest must be a nonempty bounded array")
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("invalid metadata row")
            image = row.get("image")
            path = PurePosixPath(image) if isinstance(image, str) else PurePosixPath()
            if (not image or "\\" in image or path.is_absolute() or ".." in path.parts
                    or path.as_posix() != image or path.parts[:2] != ("templates", "hand")
                    or path.suffix != ".png"):
                raise ValueError("invalid private template path")
            if image in seen or image in existing or (baseline / image).exists():
                raise ValueError("private template collision")
            seen.add(image)
            if (row.get("approved") is not True or row.get("status") != "approved"
                    or row.get("region") != "hand_region" or row.get("gold_skin_only", False) is not False
                    or row.get("tile_id") not in set(SUITED) | set(HONORS)
                    or not row.get("source_session")
                    or not _valid_hash(row.get("sha256")) or not _valid_hash(row.get("asset_sha256"))):
                raise ValueError("unqualified development support metadata")
            info = archive.getinfo(image)
            if info.file_size > 1024 * 1024:
                raise ValueError("template too large")
            pixels = archive.read(info)
            if _hash(pixels) != row["asset_sha256"]:
                raise ValueError("private template SHA256 mismatch")
            payloads.append((image, pixels))
    # Validate everything before creating a new output. No raw extractall.
    shutil.copytree(baseline, destination)
    for image, pixels in payloads:
        target = destination / image
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(pixels)
    with (destination / "labels.jsonl").open("a", encoding="utf-8") as stream:
        stream.write("\n")
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    result = {"development_only": True, "support_count": len(rows),
              "support_rows_without_embedded_match_group": sum(not r.get("original_match_group") for r in rows),
              "source_session_is_independence_evidence": False,
              "baseline_label_count": len(base_labels), "candidate_label_count": len(approved_labels(destination)),
              "package_sha256": _hash(package.read_bytes()), "threshold": 0.82,
              "safe_for_runtime": False, "safe_for_hint": False, "safe_for_executor": False,
              "baseline_unchanged": True}
    (destination / "private_candidate_restore.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package")
    parser.add_argument("--baseline", default="dataset/tiles_runtime_v0_2")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(restore_candidate(args.package, args.baseline, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
