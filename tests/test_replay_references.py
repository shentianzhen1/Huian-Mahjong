import unittest
from pathlib import Path

try:
    import cv2
except ImportError:
    cv2 = None

@unittest.skipUnless(cv2 is not None, 'Vision dependencies unavailable')
class ReplayReferenceTests(unittest.TestCase):
    def test_installed_packet_applies_review_and_preserves_base_resources(self):
        from workspace.hint_alpha.bundled_references import resolve_bundled_references
        from workspace.hint_alpha.replay_references import apply_replay_references
        from workspace.vision.tiles_runtime_v0_2.runtime_reader import prepare_runtime_resources
        root=Path(__file__).resolve().parents[1]
        manifest,version,count=resolve_bundled_references(root)
        base=prepare_runtime_resources(root/'dataset/tiles_runtime_v0_2','replay-test')
        original=len(base['training_labels'])
        adapted,meta=apply_replay_references(base,manifest)
        self.assertEqual((meta['version'],meta['count']),(version,count))
        self.assertEqual(len(adapted['classifier'].extra_features),20)
        self.assertEqual(adapted['classifier'].opened_gold_reference_count,7)
        self.assertEqual(len(adapted['training_labels']),137)
        self.assertEqual(meta['training_review']['removed_training_labels'],10)
        self.assertEqual(len(base['training_labels']),original)
        self.assertTrue(adapted['geometry_detector'].keywords['edge_seams'])
        self.assertFalse(meta['formal_promotion_evidence'])
