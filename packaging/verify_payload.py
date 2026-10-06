"""Verify the offline payload against its complete build inventory."""
import hashlib
import json
from pathlib import Path
import sys


def verify(root):
    manifest = json.loads((root / 'BUILD_INFO.json').read_text(encoding='utf-8'))
    for relative, digest in manifest['payload_sha256'].items():
        path = root / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise SystemExit(f'Payload mismatch: {relative}')
    site = root / 'runtime/Lib/site-packages'
    for relative, digest in manifest['source_sha256'].items():
        assert hashlib.sha256((site / relative).read_bytes()).hexdigest() == digest, relative
    dataset = site / 'dataset/tiles_runtime_v0_2'
    labels = [json.loads(line) for line in (dataset / 'labels.jsonl').read_text(encoding='utf-8').splitlines() if line]
    for row in labels:
        if row.get('approved') is True or row.get('status') == 'approved':
            assert (dataset / row['image']).is_file(), row['image']
    assert (dataset / 'manifest.json').is_file()
    assert not manifest['executor_enabled']
    print(f"Verified {len(manifest['payload_sha256'])} payload files; version {manifest['project_version']}; {len(labels)} labels")


if __name__ == '__main__':
    verify(Path(sys.argv[1]))
