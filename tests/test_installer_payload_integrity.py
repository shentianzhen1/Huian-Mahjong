"""Check asset/source integrity even when an altered payload is re-inventoried."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

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
