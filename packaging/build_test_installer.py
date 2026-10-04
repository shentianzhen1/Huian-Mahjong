"""Build an offline Windows test installer from .build-hint dependencies."""
import hashlib
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUILD_ID = 'shanten-' + datetime.now().strftime('%Y%m%d-%H%M%S')
BUILD = ROOT / 'build' / ('hint-installer-' + BUILD_ID)
PAYLOAD = BUILD / 'payload'
RUNTIME = PAYLOAD / 'runtime'
DIST = ROOT / 'dist'


def main():
    if PAYLOAD.exists():
        raise SystemExit('Build payload already exists; use a new build directory.')
    RUNTIME.mkdir(parents=True)
    DIST.mkdir(exist_ok=True)
    base = Path(sys.base_prefix)
    for name in ('python.exe', 'pythonw.exe', 'python3.dll', 'python314.dll',
                 'vcruntime140.dll', 'vcruntime140_1.dll', 'LICENSE.txt'):
        shutil.copy2(base / name, RUNTIME / name)
    shutil.copytree(base / 'DLLs', RUNTIME / 'DLLs')
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
    template_hashes = {}
    for row in (json.loads(line) for line in labels.read_text(encoding='utf-8').splitlines() if line):
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
    for name, args in [('START_HINT_ALPHA.bat', ''), ('CHECK_HINT_ALPHA.bat', '--check')]:
        (PAYLOAD / name).write_text('@echo off\ncd /d "%~dp0"\nset PYTHONUTF8=1\n'
            + '"runtime\\python.exe" -B launch.py ' + args
            + '\nif errorlevel 1 pause\n', encoding='utf-8')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    manifest = {'project_version': '0.2.0', 'build': BUILD_ID, 'commit': commit,
                'source_sha256': source_hashes, 'template_sha256': template_hashes,
                'shanten_advisory_connected': True, 'experimental_runtime_advisory': True,
                'executor_enabled': False, 'live_ai_advice_connected': False,
                'dependencies': subprocess.check_output([str(ROOT / '.build-hint/Scripts/python.exe'),
                    '-m', 'pip', 'freeze'], text=True).splitlines()}
    (PAYLOAD / 'BUILD_INFO.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (PAYLOAD / '使用说明.txt').write_text(
        '惠安麻将 Hint Alpha 0.2.0 测试版\n双击桌面快捷方式启动。无需另装 Python。\n'
        '新增人工录牌向听与候选弃牌、实验实时识别向听。低置信/黑屏/断流/过期时停用。\n'
        '启动后可点人工录牌。实时识别未正式晋级，界面标为实验；识别不足时BLOCKED。\n'
        '完整V0.10合法动作建议尚未接入。Executor关闭。\n'
        'PublicState OCR需另有Tesseract；缺失时明确显示不可用，采集仍可运行。\n'
        '证据保存在安装目录data/hint_alpha。CHECK_HINT_ALPHA.bat可自检。\n'
        '请保留数据；卸载可删除快捷方式及对应安装目录。\n', encoding='utf-8')
    archive = BUILD / 'payload.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(PAYLOAD.rglob('*')):
            if path.is_file():
                z.write(path, path.relative_to(PAYLOAD))
    exe = DIST / ('HuianMahjong_Test_0.2.0_' + BUILD_ID + '_Setup.exe')
    compiler = Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
    subprocess.run([str(compiler), '/nologo', '/target:winexe', '/platform:x64',
        '/reference:System.IO.Compression.dll', '/reference:System.IO.Compression.FileSystem.dll',
        '/reference:System.Windows.Forms.dll', '/out:' + str(exe),
        '/resource:' + str(archive) + ',payload.zip', str(ROOT / 'packaging/TestInstaller.cs')], check=True)
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    exe.with_suffix('.exe.sha256').write_text(digest + '  ' + exe.name + '\n', encoding='ascii')
    print(json.dumps({'installer': str(exe), 'bytes': exe.stat().st_size, 'sha256': digest}))


if __name__ == '__main__':
    main()
