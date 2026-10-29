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

    def packet(self):
        self.path.write_text(json.dumps(self.review))
        manifest = self.root / 'selected.json'
        manifest.write_text(json.dumps(dict(version='trial-test-1',
            rows=[dict(crop='templates/good.png', truth='P2',
                rgb_sha256=hashlib.sha256(Image.open(self.root / 'templates/good.png')
                                         .convert('RGB').tobytes()).hexdigest())],
            experimental_training_review=dict(file=self.path.name,
                sha256=hashlib.sha256(self.path.read_bytes()).hexdigest()))))
        return manifest

    def test_packet_cache_keeps_clean_classifier_and_coverage_together(self):
        from workspace.vision.tiles_runtime_v0_2.experimental_hand_translation import cached_private_hand_packet
        manifest = self.packet()
        first = cached_private_hand_packet(self.resources, manifest)
        second = cached_private_hand_packet(self.resources, manifest)
        self.assertIs(first['classifier'], second['classifier'])
        self.assertEqual(second['covered'], {'P2'})
        self.assertEqual(second['training_labels'], [self.good])
        self.assertEqual(second['experimental_training_review']['removed_training_labels'], 1)
        self.assertEqual(self.resources['training_labels'], [self.label, self.good])

    def test_packet_cache_rechecks_review_and_excluded_pixels_on_hit(self):
        from workspace.vision.tiles_runtime_v0_2.experimental_hand_translation import cached_private_hand_packet
        manifest = self.packet()
        cached_private_hand_packet(self.resources, manifest)
        self.path.write_text(self.path.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'review hash'):
            cached_private_hand_packet(self.resources, manifest)
        manifest = self.packet()
        cached_private_hand_packet(self.resources, manifest)
        Image.new('RGB', (48, 72), 'black').save(self.image)
        with self.assertRaisesRegex(ValueError, 'crop byte hash'):
            cached_private_hand_packet(self.resources, manifest)

    def test_packet_review_cannot_escape_package(self):
        from workspace.vision.tiles_runtime_v0_2.experimental_hand_translation import cached_private_hand_packet
        manifest = self.packet()
        data = json.loads(manifest.read_text())
        data['experimental_training_review']['file'] = '../review.json'
        manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'review file/hash'):
            cached_private_hand_packet(self.resources, manifest)

    def test_reviewed_hand_role_requires_review_and_preserves_plain_hand_features(self):
        import numpy as np
        from workspace.vision.tiles_runtime_v0_2.experimental_hand_translation import with_private_hand_packet
        manifest = self.packet()
        plain = with_private_hand_packet(self.resources, manifest)
        data = json.loads(manifest.read_text())
        data['rows'][0]['role'] = 'hand_reviewed_training'
        manifest.write_text(json.dumps(data))
        reviewed = with_private_hand_packet(self.resources, manifest)
        self.assertEqual(plain['covered'], reviewed['covered'])
        self.assertEqual(plain['training_labels'], reviewed['training_labels'])
        self.assertTrue(np.array_equal(plain['classifier'].extra_features[0][1],
                                       reviewed['classifier'].extra_features[0][1]))
        del data['experimental_training_review']
        manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'requires a verified training review'):
            with_private_hand_packet(self.resources, manifest)

    def test_manual_ui_load_validates_before_replacing_current_packet(self):
        import ast
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        source = ast.parse(Path('workspace/hint_alpha/app.py').read_text())
        app_class = next(n for n in source.body if isinstance(n, ast.ClassDef)
                         and n.name == 'HintAlphaApp')
        method = next(n for n in app_class.body if isinstance(n, ast.FunctionDef)
                      and n.name == 'open_hand_reference_packet')
        manifest = self.packet()
        dialogs, messages = Mock(), Mock()
        dialogs.askopenfilename.return_value = str(manifest)
        namespace = dict(Path=Path, PROJECT_ROOT=self.root, filedialog=dialogs, messagebox=messages)
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<actual-ui-load>', 'exec'), namespace)
        app = SimpleNamespace(evidence=None, experimental_hand_packet=Path('old.json'),
            reference_pack_status=Mock(), runtime_status=Mock(), _toggle_hand_source_trial=Mock())
        with patch('workspace.vision.tiles_runtime_v0_2.runtime_reader.prepare_runtime_resources',
                   return_value=self.resources):
            self.path.write_text('tampered')
            namespace['open_hand_reference_packet'](app)
            self.assertEqual(app.experimental_hand_packet, Path('old.json'))
            app._toggle_hand_source_trial.assert_not_called()
            self.packet()
            namespace['open_hand_reference_packet'](app)
        self.assertEqual(app.experimental_hand_packet, manifest)
        self.assertIn('trial-test-1', app.reference_pack_status.set.call_args.args[0])
        app._toggle_hand_source_trial.assert_called_once()
