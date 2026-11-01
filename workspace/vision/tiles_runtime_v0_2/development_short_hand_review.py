"""Offline count-only review; never changes GeometryFrame or opens advice."""
from dataclasses import dataclass
from math import isfinite
from statistics import median

from workspace.vision.public_observers import MeldSnapshotObserver


@dataclass(frozen=True)
class ShortHandCountReview:
    allowed: bool
    issues: tuple[str, ...]
    hand_count: int = 0
    draw_count: int = 0
    meld_group_count: int = 0
    advice_allowed: bool = False
    safe_for_runtime: bool = False
    safe_for_executor: bool = False


def _valid_hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _inside(box, container):
    cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
    return container[0] <= cx <= container[0] + container[2] and container[1] <= cy <= container[1] + container[3]


def review_short_hand_counts(geometry_frames, meld_snapshots, *,
                             source_sha256, expected_source_sha256,
                             reviewed_rgb_hashes, own_actor="player"):
    """Validate reviewed five-frame count evidence, separate from identity trust.

    Caller must have verified source bytes and RGB hashes against actual decoding.
    Hash declarations alone are not independently verified by this pure helper.
    """
    issues = []
    geometries, melds = tuple(geometry_frames), tuple(meld_snapshots)
    if not _valid_hash(source_sha256) or source_sha256 != expected_source_sha256:
        issues.append("source_sha_mismatch_or_invalid")
    if len(geometries) != 5 or len(melds) != 5:
        issues.append("five_current_frames_required")
    if issues:
        return ShortHandCountReview(False, tuple(issues))
    session = geometries[0].session
    epoch = melds[0].stream_epoch
    if not session:
        issues.append("source_session_missing")
    observer = MeldSnapshotObserver(settle_frames=5)
    signatures = []
    positions = []
    previous_frame = None
    last = None
    for geometry, snapshot in zip(geometries, melds):
        frame = geometry.frame
        if isinstance(frame, bool) or not isinstance(frame, int) or (previous_frame is not None and frame != previous_frame + 1):
            issues.append("decoded_ordinals_not_consecutive")
        if isinstance(frame, int):
            previous_frame = frame
        if not _valid_hash(reviewed_rgb_hashes.get(frame)):
            issues.append("reviewed_rgb_binding_missing")
        if geometry.session != session or snapshot.source_session != session or snapshot.stream_epoch != epoch or snapshot.frame != frame:
            issues.append("source_epoch_frame_mismatch")
        if snapshot.actor != own_actor or snapshot.trusted is not True:
            issues.append("own_meld_snapshot_untrusted")
        if f"source_sha:{source_sha256}" not in snapshot.evidence_refs:
            issues.append("meld_source_reference_missing")
        if any(issue not in {"component_count_outside_reviewed_range", "meld_candidates_detected"} for issue in geometry.issues):
            issues.append("other_geometry_failure")
        if geometry.geometry_untrusted and "component_count_outside_reviewed_range" not in geometry.issues:
            issues.append("unexplained_geometry_untrusted")
        components = geometry.components
        if any(c.session != session or c.frame != frame for c in components):
            issues.append("component_source_frame_mismatch")
        if any(c.region_candidate == "unknown" for c in components):
            issues.append("unexplained_geometry_fragment")
        if any(not all(isfinite(float(v)) for v in c.normalized_bbox) for c in components):
            issues.append("nonfinite_geometry")
        hand = sorted((c for c in components if c.region_candidate == "hand"), key=lambda c: c.pixel_bbox[0])
        draw = [c for c in components if c.region_candidate == "draw_visual"]
        exposed = [c for c in components if c.region_candidate == "meld"]
        groups = snapshot.groups
        if not 1 <= len(groups) <= 5 or any(len(g.tiles) not in {3, 4} for g in groups):
            issues.append("meld_group_shape_invalid")
        if len(exposed) != sum(len(g.tiles) for g in groups):
            issues.append("meld_face_count_disagrees")
        if any(sum(_inside(c.normalized_bbox, g.normalized_bbox) for g in groups) != 1 for c in exposed):
            issues.append("meld_face_group_assignment_ambiguous")
        if any(_inside(c.normalized_bbox, g.normalized_bbox) for c in (*hand, *draw) for g in groups):
            issues.append("hand_overlaps_meld_group")
        target = (5 - len(groups)) * 3 + 2
        if len(draw) > 1 or len(hand) != target - 1 or not 1 <= len(hand) < 8:
            issues.append("short_hand_count_disagrees")
        signatures.append((len(hand), len(draw), len(groups)))
        positions.append(tuple(c.normalized_bbox for c in (*hand, *draw)))
        last = observer.observe(snapshot)
    if len(set(signatures)) != 1:
        issues.append("current_counts_changed")
    if last is None or not last.stable or not last.trusted:
        issues.append("meld_structure_not_stable")
    if positions and all(len(p) == len(positions[0]) for p in positions):
        for current in positions[1:]:
            for a, b in zip(positions[0], current):
                if abs(a[0] - b[0]) > median((a[2], b[2])) * .1 or abs(a[1] - b[1]) > median((a[3], b[3])) * .1:
                    issues.append("current_hand_geometry_not_stable")
    unique = tuple(dict.fromkeys(issues))
    if unique:
        return ShortHandCountReview(False, unique)
    h, d, m = signatures[-1]
    return ShortHandCountReview(True, ("development_count_only_identities_not_authorized",), h, d, m)
