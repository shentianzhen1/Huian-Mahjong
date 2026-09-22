from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image

from workspace.vision.public_candidate_tracker import (
    CandidateChannel,
    PublicCandidateTracker,
    TrackEventKind,
    river_snapshot_from_channel,
)
from workspace.vision.public_detector_calibration import load_manifest
from workspace.vision.public_tile_detector import (
    PublicGeometryCandidate,
    PublicGeometryFrame,
    detect_public_tile_geometry,
    target_coverage,
)


ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = (
    ROOT
    / "references"
    / "vision"
    / "2026-09-22"
    / "public_detector_calibration_v0_1.json"
)


def candidate(
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    kind: str = "single_face",
    confidence: float = 0.8,
    frame: int = 1,
    session: str = "s1",
) -> PublicGeometryCandidate:
    return PublicGeometryCandidate(
        pixel_bbox=(
            int(round(x * 1000)),
            int(round(y * 500)),
            max(1, int(round(width * 1000))),
            max(1, int(round(height * 500))),
        ),
        normalized_bbox=(x, y, width, height),
        geometry_kind=kind,
        confidence=confidence,
        fill_ratio=0.5,
        frame=frame,
        session=session,
    )


def geometry_frame(
    frame: int,
    candidates: tuple[PublicGeometryCandidate, ...],
    *,
    session: str = "s1",
) -> PublicGeometryFrame:
    return PublicGeometryFrame(
        candidates=candidates,
        issues=("candidate_intake_only",),
        frame=frame,
        session=session,
    )


class PublicCandidateTrackerTests(unittest.TestCase):
    def test_requires_three_consecutive_frames_before_appeared(self):
        tracker = PublicCandidateTracker(settle_frames=3, disappear_frames=2)
        outputs = []
        for index, x in enumerate((0.30, 0.301, 0.299), start=1):
            outputs.append(
                tracker.observe(
                    geometry_frame(
                        index,
                        (
                            candidate(
                                x,
                                0.20,
                                0.05,
                                0.12,
                                frame=index,
                            ),
                        ),
                    ),
                    timestamp_seconds=index * 0.1,
                )
            )

        self.assertEqual(outputs[0].stable_tracks, ())
        self.assertEqual(outputs[1].stable_tracks, ())
        self.assertEqual(len(outputs[2].stable_tracks), 1)
        self.assertEqual(len(outputs[2].events), 1)
        self.assertEqual(outputs[2].events[0].kind, TrackEventKind.APPEARED)
        self.assertEqual(
            outputs[2].stable_tracks[0].evidence_refs,
            (
                "public:s1:frame:1",
                "public:s1:frame:2",
                "public:s1:frame:3",
            ),
        )

    def test_one_frame_transient_never_becomes_stable(self):
        tracker = PublicCandidateTracker(settle_frames=3, disappear_frames=2)
        first = tracker.observe(
            geometry_frame(
                1,
                (candidate(0.30, 0.20, 0.05, 0.12),),
            ),
            timestamp_seconds=0.1,
        )
        second = tracker.observe(
            geometry_frame(2, ()),
            timestamp_seconds=0.2,
        )
        third = tracker.observe(
            geometry_frame(3, ()),
            timestamp_seconds=0.3,
        )
        self.assertEqual(first.stable_tracks, ())
        self.assertEqual(second.events, ())
        self.assertEqual(third.events, ())
        self.assertEqual(third.stable_tracks, ())

    def test_confirmed_track_needs_two_misses_before_disappeared(self):
        tracker = PublicCandidateTracker(settle_frames=2, disappear_frames=2)
        appeared = None
        for frame in (1, 2):
            appeared = tracker.observe(
                geometry_frame(
                    frame,
                    (
                        candidate(
                            0.30,
                            0.20,
                            0.05,
                            0.12,
                            frame=frame,
                        ),
                    ),
                ),
                timestamp_seconds=frame * 0.1,
            )
        assert appeared is not None
        self.assertEqual(appeared.events[0].kind, TrackEventKind.APPEARED)

        first_miss = tracker.observe(
            geometry_frame(3, ()),
            timestamp_seconds=0.3,
        )
        self.assertEqual(len(first_miss.stable_tracks), 1)
        self.assertEqual(first_miss.events, ())

        second_miss = tracker.observe(
            geometry_frame(4, ()),
            timestamp_seconds=0.4,
        )
        self.assertEqual(second_miss.stable_tracks, ())
        self.assertEqual(len(second_miss.events), 1)
        self.assertEqual(
            second_miss.events[0].kind,
            TrackEventKind.DISAPPEARED,
        )

    def test_geometry_kind_change_does_not_continue_old_track(self):
        tracker = PublicCandidateTracker(settle_frames=2, disappear_frames=1)
        for frame in (1, 2):
            output = tracker.observe(
                geometry_frame(
                    frame,
                    (
                        candidate(
                            0.30,
                            0.20,
                            0.05,
                            0.12,
                            kind="single_face",
                            frame=frame,
                        ),
                    ),
                ),
                timestamp_seconds=frame * 0.1,
            )
        old_id = output.stable_tracks[0].track_id

        changed = tracker.observe(
            geometry_frame(
                3,
                (
                    candidate(
                        0.30,
                        0.20,
                        0.05,
                        0.12,
                        kind="upper_protrusion",
                        frame=3,
                    ),
                ),
            ),
            timestamp_seconds=0.3,
        )
        self.assertEqual(changed.stable_tracks, ())
        self.assertEqual(
            [event.kind for event in changed.events],
            [TrackEventKind.DISAPPEARED],
        )
        self.assertEqual(changed.events[0].track.track_id, old_id)

        confirmed_new = tracker.observe(
            geometry_frame(
                4,
                (
                    candidate(
                        0.301,
                        0.201,
                        0.05,
                        0.12,
                        kind="upper_protrusion",
                        frame=4,
                    ),
                ),
            ),
            timestamp_seconds=0.4,
        )
        self.assertEqual(len(confirmed_new.stable_tracks), 1)
        self.assertNotEqual(
            confirmed_new.stable_tracks[0].track_id,
            old_id,
        )

    def test_session_change_resets_without_false_disappearance(self):
        tracker = PublicCandidateTracker(settle_frames=2, disappear_frames=1)
        for frame in (1, 2):
            tracker.observe(
                geometry_frame(
                    frame,
                    (
                        candidate(
                            0.30,
                            0.20,
                            0.05,
                            0.12,
                            frame=frame,
                        ),
                    ),
                    session="s1",
                ),
                timestamp_seconds=frame * 0.1,
            )

        changed = tracker.observe(
            geometry_frame(3, (), session="s2"),
            timestamp_seconds=0.3,
        )
        self.assertIn("session_changed_reset", changed.issues)
        self.assertEqual(changed.events, ())
        self.assertEqual(changed.stable_tracks, ())

    def test_timestamp_must_not_go_backwards(self):
        tracker = PublicCandidateTracker(settle_frames=2)
        tracker.observe(
            geometry_frame(1, ()),
            timestamp_seconds=1.0,
        )
        with self.assertRaises(ValueError):
            tracker.observe(
                geometry_frame(2, ()),
                timestamp_seconds=0.9,
            )

    def test_explicit_channel_is_required_to_build_river_snapshot(self):
        tracker = PublicCandidateTracker(settle_frames=2)
        for frame in (1, 2):
            output = tracker.observe(
                geometry_frame(
                    frame,
                    (
                        candidate(
                            0.25,
                            0.05,
                            0.025,
                            0.07,
                            kind="single_face",
                            frame=frame,
                        ),
                        candidate(
                            0.10,
                            0.84,
                            0.13,
                            0.15,
                            kind="bottom_group",
                            frame=frame,
                        ),
                    ),
                ),
                timestamp_seconds=frame * 0.1,
            )

        channel = CandidateChannel(
            name="reviewed_upper_single_public_channel",
            geometry_kinds=("single_face",),
            zones=((0.15, 0.0, 0.25, 0.20),),
            minimum_zone_coverage=0.5,
        )
        snapshot = river_snapshot_from_channel(
            output,
            channel=channel,
            actor="opponent",
            timestamp_seconds=0.2,
        )
        self.assertEqual(snapshot.actor, "opponent")
        self.assertEqual(len(snapshot.tiles), 1)
        self.assertIsNone(snapshot.tiles[0].tile_id)
        self.assertEqual(snapshot.tiles[0].normalized_bbox[0], 0.25)


class PublicCandidateTrackerRealFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_manifest(MANIFEST_PATH)

    def _sample(self, sample_id: str):
        return next(
            sample
            for sample in self.manifest.samples
            if sample.sample_id == sample_id
        )

    def _track_same_real_frame(self, sample_id: str):
        sample = self._sample(sample_id)
        assert sample.bbox is not None
        image = Image.open(ROOT / sample.image_path).convert("RGB")
        tracker = PublicCandidateTracker(settle_frames=3)
        output = None
        for offset in range(3):
            detection = detect_public_tile_geometry(
                image,
                frame=sample.frame_index + offset,
                session=sample.source_session,
            )
            output = tracker.observe(
                detection,
                timestamp_seconds=(sample.time_ms / 1000) + offset * 0.04,
            )
        assert output is not None
        scores = [
            (
                target_coverage(track.normalized_bbox, sample.bbox),
                track,
            )
            for track in output.stable_tracks
        ]
        return sample, output, max(scores, default=(0.0, None), key=lambda x: x[0])

    def test_real_opponent_p1_candidate_survives_stability_gate(self):
        sample, output, best = self._track_same_real_frame(
            "66fe_opponent_discard_p1_035s"
        )
        score, track = best
        self.assertIsNotNone(track)
        self.assertGreaterEqual(score, 0.75)
        assert track is not None
        self.assertEqual(track.geometry_kind, "upper_protrusion")
        self.assertTrue(
            any(
                event.kind == TrackEventKind.APPEARED
                and event.track.track_id == track.track_id
                for event in output.events
            )
        )

    def test_real_player_p1_peng_candidate_survives_stability_gate(self):
        sample, output, best = self._track_same_real_frame(
            "66fe_player_peng_p1_040s"
        )
        score, track = best
        self.assertIsNotNone(track)
        self.assertGreaterEqual(score, 0.90)
        assert track is not None
        self.assertEqual(track.geometry_kind, "bottom_group")


if __name__ == "__main__":
    unittest.main()
