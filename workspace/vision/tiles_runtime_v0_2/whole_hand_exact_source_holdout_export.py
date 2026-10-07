"""Development-only whole-hand export with exact-source label exclusion.

This wrapper never mutates the committed Runtime dataset.  It builds a private
scratch view of the dataset, removes labels whose exact source SHA-256 matches
the query source (plus any explicitly requested SHA values), and then invokes
the frozen Runtime V0.2 whole-hand baseline exporter on that scratch view.

Exact-source exclusion is useful for detecting direct template leakage.  It is
*not* proof of original-match-disjoint evaluation: another derivative/source
file from the same original match could still remain unless its reviewed
lineage is also excluded separately.  Reports therefore fail closed and never
claim formal promotion evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory
from typing import Iterable

from .whole_hand_baseline_export import export_baseline, _load_truth_seed


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _normalize_shas(values: Iterable[str]) -> tuple[str, ...]:
    normalized = []
    for value in values:
        sha = str(value).strip().lower()
        if not _SHA256.fullmatch(sha):
            raise ValueError(f"invalid SHA-256 exclusion: {value!r}")
        normalized.append(sha)
    return tuple(sorted(set(normalized)))


def _filter_label_rows(rows: Iterable[dict], excluded_shas: Iterable[str]) -> tuple[list[dict], dict]:
    excluded = set(_normalize_shas(excluded_shas))
    kept: list[dict] = []
    removed: list[dict] = []
    for row in rows:
        source_sha = str(row.get("sha256") or "").lower()
        if source_sha in excluded:
            removed.append(row)
        else:
            kept.append(row)
    return kept, {
        "excluded_source_shas": sorted(excluded),
        "input_label_count": len(kept) + len(removed),
        "kept_label_count": len(kept),
        "excluded_label_count": len(removed),
        "excluded_gold_skin_label_count": sum(bool(row.get("gold_skin_only")) for row in removed),
        "excluded_tile_ids": sorted({str(row.get("tile_id")) for row in removed if row.get("tile_id")}),
        "filter_key": "exact_source_sha256",
    }


def _labels_path(root: Path) -> Path:
    runtime = root / "labels.jsonl"
    if runtime.is_file():
        return runtime
    legacy = root / "labels" / "tiles.jsonl"
    if legacy.is_file():
        return legacy
    raise ValueError(f"dataset has no labels file: {root}")


def _link_or_copy(source: str, destination: str) -> str:
    try:
        os.link(source, destination)
        return destination
    except OSError:
        return shutil.copy2(source, destination)


def _build_filtered_dataset_view(dataset_root: Path, scratch_root: Path, excluded_shas: Iterable[str]) -> tuple[Path, dict]:
    source_root = dataset_root.resolve()
    view_root = scratch_root / "dataset_exact_source_filtered"
    shutil.copytree(source_root, view_root, copy_function=_link_or_copy)

    labels_path = _labels_path(view_root)
    rows = [json.loads(line) for line in labels_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    kept, stats = _filter_label_rows(rows, excluded_shas)
    labels_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in kept),
        encoding="utf-8",
    )
    return view_root, stats


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def export_exact_source_holdout(
    video_path: Path,
    truth_seed_path: Path,
    dataset_root: Path,
    output_dir: Path,
    *,
    additional_excluded_shas: Iterable[str] = (),
) -> dict:
    seed = _load_truth_seed(truth_seed_path)
    video_sha = _sha256(video_path)
    truth_sha = str(seed["source"].get("sha256") or "").lower()
    if truth_sha and video_sha.lower() != truth_sha:
        raise ValueError("private video SHA-256 does not match truth seed")

    exclusions = _normalize_shas((video_sha, *tuple(additional_excluded_shas)))
    output_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="huian_whole_hand_exact_source_") as temporary:
        filtered_root, filter_stats = _build_filtered_dataset_view(
            dataset_root,
            Path(temporary),
            exclusions,
        )
        report = export_baseline(
            video_path,
            truth_seed_path,
            filtered_root,
            output_dir,
        )

    report["status"] = "PRIVATE_BASELINE_EXPORT_REQUIRES_CROP_REVIEW_EXACT_SOURCE_FILTERED"
    report["evaluation_filter"] = {
        **filter_stats,
        "truth_source_sha_excluded": video_sha in exclusions,
        "committed_runtime_dataset_mutated": False,
        "runtime_threshold_changed": False,
        "formal_original_match_disjointness_established": False,
        "interpretation": (
            "Direct exact-source template leakage is removed. This alone does not prove "
            "original-match-disjoint validation; reviewed lineage must also rule out other "
            "files/derivatives from the same original match."
        ),
    }
    report["safe_for_runtime_change"] = False
    report["safe_for_hint_promotion"] = False
    report["safe_for_executor"] = False
    (output_dir / "baseline_export.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export frozen whole-hand baseline after excluding exact query-source labels"
    )
    parser.add_argument("video")
    parser.add_argument("truth_seed")
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--exclude-source-sha",
        action="append",
        default=[],
        help="additional exact source SHA-256 to exclude; may be repeated",
    )
    args = parser.parse_args()
    report = export_exact_source_holdout(
        Path(args.video),
        Path(args.truth_seed),
        Path(args.dataset),
        Path(args.output),
        additional_excluded_shas=args.exclude_source_sha,
    )
    print(json.dumps({
        "schema_version": report["schema_version"],
        "sample_count": report["sample_count"],
        "confidence_threshold": report["confidence_threshold"],
        "evaluation_filter": report["evaluation_filter"],
        "report": str(Path(args.output) / "baseline_export.json"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
