"""Build an offline Windows test installer from .build-hint dependencies."""
import hashlib
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from huian.version import PROJECT_VERSION

BUILD_ID = 'integrated-' + datetime.now().strftime('%Y%m%d-%H%M%S')
BUILD = ROOT / 'build' / ('hint-installer-' + BUILD_ID)
PAYLOAD = BUILD / 'payload'
RUNTIME = PAYLOAD / 'runtime'
DIST = ROOT / 'dist'
DEPENDENCY_LOCK = ROOT / 'packaging' / 'constraints-windows-py314.txt'


def read_dependency_lock(path):
    """Read exact runtime pins; malformed/duplicate constraints fail the build."""
    pins = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.+!-]*)', line)
        if not match:
            raise ValueError(f'Invalid exact dependency pin: {line}')
        name = re.sub(r'[-_.]+', '-', match[1]).lower()
        if name in pins:
            raise ValueError(f'Duplicate dependency pin: {name}')
        pins[name] = match[2]
    if not pins:
        raise ValueError('Dependency lock is empty')
    return pins


def verify_dependency_versions(expected, actual):
    """Reject a stale or unconstrained build environment before copying it."""
    for name, version in expected.items():
        if actual.get(name) != version:
            raise ValueError(f'Dependency version mismatch: {name}: expected {version}, got {actual.get(name)}')


def installed_dependencies(python, expected):
    script = (
        'import importlib.metadata, json, sys; '
        'print(json.dumps({name: importlib.metadata.version(name) '
        'for name in json.loads(sys.argv[1])}))'
    )
    return json.loads(subprocess.check_output(
        [str(python), '-c', script, json.dumps(list(expected))], text=True,
    ))


