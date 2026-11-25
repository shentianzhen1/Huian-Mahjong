from dataclasses import replace
import unittest

try:
    from workspace.vision.tiles_runtime_v0_2.development_short_hand_review import review_short_hand_counts
    from workspace.vision.tiles_runtime_v0_2.dynamic_geometry import GeometryComponent, GeometryFrame
    from workspace.vision.public_observers import MeldGroup, MeldSnapshot
except ImportError:
    review_short_hand_counts = None


@unittest.skipIf(review_short_hand_counts is None, "Vision dependencies required")
class DevelopmentShortHandReviewTests(unittest.TestCase):
    def fixture(self):
        sha = "a" * 64
        gs, ms = [], []
        for frame in range(5):
            def component(box, region):
                return GeometryComponent(tuple(round(v * 1000) for v in box), box,
                                         region, .6, frame, "capture")
            groups = tuple(MeldGroup((.02 + j * .16, .84, .15, .13),
                                     (None, None, None), .8) for j in range(3))
            faces = [component((.025 + j * .16 + k * .047, .86, .043, .1), "meld")
                     for j in range(3) for k in range(3)]
            hand = [component((.52 + k * .05, .85, .045, .12), "hand") for k in range(7)]
            draw = component((.93, .85, .045, .12), "draw_visual")
            gs.append(GeometryFrame(tuple(faces + hand + [draw]), True,
                                    ("component_count_outside_reviewed_range", "meld_candidates_detected"), frame, "capture"))
            ms.append(MeldSnapshot(frame / 60, "player", groups, frame=frame,
                                   trusted=True, evidence_refs=("source_sha:" + sha,),
                                   source_session="capture", stream_epoch=0))
        return gs, ms, dict(source_sha256=sha, expected_source_sha256=sha,
                           reviewed_rgb_hashes={i: "b" * 64 for i in range(5)})

    def test_count_only_success_preserves_geometry_untrusted(self):
        gs, ms, kwargs = self.fixture()
        result = review_short_hand_counts(gs, ms, **kwargs)
        self.assertTrue(result.allowed)
        self.assertEqual((result.hand_count, result.draw_count, result.meld_group_count), (7, 1, 3))
        self.assertTrue(all(g.geometry_untrusted for g in gs))
        self.assertFalse(result.advice_allowed)
        self.assertFalse(result.safe_for_runtime)

    def test_negative_provenance_and_structure_cases_fail(self):
        cases = ["sha", "rgb", "epoch", "actor", "frame", "untrusted", "fragment", "count", "other_issue"]
        for case in cases:
            with self.subTest(case=case):
                gs, ms, kw = self.fixture()
                if case == "sha": kw["expected_source_sha256"] = "c" * 64
                if case == "rgb": kw["reviewed_rgb_hashes"].pop(2)
                if case == "epoch": ms[2] = replace(ms[2], stream_epoch=1)
                if case == "actor": ms[2] = replace(ms[2], actor="opponent")
                if case == "frame": gs[2] = replace(gs[2], frame=99)
                if case == "untrusted": ms[2] = replace(ms[2], trusted=False)
                if case == "fragment": gs[2] = replace(gs[2], components=gs[2].components + (replace(gs[2].components[0], region_candidate="unknown"),))
                if case == "count": ms[2] = replace(ms[2], groups=ms[2].groups[:2])
                if case == "other_issue": gs[2] = replace(gs[2], issues=gs[2].issues + ("fragmented_or_occluded_layout",))
                self.assertFalse(review_short_hand_counts(gs, ms, **kw).allowed)

    def test_four_frames_cannot_claim_stability(self):
        gs, ms, kwargs = self.fixture()
        self.assertFalse(review_short_hand_counts(gs[:4], ms[:4], **kwargs).allowed)
