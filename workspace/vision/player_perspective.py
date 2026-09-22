"""Explicit local-player perspective mapping for replay/live reconstruction.

Rules/Environment seats are symmetric and carry no screen geometry.  Vision
uses actor labels such as "player" / "opponent".  This module is the explicit
bridge between those two namespaces.

No generic "bottom UI means seat 0" rule is inferred here. Archived sessions
may lock a mapping from direct evidence; live callers may supply an explicit
configuration. Conflicts fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


SCHEMA_VERSION = "player_perspective_v0_1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
STATUSES = frozenset({"fixture_confirmed", "explicit_runtime_config"})


@dataclass(frozen=True)
class PlayerPerspectiveEvidence:
    perspective_id: str
    source_session: str | None
    source_sha256: str | None
    player_seat: int
    status: str
    evidence_ref: str
    note: str = ""

    def __post_init__(self) -> None:
        if not self.perspective_id:
            raise ValueError("perspective_id is required")
        if self.source_session is not None and not self.source_session:
            raise ValueError("source_session cannot be empty")
        if self.source_sha256 is not None:
            value = self.source_sha256.lower()
            if not _SHA256.fullmatch(value):
                raise ValueError("source_sha256 must be a SHA256 hex digest")
            object.__setattr__(self, "source_sha256", value)
        if type(self.player_seat) is not int or self.player_seat not in (0, 1):
            raise ValueError("player_seat must be seat 0 or seat 1")
        if self.status not in STATUSES:
            raise ValueError(f"unsupported perspective status: {self.status}")
        if not self.evidence_ref:
            raise ValueError("evidence_ref is required")


@dataclass(frozen=True)
class PlayerPerspectiveManifest:
    entries: tuple[PlayerPerspectiveEvidence, ...]
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        object.__setattr__(self, "entries", tuple(self.entries))
        ids = [entry.perspective_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate perspective_id")

        sessions = [
            entry.source_session
            for entry in self.entries
            if entry.source_session is not None
        ]
        if len(sessions) != len(set(sessions)):
            raise ValueError("duplicate source_session perspective mapping")

        hashes = [
            entry.source_sha256
            for entry in self.entries
            if entry.source_sha256 is not None
        ]
        if len(hashes) != len(set(hashes)):
            raise ValueError("duplicate source_sha256 perspective mapping")


@dataclass(frozen=True)
class PlayerPerspectiveResolution:
    player_seat: int | None
    source: str
    evidence_refs: tuple[str, ...]
    issues: tuple[str, ...] = ()

    @property
    def resolved(self) -> bool:
        return self.player_seat is not None and not self.issues


def _entry_from_dict(row: dict[str, Any]) -> PlayerPerspectiveEvidence:
    return PlayerPerspectiveEvidence(
        perspective_id=str(row["perspective_id"]),
        source_session=(
            str(row["source_session"])
            if row.get("source_session") is not None
            else None
        ),
        source_sha256=(
            str(row["source_sha256"])
            if row.get("source_sha256") is not None
            else None
        ),
        player_seat=row["player_seat"],
        status=str(row["status"]),
        evidence_ref=str(row["evidence_ref"]),
        note=str(row.get("note", "")),
    )


def load_player_perspective_manifest(
    path: str | Path,
) -> PlayerPerspectiveManifest:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("perspective manifest root must be an object")
    return PlayerPerspectiveManifest(
        entries=tuple(
            _entry_from_dict(row)
            for row in data.get("entries", ())
        ),
        schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
    )


def resolve_player_perspective(
    *,
    manifest: PlayerPerspectiveManifest | None = None,
    source_session: str | None = None,
    source_sha256: str | None = None,
    explicit_player_seat: int | None = None,
    explicit_evidence_ref: str = "runtime_config",
) -> PlayerPerspectiveResolution:
    """Resolve local-player seat from explicit config and/or archived evidence.

    Resolution policy:
    - explicit runtime config is allowed;
    - archived source session/hash mappings are allowed;
    - all available evidence must agree;
    - missing evidence stays unresolved;
    - screen geometry alone never supplies a seat number.
    """
    if explicit_player_seat is not None and (
        type(explicit_player_seat) is not int
        or explicit_player_seat not in (0, 1)
    ):
        raise ValueError("explicit_player_seat must be seat 0, seat 1 or None")

    if source_sha256 is not None:
        source_sha256 = source_sha256.lower()
        if not _SHA256.fullmatch(source_sha256):
            raise ValueError("source_sha256 must be a SHA256 hex digest")

    # When the caller supplies both identifiers, matching either one alone is
    # insufficient: the pair must point to the *same* archived source. This
    # also catches mixed sources whose archived player seats happen to agree.
    # Unseen live sources may still use explicit runtime configuration.
    if (
        manifest is not None
        and source_session is not None
        and source_sha256 is not None
    ):
        matched = tuple(
            entry
            for entry in manifest.entries
            if entry.source_session == source_session
            or entry.source_sha256 == source_sha256
        )
        if matched and not any(
            entry.source_session == source_session
            and entry.source_sha256 == source_sha256
            for entry in matched
        ):
            return PlayerPerspectiveResolution(
                player_seat=None,
                source="source_identity_conflict",
                evidence_refs=tuple(
                    dict.fromkeys(entry.evidence_ref for entry in matched)
                ),
                issues=("player_source_identity_conflict",),
            )

    candidates: list[tuple[int, str, str]] = []
    if explicit_player_seat is not None:
        candidates.append((
            explicit_player_seat,
            "explicit_runtime_config",
            explicit_evidence_ref,
        ))

    if manifest is not None:
        for entry in manifest.entries:
            matches_session = (
                source_session is not None
                and entry.source_session == source_session
            )
            matches_hash = (
                source_sha256 is not None
                and entry.source_sha256 == source_sha256
            )
            if matches_session or matches_hash:
                candidates.append((
                    entry.player_seat,
                    entry.status,
                    entry.evidence_ref,
                ))

    if not candidates:
        return PlayerPerspectiveResolution(
            player_seat=None,
            source="unresolved",
            evidence_refs=(),
            issues=("player_seat_unresolved",),
        )

    seats = {seat for seat, _, _ in candidates}
    refs = tuple(dict.fromkeys(ref for _, _, ref in candidates))
    sources = tuple(dict.fromkeys(source for _, source, _ in candidates))
    if len(seats) != 1:
        return PlayerPerspectiveResolution(
            player_seat=None,
            source="+".join(sources),
            evidence_refs=refs,
            issues=("player_seat_evidence_conflict",),
        )

    return PlayerPerspectiveResolution(
        player_seat=next(iter(seats)),
        source="+".join(sources),
        evidence_refs=refs,
    )
