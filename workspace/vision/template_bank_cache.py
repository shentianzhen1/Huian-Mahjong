"""Content-addressed disk cache for the balanced hand-template SIFT bank.

Why
---
`public_meld_synthetic_transfer._build_hand_template_bank` computes two SIFT
descriptor sets per hand template (the canonical face plus every
`render_self_meld_variants` variant). Running the Vision test suite recomputes
that bank from scratch every time, which made a single fusion test the largest
cost in the whole suite.

The bank is a pure function of the files under the dataset root, so it can be
cached on disk and invalidated by hashing that root's contents. A changed
template changes the signature and the cache is rebuilt, so a stale bank is not
possible.

This module is a helper only. It does not change detector, classifier, or
threshold behaviour, and it is not imported by the package runtime.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import sys
import tempfile
from pathlib import Path

SCHEMA_VERSION = "hand_template_bank_cache_v0_1"
# Bump when the bank's construction or record layout changes so old caches are
# ignored rather than mis-read.
BUILD_REVISION = 1

_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def _iter_assets(dataset_root: Path):
    for path in sorted(dataset_root.rglob("*")):
        if path.is_file() and path.suffix.lower() in _SUFFIXES:
            yield path


def dataset_signature(dataset_root: str | os.PathLike[str]) -> str:
    """Hash every asset path, size and mtime under the dataset root."""
    root = Path(dataset_root).resolve()
    if not root.is_dir():
        raise ValueError(f"dataset root is not a directory: {root}")
    digest = hashlib.sha256()
    digest.update(f"{SCHEMA_VERSION}|{BUILD_REVISION}\0".encode())
    count = 0
    for path in _iter_assets(root):
        stat = path.stat()
        digest.update(
            f"{path.relative_to(root).as_posix()}|{stat.st_size}|{stat.st_mtime_ns}\0".encode()
        )
        count += 1
    digest.update(f"count={count}".encode())
    return digest.hexdigest()


def cache_path(
    dataset_root: str | os.PathLike[str],
    cache_dir: str | os.PathLike[str] | None = None,
) -> Path:
    root = Path(dataset_root).resolve()
    directory = (
        Path(cache_dir)
        if cache_dir is not None
        else Path(tempfile.gettempdir()) / "huian_vision_cache"
    )
    return directory / f"hand_template_bank_{dataset_signature(root)}.pkl"


def load_or_build(
    dataset_root: str | os.PathLike[str],
    builder,
    *,
    cache_dir: str | os.PathLike[str] | None = None,
    verbose: bool = False,
):
    """Return the cached bank for `dataset_root`, building it on a miss.

    `builder(dataset_root: Path)` produces the value to cache. On any cache
    failure the value is built directly, so a damaged cache can only cost time,
    never correctness.
    """
    root = Path(dataset_root).resolve()
    try:
        signature = dataset_signature(root)
    except (ValueError, OSError):
        return builder(root)

    directory = (
        Path(cache_dir)
        if cache_dir is not None
        else Path(tempfile.gettempdir()) / "huian_vision_cache"
    )
    target = directory / f"hand_template_bank_{signature}.pkl"

    if target.is_file():
        try:
            with target.open("rb") as handle:
                payload = pickle.load(handle)
            if (
                isinstance(payload, dict)
                and payload.get("schema_version") == SCHEMA_VERSION
                and payload.get("build_revision") == BUILD_REVISION
                and payload.get("dataset_root") == str(root)
                and payload.get("signature") == signature
            ):
                if verbose:
                    print(f"[vision-cache] hit {target.name}", file=sys.stderr)
                return payload["bank"]
        except Exception:
            # A truncated or incompatible cache is not an error: rebuild.
            pass

    bank = builder(root)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "build_revision": BUILD_REVISION,
            "dataset_root": str(root),
            "signature": signature,
            "bank": bank,
        }
        tmp = target.with_suffix(".pkl.tmp")
        with tmp.open("wb") as handle:
            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, target)
        if verbose:
            print(f"[vision-cache] stored {target.name}", file=sys.stderr)
    except Exception:
        # Caching is best effort; never fail the caller because of it.
        pass
    return bank


def describe(
    dataset_root: str | os.PathLike[str],
    cache_dir: str | os.PathLike[str] | None = None,
) -> dict:
    """Report the cache state without building anything."""
    root = Path(dataset_root).resolve()
    target = cache_path(root, cache_dir)
    return {
        "schema_version": SCHEMA_VERSION,
        "build_revision": BUILD_REVISION,
        "dataset_root": str(root),
        "signature": dataset_signature(root),
        "cache_file": str(target),
        "cached": target.is_file(),
        "cache_bytes": target.stat().st_size if target.is_file() else 0,
    }


if __name__ == "__main__":
    print(json.dumps(describe(sys.argv[1] if len(sys.argv) > 1 else "dataset/tiles_runtime_v0_2"), indent=2))
