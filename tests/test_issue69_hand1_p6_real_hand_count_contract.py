import json
import unittest
from pathlib import Path

from workspace.vision.public_claim_hand_count_delta import (
    SourceScopedStableHandCount,
    review_new_meld_hand_count_delta,
)

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/"references/vision/2026-10-01/issue69_hand1_p6_ming_gang_hand_count_v0_1.json"


class Hand1P6RealHandCountContractTests(unittest.TestCase):
    def test_real_derived_clip_corroborates_three_consumed_tiles(self):
        data=json.loads(ART.read_text(encoding="utf-8"))
        sha=data["source"]["sha256"]
        review=data["claim_count_review"]
        common=dict(
            source_session="hand1_p6_mobile_extended",
            source_sha256=sha,
            stream_epoch=0,
            actor="player",
            tracker_state="STABLE_HAND",
            tracker_trusted=True,
            tracker_stable=True,
            hand_geometry_region_verified=True,
            source_frame_verified=True,
            draw_event_in_sample=False,
            discard_event_in_sample=False,
            hand_resort_or_occlusion_in_sample=False,
            geometry_baseline_reset_in_sample=False,
        )
        before=SourceScopedStableHandCount(
            frame_index=review["before_frame"],
            semantic_concealed_count=review["before_count"],
            evidence_ref="upright_run:frames352-357",
            **common,
        )
        after=SourceScopedStableHandCount(
            frame_index=review["after_frame"],
            semantic_concealed_count=review["after_count"],
            evidence_ref="upright_run:frames358-362",
            **common,
        )
        out=review_new_meld_hand_count_delta(
            before,after,
            new_meld_first_visible_frame=review["new_meld_first_visible_frame"],
            new_meld_face_count=review["new_meld_face_count"],
            pre_sample_brackets_onset=True,
            post_sample_before_followup_discard=True,
            independent_public_meld_onset_verified=True,
        )
        self.assertEqual(
            out.status,
            "NEW_MELD_HAND_COUNT_DELTA_CORROBORATED_OWNER_ACTION_PENDING",
        )
        self.assertEqual(out.before_count,16)
        self.assertEqual(out.after_count,13)
        self.assertEqual(out.removed_count,3)


if __name__=="__main__":
    unittest.main()
