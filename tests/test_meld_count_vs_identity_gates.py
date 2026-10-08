"""Own exposed-meld GROUP COUNT is scored separately from tile identity.

Contract locked here, without changing the 0.82 threshold, V0.10, or Executor:

- FLAT, STACKED, and a FLAT3-to-STACKED4 upgrade keep a trusted group count
  while every face stays UNKNOWN. The upgrade never becomes ADD_KONG.
- An accepted count of UNKNOWN-identity groups still allows structural shanten
  when the concealed hand, opened Gold, and stability gates are complete.
  Visible remainders and danger stay closed.
- An unexplained detector fragment (a cluster that is not 3 or 4 faces, and
  is not corroborated by the concealed-hand count) makes the player meld count
  untrusted and blocks shanten. Identity is not guessed to paper over it.
- STACKED geometry is rejected by the identity bridge. It is retained only as
  four UNKNOWN faces and cannot trust the identity snapshot.

These are contract tests on the existing snapshot, runtime adapter, structure
bridge, and identity bridge. They are not real-video accuracy.
"""
from __future__ import annotations

import importlib.util
import unittest
from dataclasses import replace
from unittest.mock import patch

from workspace.hint_alpha import analyze_snapshot_shanten
from workspace.vision.current_state_snapshot import (
    CurrentTableSnapshot,
    SnapshotCapability,
    SnapshotStatus,
    advisory_analysis_inputs,
    assess_current_snapshot,
)
from workspace.vision.runtime_public_adapter import (
    current_snapshot_from_runtime,
    player_meld_snapshot_from_runtime,
)


HAND16 = (
    "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8",
    "M9", "P1", "P2", "P3", "S1", "S2", "S3", "E",
)
# 13 concealed tiles imply one open meld on a 16-tile pre-draw hand.
HAND13 = HAND16[:13]
GOLD = "B"


def _component(
    x,
    region,
    *,
    tile_id="UNKNOWN",
    frame=102,
    y=0.80,
    width=0.04,
    height=0.10,
    identity_reason=None,
):
    if identity_reason is None:
        identity_reason = (
            "accepted" if tile_id not in (None, "UNKNOWN") else "below_confidence_threshold"
        )
    return {
        "normalized_bbox": [x, y, width, height],
        "region_candidate": region,
        "confidence": 0.95,
        "frame": frame,
        "tile_id": tile_id,
        "tile_confidence": 0.95,
        "identity_reason": identity_reason,
        "public_identity_result": None,
    }


