import unittest

from workspace.vision.public_claim_hand_count_delta import SourceScopedStableHandCount, review_new_meld_hand_count_delta
from workspace.vision.public_hand_identity_delta import StableHandIdentitySnapshot, review_hand_identity_delta
from workspace.vision.public_hand_identity_fact_adapter import identity_delta_to_hand_fact


class IdentityHandFactAdapterTests(unittest.TestCase):
    def test_exact_removed_tiles_are_preserved(self):
        sha="a"*64
        cb=SourceScopedStableHandCount("s",sha,0,100,"player",16,"STABLE_HAND",True,True,True,True,evidence_ref="cb")
        ca=SourceScopedStableHandCount("s",sha,0,102,"player",13,"STABLE_HAND",True,True,True,True,evidence_ref="ca")
        cr=review_new_meld_hand_count_delta(cb,ca,new_meld_first_visible_frame=101,new_meld_face_count=4,pre_sample_brackets_onset=True,post_sample_before_followup_discard=True,independent_public_meld_onset_verified=True)
        b=StableHandIdentitySnapshot("s",sha,0,100,"player",("P6","P6","P6","M1"),.9,.82,True,True,True,True,"ib")
        a=StableHandIdentitySnapshot("s",sha,0,102,"player",("M1",),.91,.82,True,True,True,True,"ia")
        delta=review_hand_identity_delta(b,a,cr)
        fact=identity_delta_to_hand_fact(b,a,delta,timestamp_seconds=47.4)
        self.assertIsNotNone(fact)
        self.assertEqual(fact.observation.details["removed_tiles"], ["P6"]*3)
        self.assertTrue(fact.observation.details["hand_delta_identity_observed"])
        self.assertEqual(fact.observation.confidence,.9)


if __name__=="__main__":
    unittest.main()
