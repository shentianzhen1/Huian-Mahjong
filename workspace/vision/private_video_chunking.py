"""Local-only chunk planner for large private gameplay recordings.

This module exists to make large source recordings analysis-friendly without
uploading raw footage to the repository. It plans bounded time windows and can
build conservative ffmpeg stream-copy commands. Every derived clip remains part
of the SAME original source/match group; chunking never creates independent
validation evidence.

The derived clip is only a transport convenience. Use verified_frame_lineage
before frame-level evidence is promoted.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import shlex
from typing import Iterable


DEFAULT_CHUNK_SECONDS = 45.0
DEFAULT_MAX_CHUNK_BYTES = 95 * 1024 * 1024


@dataclass(frozen=True)
class PrivateVideoChunkPlan:
    index: int
    start_seconds: float
    end_seconds: float
    duration_seconds: float

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "start_seconds": round(self.start_seconds, 6),
            "end_seconds": round(self.end_seconds, 6),
            "duration_seconds": round(self.duration_seconds, 6),
            "same_original_source": True,
            "independent_match_group": False,
            "formal_promotion_evidence": False,
            "safe_for_executor": False,
        }


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def plan_private_video_chunks(
    duration_seconds: float,
    *,
    chunk_seconds: float = DEFAULT_CHUNK_SECONDS,
) -> tuple[PrivateVideoChunkPlan, ...]:
    if isinstance(duration_seconds, bool) or not isinstance(
        duration_seconds, (int, float)
    ):
        raise ValueError("duration_seconds must be numeric")
    if isinstance(chunk_seconds, bool) or not isinstance(
        chunk_seconds, (int, float)
    ):
        raise ValueError("chunk_seconds must be numeric")

    duration_seconds = float(duration_seconds)
    chunk_seconds = float(chunk_seconds)
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("duration_seconds must be finite and positive")
    if not math.isfinite(chunk_seconds) or chunk_seconds <= 0:
        raise ValueError("chunk_seconds must be finite and positive")

    plans = []
    start = 0.0
    index = 1
    while start < duration_seconds:
        end = min(duration_seconds, start + chunk_seconds)
        plans.append(
            PrivateVideoChunkPlan(
                index=index,
                start_seconds=start,
                end_seconds=end,
                duration_seconds=end - start,
            )
        )
        start = end
        index += 1
    return tuple(plans)


def build_ffmpeg_stream_copy_command(
    source: str | Path,
    output: str | Path,
    plan: PrivateVideoChunkPlan,
) -> tuple[str, ...]:
    """Return a no-reencode chunk command.

    Stream copy preserves compressed video payloads where the container permits,
    but seeking can begin on a nearby keyframe. Therefore callers MUST run the
    existing verified_frame_lineage check before treating frame indexes from the
    derivative clip as source-qualified evidence.
    """
    if not isinstance(plan, PrivateVideoChunkPlan):
        raise TypeError("plan must be PrivateVideoChunkPlan")
    return (
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{plan.start_seconds:.6f}",
        "-i",
        str(source),
        "-t",
        f"{plan.duration_seconds:.6f}",
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c",
        "copy",
        "-avoid_negative_ts",
        "make_zero",
        str(output),
    )


def command_as_shell_text(command: Iterable[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in command)


def chunk_record(
    *,
    source_name: str,
    source_sha256: str,
    match_group: str,
    plan: PrivateVideoChunkPlan,
    output_name: str,
    output_sha256: str | None = None,
    output_size_bytes: int | None = None,
    maximum_chunk_bytes: int = DEFAULT_MAX_CHUNK_BYTES,
) -> dict:
    if not source_name:
        raise ValueError("source_name is required")
    if len(source_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_sha256):
        raise ValueError("source_sha256 must be lowercase SHA256")
    if not match_group:
        raise ValueError("match_group is required")
    if not output_name:
        raise ValueError("output_name is required")
    if isinstance(maximum_chunk_bytes, bool) or not isinstance(maximum_chunk_bytes, int):
        raise ValueError("maximum_chunk_bytes must be integer")
    if maximum_chunk_bytes <= 0:
        raise ValueError("maximum_chunk_bytes must be positive")
    if output_sha256 is not None and (
        len(output_sha256) != 64
        or any(c not in "0123456789abcdef" for c in output_sha256)
    ):
        raise ValueError("output_sha256 must be lowercase SHA256")
    if output_size_bytes is not None and (
        isinstance(output_size_bytes, bool)
        or not isinstance(output_size_bytes, int)
        or output_size_bytes < 0
    ):
        raise ValueError("output_size_bytes must be nonnegative integer")

    size_gate = (
        None
        if output_size_bytes is None
        else output_size_bytes <= maximum_chunk_bytes
    )
    return {
        "schema_version": "private_video_chunk_record_v0_1",
        "source_name": source_name,
        "source_sha256": source_sha256,
        "match_group": match_group,
        "chunk": plan.to_dict(),
        "output_name": output_name,
        "output_sha256": output_sha256,
        "output_size_bytes": output_size_bytes,
        "maximum_chunk_bytes": maximum_chunk_bytes,
        "within_transport_size_gate": size_gate,
        "same_original_source": True,
        "independent_match_group": False,
        "requires_frame_lineage_verification": True,
        "raw_or_derived_media_must_stay_private": True,
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }
