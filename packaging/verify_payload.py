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
    for inventory in ('label_sha256', 'template_sha256'):
        for relative, digest in manifest[inventory].items():
            path = dataset / relative
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise SystemExit(f'Build-source mismatch: {relative}')
    label_paths = [dataset / 'labels.jsonl']
    reviewed_additions = dataset / 'labels_reviewed_additions'
    if reviewed_additions.is_dir():
        label_paths.extend(sorted(reviewed_additions.glob('*.jsonl')))
    actual_labels = {path.relative_to(dataset).as_posix() for path in label_paths}
    if actual_labels != set(manifest['label_sha256']):
        raise SystemExit('Reviewed label inventory mismatch')
    labels = [
        json.loads(line)
        for label_path in label_paths
        for line in label_path.read_text(encoding='utf-8').splitlines()
        if line
    ]
    for row in labels:
        if row.get('approved') is True or row.get('status') == 'approved':
            template = dataset / row['image']
            assert template.is_file(), row['image']
            if row['image'] not in manifest['template_sha256']:
                raise SystemExit(f"Template absent from build-source inventory: {row['image']}")
            if row.get('asset_sha256'):
                assert hashlib.sha256(template.read_bytes()).hexdigest() == row['asset_sha256'], row['image']
    assert (dataset / 'manifest.json').is_file()
    assert not manifest['executor_enabled']
    print(f"Verified {len(manifest['payload_sha256'])} payload files; version {manifest['project_version']}; {len(labels)} labels")


if __name__ == '__main__':
    verify(Path(sys.argv[1]))
