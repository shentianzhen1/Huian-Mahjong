"""Locate unresolved concealed-template source SHA256 values in local archives.

This is a local provenance-recovery helper. It hashes files under one or more
roots and reports only exact SHA256 matches from the frozen recovery queue.
It never infers or writes an original match_group.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable


DEFAULT_QUEUE = Path(
    "references/vision/2026-10-01/"
    "concealed_template_lineage_recovery_queue_v0_1.json"
)


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def load_target_shas(queue_path: str | Path = DEFAULT_QUEUE) -> set[str]:
    payload = json.loads(Path(queue_path).read_text(encoding="utf-8"))
    if payload.get("match_group_inference_allowed") is not False:
        raise ValueError("recovery queue must forbid match-group inference")
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("recovery queue items are required")
    targets = {
        item.get("source_sha256")
        for item in items
        if isinstance(item, dict)
        and item.get("status") == "UNKNOWN_ORIGINAL_MATCH"
        and isinstance(item.get("source_sha256"), str)
    }
    if not targets:
        raise ValueError("recovery queue has no unresolved SHA256 targets")
    return targets


def scan_exact_sha_matches(
    roots: Iterable[str | Path],
    target_shas: set[str],
) -> dict[str, list[str]]:
    """Return exact target SHA matches without inferring lineage.

    Paths are reported exactly as local scan results and should stay local
    unless they are privacy-reviewed before being turned into evidence.
    """
    matches = {sha: [] for sha in sorted(target_shas)}
    seen: set[Path] = set()
    for root_value in roots:
        root = Path(root_value).expanduser()
        candidates = [root] if root.is_file() else (
            sorted(path for path in root.rglob("*") if path.is_file())
            if root.is_dir()
            else []
        )
        for path in candidates:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            digest = sha256_file(path)
            if digest in matches:
                matches[digest].append(str(path))
    return matches


def build_scan_report(matches: dict[str, list[str]]) -> dict[str, object]:
    found = sum(1 for paths in matches.values() if paths)
    return {
        "schema_version": "concealed_template_local_sha_scan_v0_1",
        "local_only": True,
        "exact_sha_only": True,
        "match_group_inference_allowed": False,
        "target_count": len(matches),
        "matched_target_count": found,
        "unmatched_target_count": len(matches) - found,
        "matches": [
            {
                "source_sha256": sha,
                "local_paths": paths,
                "status": "EXACT_SHA_FOUND_NEEDS_MATCH_REVIEW"
                if paths
                else "NOT_FOUND",
            }
            for sha, paths in sorted(matches.items())
        ],
        "safe_to_auto_bind_match_group": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", help="Local files/directories to hash")
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE))
    parser.add_argument(
        "--output",
        help="Optional LOCAL-ONLY JSON report path; do not commit raw local paths.",
    )
    args = parser.parse_args()

    targets = load_target_shas(args.queue)
    report = build_scan_report(scan_exact_sha_matches(args.roots, targets))
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