def main():
    if sys.version_info[:3] != (3, 14, 7):
        raise SystemExit('Windows test installer requires the pinned Python 3.14.7 runtime.')
    dependency_versions = read_dependency_lock(DEPENDENCY_LOCK)
    actual_versions = installed_dependencies(
        ROOT / '.build-hint/Scripts/python.exe', dependency_versions,
    )
    verify_dependency_versions(dependency_versions, actual_versions)
    if PAYLOAD.exists():
        raise SystemExit('Build payload already exists; use a new build directory.')
    RUNTIME.mkdir(parents=True)
    DIST.mkdir(exist_ok=True)
    base = Path(sys.base_prefix)
    for name in ('python.exe', 'pythonw.exe', 'python3.dll', 'python314.dll',
                 'vcruntime140.dll', 'vcruntime140_1.dll', 'LICENSE.txt'):
        shutil.copy2(base / name, RUNTIME / name)
    shutil.copytree(base / 'DLLs', RUNTIME / 'DLLs')
    shutil.copytree(base / 'tcl', RUNTIME / 'tcl')
    shutil.copytree(base / 'Lib', RUNTIME / 'Lib',
                    ignore=shutil.ignore_patterns('site-packages', '__pycache__', 'test', 'tests'))
    site = RUNTIME / 'Lib' / 'site-packages'
    shutil.copytree(ROOT / '.build-hint' / 'Lib' / 'site-packages', site,
                    ignore=shutil.ignore_patterns('__pycache__'))
    # Overlay current source: the dependency environment may contain an older wheel.
    source_hashes = {}
    for package in ('huian', 'mahjong_framework', 'workspace/ai',
                    'workspace/simulator', 'workspace/vision', 'workspace/hint_alpha'):
        for path in sorted((ROOT / package).rglob('*.py')):
            if path.name.startswith('test_') or '__pycache__' in path.parts:
                continue
            relative = path.relative_to(ROOT)
            destination = site / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            source_hashes[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    dataset = ROOT / 'dataset' / 'tiles_runtime_v0_2'
    dataset_target = site / 'dataset' / 'tiles_runtime_v0_2'
    dataset_target.mkdir(parents=True)
    labels = dataset / 'labels.jsonl'
    shutil.copy2(labels, dataset_target / 'labels.jsonl')
    shutil.copy2(dataset / 'manifest.json', dataset_target / 'manifest.json')

    label_paths = [labels]
    reviewed_additions = dataset / 'labels_reviewed_additions'
    if reviewed_additions.is_dir():
        reviewed_target = dataset_target / 'labels_reviewed_additions'
        reviewed_target.mkdir(parents=True, exist_ok=True)
        for sidecar in sorted(reviewed_additions.glob('*.jsonl')):
            if not sidecar.is_file():
                continue
            shutil.copy2(sidecar, reviewed_target / sidecar.name)
            label_paths.append(sidecar)

    template_hashes = {}
    for label_path in label_paths:
        for row in (json.loads(line) for line in label_path.read_text(encoding='utf-8').splitlines() if line):
            if not (row.get('approved') is True or row.get('status') == 'approved'):
                continue
            template = (dataset / row['image']).resolve()
            relative = template.relative_to(dataset.resolve())
            destination = dataset_target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(template, destination)
            template_hashes[relative.as_posix()] = hashlib.sha256(template.read_bytes()).hexdigest()
    # Phase detector requires these six already-reviewed UI templates.
    evidence = Path('references/capture_review/2026-09-13')
    (site / evidence).mkdir(parents=True)
    for name in ('opening_gold_dice_and_room_settings.jpg', 'opening_gold_reveal_wall_108.jpg',
                 'liuju_zero_settlement.jpg', 'pinghu_11_settlement.jpg',
                 'pinghu_16_settlement.jpg', 'zimo_38_kong_settlement.jpg'):
        shutil.copy2(ROOT / evidence / name, site / evidence / name)
    shutil.copy2(ROOT / 'packaging' / 'launch.py', PAYLOAD / 'launch.py')
    shutil.copy2(DEPENDENCY_LOCK, PAYLOAD / 'DEPENDENCIES.txt')
    for name, args in [('START_HINT_ALPHA.bat', ''), ('CHECK_HINT_ALPHA.bat', '--check')]:
        (PAYLOAD / name).write_text('@echo off\ncd /d "%~dp0"\nset PYTHONUTF8=1\n'
            + '"runtime\\python.exe" -B launch.py ' + args
            + '\nif errorlevel 1 pause\n', encoding='utf-8')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    manifest = {'project_version': PROJECT_VERSION, 'build': BUILD_ID, 'commit': commit,
                'python_version': '.'.join(map(str, sys.version_info[:3])),
                'dependency_versions': actual_versions,
                'dependency_lock_sha256': hashlib.sha256(DEPENDENCY_LOCK.read_bytes()).hexdigest(),
                'source_sha256': source_hashes, 'template_sha256': template_hashes,
                'label_sha256': {path.relative_to(dataset).as_posix():
                    hashlib.sha256(path.read_bytes()).hexdigest() for path in label_paths},
                'shanten_advisory_connected': True, 'experimental_runtime_advisory': True,
                'executor_enabled': False, 'live_ai_advice_connected': False,
                'dependencies': subprocess.check_output([str(ROOT / '.build-hint/Scripts/python.exe'),
                    '-m', 'pip', 'freeze'], text=True).splitlines()}
    (PAYLOAD / '使用说明.txt').write_text(
        f'惠安麻将 Hint Alpha {PROJECT_VERSION} 测试版\n双击桌面快捷方式启动。无需另装 Python。\n'
        '新增人工录牌向听与候选弃牌、实验实时识别向听。低置信/黑屏/断流/过期时停用。\n'
        '启动后可点人工录牌。实时识别未正式晋级，界面标为实验；识别不足时BLOCKED。\n'
        '完整V0.10合法动作建议尚未接入。Executor关闭。\n'
        'PublicState OCR需另有Tesseract；缺失时明确显示不可用，采集仍可运行。\n'
        '证据保存在安装目录data/hint_alpha。CHECK_HINT_ALPHA.bat可自检。\n'
        '请保留数据；卸载可删除快捷方式及对应安装目录。\n', encoding='utf-8')
    manifest['payload_sha256'] = {
        path.relative_to(PAYLOAD).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(PAYLOAD.rglob('*')) if path.is_file()
    }
    (PAYLOAD / 'BUILD_INFO.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    archive = BUILD / 'payload.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(PAYLOAD.rglob('*')):
            if path.is_file():
                z.write(path, path.relative_to(PAYLOAD))
    exe = DIST / ('HuianMahjong_Test_' + PROJECT_VERSION + '_' + BUILD_ID + '_Setup.exe')
    compiler = Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
    installer_source = BUILD / 'TestInstaller.cs'
    installer_source.write_text(
        (ROOT / 'packaging/TestInstaller.cs').read_text(encoding='utf-8').replace(
            '__PROJECT_VERSION__', PROJECT_VERSION), encoding='utf-8')
    subprocess.run([str(compiler), '/nologo', '/target:winexe', '/platform:x64',
        '/reference:System.IO.Compression.dll', '/reference:System.IO.Compression.FileSystem.dll',
        '/reference:System.Windows.Forms.dll', '/out:' + str(exe),
        '/resource:' + str(archive) + ',payload.zip', str(installer_source)], check=True)
    shutil.copy2(PAYLOAD / 'BUILD_INFO.json', DIST / 'BUILD_INFO.json')
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    exe.with_suffix('.exe.sha256').write_text(digest + '  ' + exe.name + '\n', encoding='ascii')
    print(json.dumps({'installer': str(exe), 'bytes': exe.stat().st_size, 'sha256': digest}))


if __name__ == '__main__':
    main()
