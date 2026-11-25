import unittest
from copy import deepcopy
from unittest.mock import patch
from workspace.vision.tiles_runtime_v0_2.local_meld_trial import with_local_meld_trial
from workspace.hint_alpha.runtime_pipeline import RuntimeAdvicePipeline
from workspace.vision.current_state_snapshot import assess_current_snapshot, SnapshotCapability
from tests.test_live_opening_tracker import runtime_report
try:
    import numpy as np
    from PIL import Image
    from workspace.vision.tiles_runtime_v0_2.dynamic_geometry import GeometryComponent, GeometryFrame, _normalized
except ImportError:
    np = None


class TrialAdmissionTests(unittest.TestCase):
    def test_trial_factory_does_not_mutate_default_resources(self):
        classifier = object()
        base = {'classifier': classifier}
        result = with_local_meld_trial(base)
        self.assertEqual(base, {'classifier':classifier})
        self.assertIs(result['classifier'], classifier)
        self.assertTrue(result['experimental_local_meld_geometry'])

    def test_flagged_geometry_requires_trial_and_stays_structural(self):
        report = runtime_report()
        report['experimental_local_meld_geometry'] = True
        saved = deepcopy(report)
        for trial, experimental in [(False, True),(True,False)]:
            p = RuntimeAdvicePipeline(allow_unvalidated_hand_sources=trial)
            self.assertFalse(p.evaluate(report,captured=1,experimental=experimental).display_allowed)
        p = RuntimeAdvicePipeline(allow_unvalidated_hand_sources=True)
        result = p.evaluate(report,captured=1,experimental=True)
        self.assertTrue(result.display_allowed)
        self.assertIn('experimental_meld_geometry_unvalidated',result.hint.issues)
        assessment = assess_current_snapshot(result.snapshot)
        self.assertFalse(assessment.allows(SnapshotCapability.VISIBLE_REMAINDERS))
        self.assertFalse(assessment.allows(SnapshotCapability.DANGER_HINT))
        self.assertFalse(result.safe_for_executor)
        self.assertEqual(report,saved)


@unittest.skipUnless(np is not None,'Vision dependencies unavailable')
class TrialGeometryTests(unittest.TestCase):
    def component(self, box, role='meld'):
        return GeometryComponent(box,_normalized(box,1108,512),role,.9,3,'scope')

    def test_local_recovery_keeps_source_pixels_and_hand_boxes(self):
        from workspace.vision.tiles_runtime_v0_2.local_meld_trial import detect_local_meld_trial
        boxes=[(101,442,51,54),(145,442,49,54),(248,442,48,54),(294,442,45,54)]
        components=tuple(self.component(box) for box in boxes)+(self.component((416,442,49,65),'hand'),)
        base=GeometryFrame(components,False,(),3,'scope')
        image=Image.new('RGB',(1108,512),(100,100,100));pixels=image.tobytes()
        proposals=[(194,442,42,56),(337,442,44,52)]
        with patch('workspace.vision.tiles_runtime_v0_2.dynamic_geometry.detect_dynamic_geometry',return_value=base), \
             patch('workspace.vision.tiles_runtime_v0_2.dynamic_geometry._bright_boxes',return_value=proposals):
            result=detect_local_meld_trial(image,frame=3,session='scope')
        self.assertEqual(len(result.components),7)
        for old,new in zip(base.components,result.components):self.assertIs(old,new)
        self.assertEqual(image.tobytes(),pixels)
        from workspace.vision.runtime_public_adapter import player_meld_snapshot_from_runtime
        before={'components':[c.to_dict() for c in base.components],'geometry_untrusted':False,'concealed_tile_count':10,'frames':[1,2,3]}
        self.assertEqual(len(player_meld_snapshot_from_runtime(before,timestamp_seconds=1).groups),1)
        report={**before,'components':[c.to_dict() for c in result.components], 'experimental_local_meld_geometry':True}
        grouped=player_meld_snapshot_from_runtime(report,timestamp_seconds=1)
        self.assertEqual([len(g.tiles) for g in grouped.groups],[3,3])
        self.assertTrue(all(tile is None for group in grouped.groups for tile in group.tiles))

    def test_untrusted_or_no_meld_geometry_does_not_generate_proposals(self):
        from workspace.vision.tiles_runtime_v0_2.local_meld_trial import detect_local_meld_trial
        for base in [GeometryFrame((),False,(),3,'scope'), GeometryFrame((self.component((101,442,51,54)),),True,(),3,'scope')]:
            with patch('workspace.vision.tiles_runtime_v0_2.dynamic_geometry.detect_dynamic_geometry',return_value=base), \
                 patch('workspace.vision.tiles_runtime_v0_2.dynamic_geometry._bright_boxes') as candidates:
                self.assertIs(detect_local_meld_trial(Image.new('RGB',(1108,512))),base)
                candidates.assert_not_called()
