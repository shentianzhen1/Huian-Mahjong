import copy
import unittest
from workspace.hint_alpha.gold_source_trial import trial_opened_gold_report


class OpenedGoldTrialTests(unittest.TestCase):
    def report(self):
        item=dict(candidate_tile_id='M4',tile_id='UNKNOWN',tile_confidence=.91,
            identity_reason='class_not_cross_session_validated_in_region',opened_gold_reference_supported=True)
        return dict(geometry_untrusted=False,frames=[1,2,3],
            components=[dict(item,region_candidate='gold',frame=3)],
            gold_identity_observations=[dict(item,frame=n) for n in [1,2,3]])

    def test_only_reference_backed_three_distinct_frames_restore_copy(self):
        original=self.report();before=copy.deepcopy(original)
        restored,used=trial_opened_gold_report(original)
        self.assertEqual(original,before)
        self.assertEqual(used,('M4','M4','M4'))
        self.assertEqual(restored['components'][0]['tile_id'],'M4')
        self.assertEqual(restored['components'][0]['original_identity_reason'],
                         'class_not_cross_session_validated_in_region')

    def test_missing_reference_low_score_conflicts_and_other_reasons_stay_blocked(self):
        for key,value in [('opened_gold_reference_supported',False),('tile_confidence',.81),
                          ('tile_confidence',float('nan')),('tile_confidence',True),
                          ('candidate_tile_id','M6'),('identity_reason','below_confidence_threshold'),
                          ('frame',90)]:
            r=self.report();r['gold_identity_observations'][0][key]=value
            with self.subTest(key=key,value=value):
                self.assertIs(trial_opened_gold_report(r)[0],r)
        r=self.report();r['gold_identity_observations'].pop()
        self.assertIs(trial_opened_gold_report(r)[0],r)
        r=self.report();r['geometry_untrusted']=True
        self.assertIs(trial_opened_gold_report(r)[0],r)

    def test_default_mode_and_switch_off_cannot_inherit_trial_gold(self):
        from workspace.hint_alpha.runtime_pipeline import RuntimeAdvicePipeline
        report=self.report();report.update(session='gold-test',stream_epoch=0,confidence_threshold=.82)
        strict=RuntimeAdvicePipeline().evaluate(report,captured=1.,experimental=True)
        self.assertFalse(strict.snapshot.gold_trusted)
        pipeline=RuntimeAdvicePipeline(allow_unvalidated_hand_sources=True)
        trial=pipeline.evaluate(report,captured=1.,experimental=True)
        self.assertTrue(trial.snapshot.gold_trusted)
        self.assertTrue(trial.gold_source_trial)
        self.assertFalse(trial.opening_fact.state_tracker_ready)
        self.assertEqual(trial.opening_fact.source_kind,'EXPERIMENTAL_REFERENCE_GOLD')
        missing=dict(report,frames=[4,5,6],components=[],gold_identity_observations=[])
        carried=pipeline.evaluate(missing,captured=1.3,experimental=True)
        self.assertTrue(carried.gold_source_trial)
        self.assertFalse(carried.opening_fact.state_tracker_ready)
        pipeline.allow_unvalidated_hand_sources=False
        stopped=pipeline.evaluate(missing,captured=1.6,experimental=True)
        self.assertFalse(stopped.snapshot.gold_trusted)
        self.assertFalse(stopped.gold_source_trial)
