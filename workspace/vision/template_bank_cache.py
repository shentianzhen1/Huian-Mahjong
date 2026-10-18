"""Content-addressed disk cache for the balanced hand-template SIFT bank.

Why
---
`public_meld_synthetic_transfer._build_hand_template_bank` computes two SIFT
descriptor sets per hand template (the canonical face plus every
`render_self_meld_variants` variant). Running the Vision test suite recomputes
that bank from scratch every time, which made a single fusion test the largest
cost in the whole suite.

The cache fingerprints image bytes and the active label manifests, including
reviewed additions. File size and timestamps are not evidence of unchanged
pixels or labels. Dataset changes during a build prevent cache publication.

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

from workspace.vision.tiles_v0_1.labels import _label_paths, approved_labels

SCHEMA_VERSION = "hand_template_bank_cache_v0_2"
# Bump when the bank's construction or record layout changes so old caches are
# ignored rather than mis-read.
BUILD_REVISION = 2

_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".tif", ".tiff",
    ".pgm", ".ppm", ".pbm", ".pnm",
}


def _iter_assets(dataset_root: Path):
    paths = set(_label_paths(dataset_root))
    # Pillow reads file contents, so a reviewed image may use a nonstandard
    # extension. Match the bank's eligible label domain as well as image suffixes.
    for row in approved_labels(dataset_root):
        if row.get("region") != "hand_region" or row.get("gold_skin_only"):
            continue
        image = row.get("image")
        if isinstance(image, str) and isinstance(row.get("tile_id"), str):
            path = (dataset_root / image).resolve()
            if dataset_root not in path.parents:
                raise ValueError("hand template path escapes dataset root")
            paths.add(path)
    paths.update(
        path for path in dataset_root.rglob("*")
        if path.is_file() and path.suffix.lower() in _SUFFIXES
    )
    yield from sorted(paths)


def dataset_signature(dataset_root: str | os.PathLike[str]) -> str:
    """Hash the dataset identity, image bytes and active label-file bytes."""
    root = Path(dataset_root).resolve()
    if not root.is_dir():
        raise ValueError(f"dataset root is not a directory: {root}")
    digest = hashlib.sha256()
    digest.update(f"{SCHEMA_VERSION}|{BUILD_REVISION}\0".encode())
    digest.update(str(root).encode("utf-8") + b"\0")
    count = 0
    for path in _iter_assets(root):
        content_digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                content_digest.update(chunk)
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(content_digest.digest())
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
                and dataset_signature(root) == signature
            ):
                if verbose:
                    print(f"[vision-cache] hit {target.name}", file=sys.stderr)
                return payload["bank"]
        except Exception:
            # A truncated or incompatible cache is not an error: rebuild.
            pass

    bank = builder(root)
    tmp = None
    try:
        if dataset_signature(root) != signature:
            return bank
        directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "build_revision": BUILD_REVISION,
            "dataset_root": str(root),
            "signature": signature,
            "bank": bank,
        }
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=directory, prefix=target.name + ".", suffix=".tmp",
            delete=False,
        ) as handle:
            tmp = Path(handle.name)
            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, target)
        if verbose:
            print(f"[vision-cache] stored {target.name}", file=sys.stderr)
    except Exception:
        # Caching is best effort; never fail the caller because of it.
        pass
    finally:
        if tmp is not None:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
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
