"""Issue #69: bridge the existing DrawEventTracker stable count into source scope.

This adapter does not alter DrawEventTracker. It accepts ONLY a trusted
STABLE_HAND output with no draw/discard event in that sample, then wraps the
semantic concealed count with private source lineage for later claim-delta
review. DRAW_VISIBLE is intentionally rejected even though Hint may consider
it stable, because a claim-count comparison must not mix in a live draw tile.

No hand shading, OCR, action classification or Runtime/Executor behavior.
"""
from __future__ import annotations

import re

from workspace.vision.public_claim_hand_count_delta import SourceScopedStableHandCount
from workspace.vision.tiles_runtime_v0_2.draw_event_tracker import (
    DrawState, DrawTrackerOutput,
)

_SHA = re.compile(r"^[a-f0-9]{64}$")


def stable_draw_tracker_output_to_source_count(
    output: DrawTrackerOutput,
    *,
    source_session: str,
    source_sha256: str,
    stream_epoch: int,
    frame_index: int,
    actor: str,
    hand_geometry_region_verified: bool,
    source_frame_verified: bool,
    evidence_ref: str,
) -> SourceScopedStableHandCount | None:
    """Wrap only an uncontaminated semantic STABLE_HAND count."""
    if not isinstance(output, DrawTrackerOutput):
        return None
    if (
        output.state != DrawState.STABLE_HAND
        or output.trusted is not True
        or output.stable_for_hint is not True
        or output.draw_event is not None
        or output.discard_event is not None
        or output.concealed_tile_count is None
        or type(output.concealed_tile_count) is not int
        or output.concealed_tile_count < 0
    ):
        return None
    if (
        not isinstance(source_session, str) or not source_session
        or not isinstance(source_sha256, str) or not _SHA.fullmatch(source_sha256)
        or type(stream_epoch) is not int or stream_epoch < 0
        or type(frame_index) is not int or frame_index < 0
        or actor not in {"player", "opponent"}
        or hand_geometry_region_verified is not True
        or source_frame_verified is not True
        or not isinstance(evidence_ref, str) or not evidence_ref
    ):
        return None
    return SourceScopedStableHandCount(
        source_session=source_session,
        source_sha256=source_sha256,
        stream_epoch=stream_epoch,
        frame_index=frame_index,
        actor=actor,
        semantic_concealed_count=output.concealed_tile_count,
        tracker_state=output.state.value,
        tracker_trusted=True,
        tracker_stable=True,
        hand_geometry_region_verified=True,
        source_frame_verified=True,
        draw_event_in_sample=False,
        discard_event_in_sample=False,
        hand_resort_or_occlusion_in_sample=False,
        geometry_baseline_reset_in_sample=False,
        evidence_ref=evidence_ref,
    )
