import hashlib
import json
from pathlib import Path
import tempfile
import unittest

try:
    from PIL import Image
    from workspace.vision.tiles_runtime_v0_2.runtime_reader import prepare_runtime_resources
    from workspace.vision.tiles_runtime_v0_2.experimental_training_review import (
        with_reviewed_training_exclusions,
    )
except ImportError:
    prepare_runtime_resources = None


@unittest.skipUnless(prepare_runtime_resources is not None, 'Vision dependencies unavailable')
class ExperimentalTrainingReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / 'templates/bad.png'
        self.image.parent.mkdir()
        Image.new('RGB', (48, 72), 'white').save(self.image)
        self.label = dict(image='templates/bad.png', tile_id='P1', sha256='a' * 64,
                          source_session='s', region='hand_region', bbox=[0, 0, 48, 72],
                          approved=True)
        Image.new('RGB', (48, 72), 'gray').save(self.root / 'templates/good.png')
        self.good = dict(self.label, image='templates/good.png', tile_id='P2',
                         sha256='b' * 64, source_session='other')
        self.resources = dict(root=self.root, labels=[self.label, self.good],
                              training_labels=[self.label, self.good], classifier=object(), marker=object())
        self.review = dict(development_only=True, changes_runtime_labels=False,
            review_authority='ASSISTANT_VISUAL_REVIEW_REVEALED_DEVELOPMENT',
            excluded_training_images=[dict(image=self.label['image'], tile_id='P1',
                source_sha256='a' * 64,
                crop_file_sha256=hashlib.sha256(self.image.read_bytes()).hexdigest())])
        self.path = self.root / 'review.json'

    def apply(self):
        self.path.write_text(json.dumps(self.review))
        return with_reviewed_training_exclusions(self.resources, self.path)

    def test_rebuilds_consistent_coverage_without_mutating_input(self):
        original = self.resources['classifier']
        result = self.apply()
        self.assertEqual(result['training_labels'], [self.good])
        self.assertEqual(result['labels'], [self.good])
        self.assertEqual(result['covered'], {'P2'})
        self.assertNotIn('P1', result['classifier'].templates)
        self.assertEqual(result['experimental_training_review']['removed_training_labels'], 1)
        self.assertEqual(self.resources['training_labels'], [self.label, self.good])
        self.assertIs(self.resources['classifier'], original)
        self.assertIs(result['marker'], self.resources['marker'])

    def test_changed_pixels_fail_closed(self):
        Image.new('RGB', (48, 72), 'black').save(self.image)
        with self.assertRaisesRegex(ValueError, 'byte hash'):
            self.apply()

    def test_changed_source_or_label_fail_closed(self):
        for field, value in [('source_sha256', 'b' * 64), ('tile_id', 'P2')]:
            with self.subTest(field=field):
                original = self.review['excluded_training_images'][0][field]
                self.review['excluded_training_images'][0][field] = value
                with self.assertRaisesRegex(ValueError, 'label/source'):
                    self.apply()
                self.review['excluded_training_images'][0][field] = original

    def test_traversal_duplicate_and_unlisted_paths_rejected(self):
        entry = self.review['excluded_training_images'][0]
        for name in ('../bad.png', str(self.image), 'templates/missing.png'):
            with self.subTest(name=name):
                entry['image'] = name
                with self.assertRaises(ValueError):
                    self.apply()
        entry['image'] = self.label['image']
        self.review['excluded_training_images'].append(dict(entry))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.apply()

    def test_missing_development_authority_rejected(self):
        self.review['changes_runtime_labels'] = True
        with self.assertRaisesRegex(ValueError, 'development'):
            self.apply()

    def test_session_exclusion_is_not_undone(self):
        self.resources['training_labels'] = [self.good]
        result = self.apply()
        self.assertEqual(result['training_labels'], [self.good])
        self.assertEqual(result['experimental_training_review']['removed_training_labels'], 0)

    def test_empty_remaining_bank_stops_instead_of_reusing_old_classifier(self):
        self.resources['training_labels'] = [self.label]
        with self.assertRaisesRegex(ValueError, 'No approved tile labels'):
            self.apply()
