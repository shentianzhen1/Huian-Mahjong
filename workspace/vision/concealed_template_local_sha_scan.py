"""Locate unresolved concealed-template source SHA256 values in local archives.

This is a local provenance-recovery helper. It hashes files under one or more
roots and reports only exact SHA256 matches from the frozen recovery queue.
It never infers or writes an original match_group.

The default queue is the current full Runtime concealed identity domain
(``hand_region`` + ``draw_visual``). Historical queues remain supported through
``--queue`` for reproducibility.

When no roots are supplied, the scanner uses the historical local recovery
locations in priority order. Phase 5B originally sourced its blind holdout from
``data/capture_validation``; later Issue #69 private recovery used
``data/issue69_private``. ``references`` is a final local fallback for older
static/image-derived sources. Missing default roots are skipped explicitly and
reported; the scanner never broadens itself to the whole disk.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable


DEFAULT_QUEUE = Path(
    "references/vision/2026-10-07/"
    "concealed_full_domain_lineage_recovery_queue_v0_1.json"
)
DEFAULT_LOCAL_SCAN_ROOTS = (
    Path("data/capture_validation"),
    Path("data/issue69_private"),
    Path("references"),
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


def resolve_scan_roots(
    roots: Iterable[str | Path] | None,
    *,
    project_root: str | Path = ".",
) -> tuple[list[Path], list[Path], bool]:
    """Resolve explicit roots or existing historical defaults.

    Returns ``(scan_roots, missing_default_roots, used_defaults)``. Explicit
    roots are preserved even when currently missing so callers can see that no
    candidates were found there. Default mode keeps only existing roots and
    refuses to silently broaden the search beyond the frozen local locations.
    """
    supplied = [Path(value).expanduser() for value in (roots or [])]
    if supplied:
        return supplied, [], False

    base = Path(project_root).expanduser()
    existing: list[Path] = []
    missing: list[Path] = []
    for relative in DEFAULT_LOCAL_SCAN_ROOTS:
        candidate = base / relative
        if candidate.exists():
            existing.append(candidate)
        else:
            missing.append(candidate)
    if not existing:
        expected = ", ".join(str(base / path) for path in DEFAULT_LOCAL_SCAN_ROOTS)
        raise FileNotFoundError(
            "none of the historical default scan roots exists; pass an explicit "
            f"root or restore one of: {expected}"
        )
    return existing, missing, True


def scan_exact_sha_matches(
    roots: Iterable[str | Path],
    target_shas: set[str],
) -> dict[str, list[str]]:
    """Return exact target SHA matches without inferring lineage.

    Paths are reported exactly as local scan results and should stay local
    unless they are privacy-reviewed before being turned into evidence. Every
    ordinary file is eligible regardless of suffix, so old PNG/JPG sources and
    video/clip derivatives are handled identically.
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


def build_scan_report(
    matches: dict[str, list[str]],
    *,
    scan_roots: Iterable[str | Path] | None = None,
    missing_default_roots: Iterable[str | Path] = (),
    used_default_roots: bool = False,
) -> dict[str, object]:
    found = sum(1 for paths in matches.values() if paths)
    return {
        "schema_version": "concealed_template_local_sha_scan_v0_2",
        "local_only": True,
        "exact_sha_only": True,
        "match_group_inference_allowed": False,
        "used_historical_default_roots": used_default_roots,
        "scan_roots": [str(path) for path in (scan_roots or [])],
        "missing_default_roots": [
            str(path) for path in missing_default_roots
        ],
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
        "match_group_review_required": found > 0,
        "safe_to_auto_bind_match_group": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "roots",
        nargs="*",
        help=(
            "Local files/directories to hash. If omitted, use historical roots: "
            "data/capture_validation, data/issue69_private, references."
        ),
    )
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE))
    parser.add_argument(
        "--output",
        help="Optional LOCAL-ONLY JSON report path; do not commit raw local paths.",
    )
    args = parser.parse_args()

    scan_roots, missing_defaults, used_defaults = resolve_scan_roots(args.roots)
    targets = load_target_shas(args.queue)
    report = build_scan_report(
        scan_exact_sha_matches(scan_roots, targets),
        scan_roots=scan_roots,
        missing_default_roots=missing_defaults,
        used_default_roots=used_defaults,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