def _runtime_report(hand, meld_components, *, concealed_count=None, session="meld-count-gate"):
    concealed = [
        _component(0.40 + index * 0.02, "hand", tile_id=tile)
        for index, tile in enumerate(hand)
    ]
    gold = [_component(0.95, "gold", tile_id=GOLD)]
    return {
        "schema_version": "vision_runtime_v0_2_smoke",
        "session": session,
        "stream_epoch": 0,
        "frames": [100, 101, 102],
        "components": [*concealed, *meld_components, *gold],
        "gold_identity_observations": [
            {
                "frame": frame,
                "candidate_tile_id": GOLD,
                "tile_id": GOLD,
                "tile_confidence": 0.95,
                "identity_reason": "accepted",
            }
            for frame in (100, 101, 102)
        ],
        "concealed_tile_count": len(hand) if concealed_count is None else concealed_count,
        "all_concealed_tile_ids_trusted": True,
        "geometry_untrusted": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def _flat_cluster(origin_x):
    return [
        _component(origin_x, "meld"),
        _component(origin_x + 0.04, "meld"),
        _component(origin_x + 0.08, "meld"),
    ]


def _stacked_cluster(origin_x):
    return [
        _component(origin_x, "meld", y=0.78),
        _component(origin_x + 0.04, "meld", y=0.78),
        _component(origin_x + 0.04, "meld", y=0.82),
        _component(origin_x + 0.08, "meld", y=0.82),
    ]


class MeldCountVersusIdentityGateTests(unittest.TestCase):
    """Accepted UNKNOWN count still yields structural shanten; fragments do not."""

    def _assess(self, hand, meld_components, **report_changes):
        source = _runtime_report(hand, meld_components, **report_changes)
        snapshot = current_snapshot_from_runtime(source, timestamp_seconds=2.0)
        return snapshot, assess_current_snapshot(snapshot)

    def test_flat_unknown_count_allows_structural_shanten_only(self):
        snapshot, result = self._assess(HAND13, _flat_cluster(0.05))

        self.assertEqual(len(snapshot.melds[0]), 1)
        self.assertEqual(snapshot.melds[0][0], (None, None, None))
        self.assertTrue(snapshot.meld_trusted[0])
        self.assertEqual(result.status, SnapshotStatus.PARTIAL)
        self.assertTrue(result.allows(SnapshotCapability.SHANTEN))
        self.assertFalse(result.allows(SnapshotCapability.VISIBLE_REMAINDERS))
        self.assertFalse(result.allows(SnapshotCapability.DANGER_HINT))
        self.assertIn("meld_identity_unknown:0", result.issues)
        self.assertNotIn("player_meld_count_untrusted", result.issues)

        inputs = advisory_analysis_inputs(snapshot, result)
        self.assertEqual(inputs.open_meld_count, 1)
        self.assertIsNone(inputs.visible_tiles)
        self.assertFalse(inputs.safe_for_executor)

        hint = analyze_snapshot_shanten(snapshot)
        self.assertTrue(hint.allowed)
        self.assertEqual(hint.status, "PARTIAL")
        self.assertEqual(hint.phase, "PRE_DRAW")
        self.assertIsNotNone(hint.shanten)
        self.assertFalse(hint.visible_remainders_used)
        self.assertFalse(hint.safe_for_executor)

    def test_stacked_unknown_four_face_count_is_one_group(self):
        # 10 concealed tiles: two open melds, pre-draw. One FLAT plus one STACKED.
        hand = HAND16[:10]
        snapshot, result = self._assess(
            hand,
            [*_flat_cluster(0.05), *_stacked_cluster(0.30)],
        )
        self.assertEqual(len(snapshot.melds[0]), 2)
        self.assertEqual(snapshot.melds[0][1], (None, None, None, None))
        self.assertTrue(snapshot.meld_trusted[0])
        self.assertTrue(result.allows(SnapshotCapability.SHANTEN))
        self.assertFalse(result.allows(SnapshotCapability.DANGER_HINT))
        self.assertEqual(
            advisory_analysis_inputs(snapshot, result).open_meld_count,
            2,
        )
        self.assertIn("meld_identity_unknown:0", result.issues)

    def test_add_kong_shaped_upgrade_keeps_count_and_rejects_action_kind(self):
        """A 3-face group becoming 4 faces is still UNKNOWN, never ADD_KONG.

        The structure matrix already refuses to promote that transition. This
        gate checks the same refusal still leaves a usable group count when
        the runtime detector reports the resulting four-face cluster and the
        concealed count agrees (7 tiles = three open melds, pre-draw).
        """
        hand = HAND16[:7]
        clusters = [
            *_flat_cluster(0.05),
            *_flat_cluster(0.22),
            *_stacked_cluster(0.42),
        ]
        snapshot, result = self._assess(hand, clusters)
        self.assertEqual(
            [len(group) for group in snapshot.melds[0]],
            [3, 3, 4],
        )
        self.assertTrue(all(tile is None for group in snapshot.melds[0] for tile in group))
        self.assertTrue(result.allows(SnapshotCapability.SHANTEN))
        self.assertEqual(
            advisory_analysis_inputs(snapshot, result).open_meld_count,
            3,
        )

        self.assertFalse(any("ADD_KONG" in issue for issue in result.issues))
        # Action-kind refusal for FLAT3 -> STACKED4 stays in
        # test_issue69_meld_structure_regression_matrix. This gate only locks
        # that the resulting four-face cluster still counts as one UNKNOWN group.

    def test_unexplained_fragment_makes_count_untrusted_and_blocks_shanten(self):
        # One legal 3-face group plus a leftover single face. Concealed count
        # of 13 expects exactly one meld, so the fragment is not a corroborated
        # incomplete cluster and must not be absorbed into the count.
        snapshot, result = self._assess(
            HAND13,
            [*_flat_cluster(0.05), _component(0.40, "meld")],
        )
        meld = player_meld_snapshot_from_runtime(
            _runtime_report(HAND13, [*_flat_cluster(0.05), _component(0.40, "meld")]),
            timestamp_seconds=2.0,
        )
        self.assertFalse(meld.trusted)
        self.assertEqual(len(meld.groups), 1)
        self.assertEqual(meld.groups[0].tiles, (None, None, None))
        self.assertFalse(snapshot.meld_trusted[0])
        self.assertEqual(result.status, SnapshotStatus.BLOCKED)
        self.assertFalse(result.allows(SnapshotCapability.SHANTEN))
        self.assertIn("player_meld_count_untrusted", result.issues)
        self.assertIn("meld_identity_unknown:0", result.issues)
        self.assertFalse(analyze_snapshot_shanten(snapshot).allowed)

    def test_two_face_fragment_without_hand_agreement_is_not_a_group(self):
        meld = player_meld_snapshot_from_runtime(
            _runtime_report(
                HAND16,
                [_component(0.05, "meld"), _component(0.09, "meld")],
                concealed_count=16,
            ),
            timestamp_seconds=2.0,
        )
        self.assertEqual(meld.groups, ())
        self.assertFalse(meld.trusted)

    def test_direct_tile_ids_on_flat_components_stay_unknown(self):
        labeled = [
            _component(0.05, "meld", tile_id="P3"),
            _component(0.09, "meld", tile_id="P4"),
            _component(0.13, "meld", tile_id="P5"),
        ]
        snapshot, result = self._assess(HAND13, labeled)
        self.assertEqual(snapshot.melds[0][0], (None, None, None))
        self.assertTrue(result.allows(SnapshotCapability.SHANTEN))
        self.assertFalse(result.allows(SnapshotCapability.VISIBLE_REMAINDERS))


class SnapshotUnknownIdentityCountTests(unittest.TestCase):
    """Same contract on CurrentTableSnapshot, including a four-face UNKNOWN slot."""

    def snapshot(self, **changes):
        base = CurrentTableSnapshot(
            timestamp_seconds=12.5,
            source_session="hand-count-gate",
            stream_epoch=0,
            stable_frames=3,
            own_hand=HAND13,
            gold_tile=GOLD,
            rivers=((), ()),
            melds=(((None, None, None),), ()),
            hand_trusted=True,
            gold_trusted=True,
            river_trusted=(False, False),
            meld_trusted=(True, False),
        )
        return replace(base, **changes)

    def test_unknown_three_and_four_face_counts_both_allow_shanten(self):
        for groups in (
            (((None, None, None),), ()),
            (((None, None, None), (None, None, None, None)), ()),
        ):
            concealed = HAND16[: 16 - 3 * len(groups[0])]
            snapshot = self.snapshot(own_hand=concealed, melds=groups)
            result = assess_current_snapshot(snapshot)
            with self.subTest(faces=[len(group) for group in groups[0]]):
                self.assertTrue(result.allows(SnapshotCapability.SHANTEN))
                self.assertFalse(result.allows(SnapshotCapability.DANGER_HINT))
                self.assertEqual(
                    advisory_analysis_inputs(snapshot, result).open_meld_count,
                    len(groups[0]),
                )
                self.assertTrue(
                    all(tile is None for group in snapshot.melds[0] for tile in group)
                )

    def test_fragment_shape_blocks_even_when_count_flag_is_trusted(self):
        snapshot = self.snapshot(melds=((("P6", "P6"),), ()))
        result = assess_current_snapshot(snapshot)
        self.assertEqual(result.status, SnapshotStatus.BLOCKED)
        self.assertIn("meld_shape_invalid:0:0", result.issues)
        self.assertFalse(result.allows(SnapshotCapability.SHANTEN))

    def test_untrusted_count_blocks_shanten_despite_unknown_identity_shape(self):
        snapshot = self.snapshot(meld_trusted=(False, False))
        result = assess_current_snapshot(snapshot)
        self.assertIn("player_meld_count_untrusted", result.issues)
        self.assertFalse(result.allows(SnapshotCapability.SHANTEN))
        self.assertFalse(result.safe_for_executor)


VISION = all(
    importlib.util.find_spec(name) is not None
    for name in ("PIL", "cv2", "numpy")
)


@unittest.skipUnless(VISION, "Pillow/OpenCV/numpy are optional in core-only installs")
class StackedIdentityRejectedTests(unittest.TestCase):
    """STACKED identity is rejected; the group is kept only as UNKNOWN faces."""

    @classmethod
    def setUpClass(cls):
        from PIL import Image, ImageDraw
        from workspace.vision.public_identity_shadow_v0_2 import ShadowBank, SourceGroup
        from workspace.vision.public_meld_identity_bridge import (
            classify_public_meld_group,
            meld_snapshot_from_identity_bridges,
        )
        from workspace.vision.public_tile_detector import PublicGeometryCandidate

        cls.Image = Image
        cls.ImageDraw = ImageDraw
        cls.classify = staticmethod(classify_public_meld_group)
        cls.snapshot_from_bridges = staticmethod(meld_snapshot_from_identity_bridges)
        cls.ShadowBank = ShadowBank
        cls.SourceGroup = SourceGroup
        cls.Candidate = PublicGeometryCandidate

    def _stacked_image(self):
        image = self.Image.new("RGB", (240, 170), (0, 75, 78))
        draw = self.ImageDraw.Draw(image)
        for x in (25, 85, 145):
            draw.rectangle((x, 70, x + 54, 155), fill=(235, 235, 225))
        draw.rectangle((85, 15, 139, 100), fill=(235, 235, 225))
        return image

    def _group(self):
        return self.Candidate(
            pixel_bbox=(20, 10, 185, 150),
            normalized_bbox=(0.1, 0.2, 0.3, 0.2),
            geometry_kind="bottom_group",
            confidence=0.90,
            fill_ratio=0.80,
            frame=10,
            session="query",
        )

    def test_stacked_identity_rejected_but_four_unknown_faces_kept(self):
        bank = self.ShadowBank(
            sources={
                "query": self.SourceGroup(
                    session="query",
                    source_sha256="c" * 64,
                    match_group="query-match",
                )
            },
            templates=(),
        )
        with patch(
            "workspace.vision.public_meld_identity_bridge.propose_shadow_identity",
        ) as proposer:
            result = self.classify(
                self._stacked_image(),
                self._group(),
                bank=bank,
                source_session="query",
                source_sha256="c" * 64,
            )
        proposer.assert_not_called()
        self.assertFalse(result.trusted_for_read_only_runtime)
        self.assertEqual(result.tile_ids, ())
        self.assertEqual(result.prepared.geometry.stack_state, "STACKED")
        self.assertIn("stacked_meld_identity_split_not_implemented", result.issues)

        snapshot = self.snapshot_from_bridges(
            ((self._group(), result),),
            actor="player",
            timestamp_seconds=1.0,
            frame=10,
            source_session="query",
        )
        self.assertFalse(snapshot.trusted)
        self.assertEqual(len(snapshot.groups), 1)
        self.assertEqual(snapshot.groups[0].tiles, (None, None, None, None))
        self.assertFalse(snapshot.groups[0].identities_complete)


if __name__ == "__main__":
    unittest.main()
