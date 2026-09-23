"""Fail-closed source/match lineage for #69 public visual development.

A different clip is not necessarily a different match. Different matches in
already-inspected replays are useful DEVELOPMENT data, not blind promotion data.
This module never performs Runtime Vision promotion or changes an action grade.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import re

_SCHEMA = "public_source_lineage_v0_1"
_SHA = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SourceRecord:
    source_session: str
    source_sha256: str
    match_group: str
    capture_mode: str
    review_exposure: str
    development_only: bool
    excluded_from_formal_promotion: bool

    def __post_init__(self) -> None:
        if (not self.source_session or not self.match_group
                or not _SHA.fullmatch(self.source_sha256)):
            raise ValueError("source requires session, match group and exact SHA256")
        if self.capture_mode not in {"in_app_replay", "live_capture"}:
            raise ValueError("unknown capture mode")
        if self.review_exposure not in {"previously_inspected", "untouched"}:
            raise ValueError("review exposure must be explicit")
        if self.development_only is not True or self.excluded_from_formal_promotion is not True:
            raise ValueError("this development registry cannot certify promotion")


def load_lineage(path: str | Path) -> dict[str, SourceRecord]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if (not isinstance(doc, dict) or doc.get("schema_version") != _SCHEMA
            or not isinstance(doc.get("sources"), list)):
        raise ValueError("unsupported source lineage registry")
    results: dict[str, SourceRecord] = {}
    hashes: dict[str, str] = {}
    for entry in doc["sources"]:
        if not isinstance(entry, dict) or set(entry) != {
            "source_session", "source_sha256", "match_group", "capture_mode",
            "review_exposure", "development_only", "excluded_from_formal_promotion",
        }:
            raise ValueError("source registry entry fields do not match schema")
        row = SourceRecord(**entry)
        if row.source_session in results:
            raise ValueError("duplicate source session")
        if row.source_sha256 in hashes and hashes[row.source_sha256] != row.match_group:
            raise ValueError("same video assigned to conflicting match groups")
        hashes[row.source_sha256] = row.match_group
        results[row.source_session] = row
    if not results:
        raise ValueError("source registry must contain records")
    return results


def compare_sources(first: SourceRecord, second: SourceRecord) -> dict[str, object]:
    same_bytes = first.source_sha256 == second.source_sha256
    same_match = first.match_group == second.match_group
    return {
        "different_video_bytes": not same_bytes,
        "different_recorded_match": not same_match and not same_bytes,
        "different_match_development_example": not same_match and not same_bytes,
        "formal_promotion_eligible": False,
        "reasons": (
            ["identical_video_bytes"] if same_bytes else
            ["same_recorded_match"] if same_match else
            ["different_match_but_previously_inspected_or_replay_development_only"]
        ),
    }


def verify_local_source(path: str | Path, source: SourceRecord) -> None:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != source.source_sha256:
        raise ValueError("source SHA256 mismatch: refuse cross-source data")


def development_lineage_report(path: str | Path) -> dict[str, object]:
    rows = load_lineage(path)
    groups = sorted({row.match_group for row in rows.values()})
    return {
        "schema_version": _SCHEMA, "clips": len(rows),
        "distinct_recorded_matches": len(groups),
        "previously_inspected_clips": sum(r.review_exposure == "previously_inspected" for r in rows.values()),
        "formal_promotion_eligible_clips": 0,
        "formal_promotion_evidence": False,
        "safe_for_executor": False,
        "note": "Match grouping does not establish a blind independent Vision holdout.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True)
    args = parser.parse_args()
    print(json.dumps(development_lineage_report(args.registry), indent=2))


if __name__ == "__main__":
    main()
