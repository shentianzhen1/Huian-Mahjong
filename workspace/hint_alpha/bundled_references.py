"""Versioned, byte-verified development reference assets shipped with the app."""
import hashlib
import json
from pathlib import Path

REFERENCE_VERSION = '2026.10.25.4'


def resolve_bundled_references(project_root):
    folder = Path(project_root) / 'dataset/tiles_runtime_v0_2/reference_pack'
    metadata = json.loads((folder / 'bundle.json').read_text(encoding='utf-8'))
    if metadata['version'] != REFERENCE_VERSION:
        raise ValueError('素材版本与程序不匹配')
    files = metadata['files']
    if 'selected.json' not in files:
        raise ValueError('素材清单缺失')
    for name, digest in files.items():
        if Path(name).name != name or not (folder / name).is_file():
            raise ValueError('素材文件缺失：' + name)
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
            raise ValueError('素材文件校验失败：' + name)
    manifest = json.loads((folder / 'selected.json').read_text(encoding='utf-8'))
    if not manifest['rows'] or any(row['crop'] not in files for row in manifest['rows']):
        raise ValueError('牌面图片未登记')
    return folder / 'selected.json', metadata['version'], len(manifest['rows'])


def copy_bundled_references(project_root, target_root):
    import shutil
    manifest, version, count = resolve_bundled_references(project_root)
    target = Path(target_root) / 'dataset/tiles_runtime_v0_2/reference_pack'
    shutil.copytree(manifest.parent, target, dirs_exist_ok=True)
    resolve_bundled_references(target_root)
    return version, count
