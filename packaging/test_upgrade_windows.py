"""Exercise the real EXE's upgrade path in a private temporary install root."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def run_install(installer, root, expected=0):
    result = subprocess.run([str(installer), '--install-test', str(root)], check=False, timeout=180)
    details = root.with_suffix('.error.txt')
    assert result.returncode == expected, details.read_text() if details.exists() else result.returncode


def broken_installer(directory, version):
    # A hash-consistent payload whose Python cannot run must fail its doctor,
    # without removing a working install or the desktop entry.
    files = {'runtime/python.exe': b'not an executable', 'launch.py': b'pass\n'}
    info = {'payload_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
    archive = directory / 'broken.zip'
    with zipfile.ZipFile(archive, 'w') as packet:
        for name, data in files.items():
            packet.writestr(name, data)
        packet.writestr('BUILD_INFO.json', json.dumps(info))
    source = directory / 'BrokenInstaller.cs'
    source.write_text((ROOT / 'packaging/TestInstaller.cs').read_text(encoding='utf-8').replace('__PROJECT_VERSION__', version), encoding='utf-8')
    executable = directory / 'BrokenInstaller.exe'
    compiler = Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
    subprocess.run([str(compiler), '/nologo', '/target:winexe', '/platform:x64',
                    '/reference:System.IO.Compression.dll', '/reference:System.IO.Compression.FileSystem.dll',
                    '/reference:System.Windows.Forms.dll', '/reference:System.Web.Extensions.dll',
                    '/out:' + str(executable), '/resource:' + str(archive) + ',payload.zip', str(source)], check=True)
    return executable


def main():
    import win32com.client

    installer = Path(sys.argv[1]).resolve()
    version = json.loads((ROOT / 'dist/BUILD_INFO.json').read_text(encoding='utf-8'))['project_version']
    with tempfile.TemporaryDirectory() as directory:
        scratch = Path(directory)
        root = scratch / 'install'
        desktop = root / 'desktop'
        desktop.mkdir(parents=True)
        legacy = root / (version + '-20261001000000000')
        (legacy / 'runtime').mkdir(parents=True)
        (legacy / 'runtime/python.exe').write_bytes(b'old-program')
        (legacy / 'launch.py').write_text('old launcher')
        (legacy / 'BUILD_INFO.json').write_text(json.dumps({'project_version': version,
            'build': 'integrated-test', 'source_sha256': {}, 'executor_enabled': False}))
        (legacy / 'data/hint_alpha').mkdir(parents=True)
        evidence = b'private-old-session\r\n'
        (legacy / 'data/hint_alpha/session.json').write_bytes(evidence)
        unrelated = root / 'personal'
        unrelated.mkdir()
        (unrelated / 'keep.txt').write_text('keep')
        shell = win32com.client.Dispatch('WScript.Shell')
        old_link = desktop / '惠安麻将测试版-20261001000000.lnk'
        link = shell.CreateShortcut(str(old_link))
        link.TargetPath = str(legacy / 'runtime/pythonw.exe')
        link.Save()
        archive = root / 'data/legacy' / legacy.name / 'hint_alpha/session.json'
        archive.parent.mkdir(parents=True)
        archive.write_bytes(b'conflicting old evidence')
        run_install(installer, root, expected=1)
        assert legacy.exists() and old_link.exists() and not (root / 'current').exists()
        assert archive.read_bytes() == b'conflicting old evidence'
        archive.unlink()
        run_install(installer, root)
        current = root / 'current'
        canonical = desktop / '惠安麻将测试版-向听辅助.lnk'
        assert current.is_dir() and not legacy.exists() and not old_link.exists()
        assert (root / 'data/legacy' / legacy.name / 'hint_alpha/session.json').read_bytes() == evidence
        assert (unrelated / 'keep.txt').read_text() == 'keep'
        assert len(list(desktop.glob('惠安麻将测试版-*.lnk'))) == 1
        assert Path(shell.CreateShortcut(str(canonical)).TargetPath) == current / 'runtime/pythonw.exe'
        active_data = root / 'data/hint_alpha/keep.json'
        active_data.parent.mkdir(parents=True, exist_ok=True)
        active_data.write_bytes(b'live-evidence')
        current_hash = hashlib.sha256((current / 'launch.py').read_bytes()).hexdigest()
        shortcut_hash = hashlib.sha256(canonical.read_bytes()).hexdigest()
        broken = broken_installer(scratch, version)
        run_install(broken, root, expected=1)
        assert hashlib.sha256((current / 'launch.py').read_bytes()).hexdigest() == current_hash
        assert hashlib.sha256(canonical.read_bytes()).hexdigest() == shortcut_hash
        assert active_data.read_bytes() == b'live-evidence'
        assert not list(root.glob('.staging-*')) and not list(root.glob('.previous-*'))
        running = subprocess.Popen([str(current / 'runtime/python.exe'), '-c', 'import time; time.sleep(60)'])
        try:
            time.sleep(0.5)
            run_install(installer, root, expected=1)
            assert running.poll() is None
            assert hashlib.sha256(canonical.read_bytes()).hexdigest() == shortcut_hash
        finally:
            running.terminate()
            running.wait(timeout=10)
        run_install(installer, root)
        assert active_data.read_bytes() == b'live-evidence'
        assert not list(root.glob('.staging-*')) and not list(root.glob('.previous-*'))
        assert len(list(desktop.glob('惠安麻将测试版-*.lnk'))) == 1
        assert (unrelated / 'keep.txt').read_text() == 'keep'
        print('UPGRADE_OK: legacy data, fixed entry, repeated install, failed doctor, running-app refusal, data conflict')


if __name__ == '__main__':
    main()
