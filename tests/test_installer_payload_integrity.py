"""Check asset/source integrity even when an altered payload is re-inventoried."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys

spec = importlib.util.spec_from_file_location('verify_payload', Path(__file__).resolve().parents[1] / 'packaging/verify_payload.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PayloadIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dataset = self.root / 'runtime/Lib/site-packages/dataset/tiles_runtime_v0_2'
        self.dataset.mkdir(parents=True)
        self.asset = self.dataset / 'templates/hand/S2.pgm'
        self.asset.parent.mkdir(parents=True)
        self.asset.write_bytes(b'P2\n1 1\n255\n128\n')
        self.sidecar = self.dataset / 'labels_reviewed_additions/s2.jsonl'
        self.sidecar.parent.mkdir()
        self.sidecar.write_text(json.dumps({'approved': True, 'image': 'templates/hand/S2.pgm', 'asset_sha256': self.digest(self.asset)}) + '\n')
        (self.dataset / 'labels.jsonl').write_bytes(b'')
        (self.dataset / 'manifest.json').write_text('{}')
        self.manifest = {'project_version': 'test', 'executor_enabled': False, 'source_sha256': {},
            'template_sha256': {'templates/hand/S2.pgm': self.digest(self.asset)},
            'label_sha256': {p.relative_to(self.dataset).as_posix(): self.digest(p) for p in (self.dataset / 'labels.jsonl', self.sidecar)}}
        self.refresh_payload()

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def refresh_payload(self):
        self.manifest['payload_sha256'] = {p.relative_to(self.root).as_posix(): self.digest(p) for p in self.root.rglob('*') if p.is_file() and p.name != 'BUILD_INFO.json'}
        (self.root / 'BUILD_INFO.json').write_text(json.dumps(self.manifest))

    def test_original_bytes_pass(self):
        module.verify(self.root)

    def test_executor_must_be_false_not_merely_falsy(self):
        for value in (True, 0, None, "false"):
            with self.subTest(value=value):
                self.manifest['executor_enabled'] = value
                self.refresh_payload()
                with self.assertRaisesRegex(SystemExit, 'explicitly disabled'):
                    module.verify(self.root)

    def test_optimized_python_cannot_remove_executor_check(self):
        self.manifest['executor_enabled'] = True
        self.refresh_payload()
        result = subprocess.run([sys.executable, '-O', module.__file__, str(self.root)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Executor must be explicitly disabled', result.stderr)

    def test_optimized_python_cannot_remove_source_hash_check(self):
        source = self.root / 'runtime/Lib/site-packages/workspace/dummy.py'
        source.parent.mkdir(parents=True)
        source.write_text('pass\n')
        self.manifest['source_sha256'] = {'workspace/dummy.py': '0' * 64}
        self.refresh_payload()
        result = subprocess.run([sys.executable, '-O', module.__file__, str(self.root)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Source mismatch', result.stderr)

    def test_crlf_conversion_fails_even_with_refreshed_payload_hashes(self):
        self.asset.write_bytes(self.asset.read_bytes().replace(b'\n', b'\r\n'))
        self.refresh_payload()
        with self.assertRaisesRegex(SystemExit, 'Build-source mismatch'):
            module.verify(self.root)

    def test_missing_sidecar_fails_even_with_refreshed_payload_hashes(self):
        self.sidecar.unlink()
        self.refresh_payload()
        with self.assertRaisesRegex(SystemExit, 'Build-source mismatch'):
            module.verify(self.root)

    def test_uninventoried_referenced_asset_fails(self):
        self.manifest['template_sha256'] = {}
        self.refresh_payload()
        with self.assertRaisesRegex(SystemExit, 'absent from build-source inventory'):
            module.verify(self.root)

    def test_changed_dependency_lock_fails_after_payload_reinventory(self):
        lock = self.root / 'DEPENDENCIES.txt'
        lock.write_text('numpy==2.5.4\n')
        self.manifest['dependency_lock_sha256'] = self.digest(lock)
        self.refresh_payload()
        module.verify(self.root)
        lock.write_text('numpy==2.5.3\n')
        self.refresh_payload()
        with self.assertRaisesRegex(SystemExit, 'Dependency lock mismatch'):
            module.verify(self.root)

    def test_missing_dependency_lock_fails(self):
        self.manifest['dependency_lock_sha256'] = '0' * 64
        self.refresh_payload()
        with self.assertRaisesRegex(SystemExit, 'Dependency lock mismatch'):
            module.verify(self.root)
