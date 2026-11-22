"""Run against an extracted installer using its bundled Python, without capture."""
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import cv2
import numpy as np

root = Path(sys.argv[1]).resolve()
site = root / 'runtime/Lib/site-packages'
manifest = json.loads((root / 'BUILD_INFO.json').read_text(encoding='utf-8'))
assert hashlib.sha256((root / 'TEST_RELEASE_NOTES.txt').read_bytes()).hexdigest() == manifest['testing_release_notes_sha256']
assert '.'.join(map(str, sys.version_info[:3])) == manifest['python_version']
for name, version in manifest['dependency_versions'].items():
    assert importlib.metadata.version(name) == version, name
for relative, expected in manifest['source_sha256'].items():
    assert hashlib.sha256((site / relative).read_bytes()).hexdigest() == expected, relative
dataset = site / 'dataset/tiles_runtime_v0_2'
for relative, expected in manifest['template_sha256'].items():
    assert hashlib.sha256((dataset / relative).read_bytes()).hexdigest() == expected, relative

from workspace.hint_alpha import app, live_app
from workspace.hint_alpha.video_test import ReplayOCRCache, _runtime_environment, iter_video_samples
from workspace.hint_alpha.manual_input import evaluate_manual_input
from workspace.hint_alpha.runtime_pipeline import evaluate_runtime_report
from workspace.vision.tiles_v0_1.labels import approved_labels
from workspace.vision.tiles_v0_1.template_classifier import TemplateTileClassifier

build = _runtime_environment()
assert build['installer_commit'] == manifest['commit']
assert build['bundled_reference_version'] == manifest['reference_pack_version']
from numpy import array, uint8
crop = array([[1, 2]], dtype=uint8)
cache = ReplayOCRCache(lambda image: str(image[0, 1]))
assert cache(crop) == cache(crop.copy()) == '2'
assert (cache.hits, cache.misses) == (1, 1)

# Verify the replay entry points and the score short circuit from installed modules.
from PIL import Image
from workspace.hint_alpha import replay_compare, video_cli
from workspace.vision.tiles_v0_1.public_state_scores import read_score_pair

assert Path(replay_compare.__file__).resolve().is_relative_to(site)
assert Path(video_cli.__file__).resolve().is_relative_to(site)
diagnostics = root / "diagnostics"
draw_manifest = json.loads((diagnostics / "draw_opportunity_inventory.development.json").read_text(encoding="utf-8"))
review_manifest = json.loads((diagnostics / "dense_replay_reviewed_gains.development.json").read_text(encoding="utf-8"))
assert len(draw_manifest["episodes"]) - len(draw_manifest["flower_episode_indices"]) == 15
assert sum(len(source["frames"]) for source in review_manifest["sources"]) == 15
assert draw_manifest["development_only"] and review_manifest["development_only"]

texts = iter(("1077", "1077", "923", "923"))
score = read_score_pair(Image.new("RGB", (1000, 500)), backend=lambda _: next(texts),
                        stop_on_score_majority=True)
assert score.score_pair == (1077, 923) and score.mode == "direct"
assert len(score.top_attempts) == len(score.bottom_attempts) == 2


assert importlib.util.find_spec('pip') is None
assert importlib.util.find_spec('ensurepip') is None
assert not (site / 'PyWin32.chm').exists()
with TemporaryDirectory() as temporary:
    video = str(Path(temporary) / 'replay-smoke.avi')
    writer = cv2.VideoWriter(video, cv2.CAP_FFMPEG, cv2.VideoWriter_fourcc(*'MJPG'),
                             10.0, (64, 64))
    try:
        assert writer.isOpened(), 'Packaged FFmpeg video writer did not open'
        for value in (40, 100, 160):
            writer.write(np.full((64, 64, 3), value, dtype=np.uint8))
    finally:
        writer.release()
    samples = list(iter_video_samples(video, sample_interval_seconds=0.1))
    assert [sample[0] for sample in samples] == [0, 1, 2]
    assert all(image.size == (64, 64) and image.mode == 'RGB' for _, _, image in samples)

assert Path(app.__file__).resolve().is_relative_to(site)
assert Path(live_app.__file__).resolve().is_relative_to(site)
assert Path(app.PROJECT_ROOT) == site
labels = approved_labels(dataset)
TemplateTileClassifier.from_labels(dataset, labels)
hand = ['M1'] * 3 + ['P1'] * 3 + ['S1'] * 3 + ['E'] * 3 + ['R'] * 3 + ['B', 'N']
snapshot, hint = evaluate_manual_input(session_id='packaged-smoke', revision=0,
    captured=1.0, hand=hand, gold_tile='W', own_meld_count=0)
assert hint.allowed and hint.shanten == 0
assert {item.discard for item in hint.best_discards} == {'B', 'N'}
assert hint.safe_for_executor is False
unknown = evaluate_runtime_report(dict(session='smoke', stream_epoch=0,
    frames=[1, 2, 3], components=[], geometry_untrusted=True), captured=1, experimental=True)
assert not unknown.display_allowed and not unknown.safe_for_executor
app.OUTPUT = root / 'data/hint_alpha'
window = live_app.LiveHintAlphaApp(demo=True, experimental_runtime_advisory=True)
assert window.public_reader.stop_on_score_majority
assert window.runtime_advice_pipeline is not None
assert '暂无' in window.hint_latency.get()
assert '等待' in window.blocked_detail.get()
from workspace.hint_alpha.bundled_references import resolve_bundled_references
from workspace.vision.tiles_runtime_v0_2.experimental_hand_translation import with_private_hand_packet
from workspace.vision.tiles_runtime_v0_2.runtime_reader import prepare_runtime_resources
reference_path, reference_version, reference_count = resolve_bundled_references(site)
assert window.experimental_hand_packet == reference_path
assert reference_count == manifest['reference_pack_count']
assert reference_version == manifest['reference_pack_version']
assert '校验通过' in window.reference_pack_status.get()
reference_resources = with_private_hand_packet(prepare_runtime_resources(dataset, 'installed-assets-smoke'), reference_path)
assert len(reference_resources['classifier'].extra_features) == 20
assert reference_resources['classifier'].opened_gold_reference_count == 7
assert len(reference_resources['training_labels']) == 137
assert reference_resources['experimental_training_review']['removed_training_labels'] == 10
from workspace.vision.tiles_runtime_v0_2.concealed_gold_references import ConcealedGoldReferenceClassifier
concealed = reference_resources['classifier'].ordinary
assert isinstance(concealed, ConcealedGoldReferenceClassifier)
assert len(concealed.references) == 1
assert len(reference_resources['classifier'].extra_features) + reference_resources['classifier'].opened_gold_reference_count + len(concealed.references) == reference_count
from workspace.vision.capture_validator.auto_recorder import TemplatePhaseDetector
phase_detector = TemplatePhaseDetector.from_project_evidence(site)
assert sum(len(v) for v in phase_detector.templates.values()) == 6
window.withdraw()
window.update()
window.open_assistant()
assistant = window.assistant_window
window.open_assistant()
assert window.assistant_window is assistant
assert '未知' in window.simple_hint.get()
window.open_diagnostics()
window.update()
assert window.notebook.tab(0, 'text') == '实时流水'
diagnostic = window.diagnostics_window
assert diagnostic.winfo_exists()
window.open_diagnostics()
assert window.diagnostics_window is diagnostic
window._copy_diagnostics()
assert window.capture_status.get() in window.clipboard_get()
assert window.version_status.get() in window.clipboard_get()
diagnostic.destroy()
window.geometry('1040x620')
window.deiconify()
window.update()
assert window.winfo_ismapped()
window.notebook.select(window.diagnostic_tab)
window.update()
assert window.canvas.winfo_width() > 300
assert window.canvas.winfo_height() > 150
window.notebook.select(window.video_test_tab)
window.update()
assert window.video_test_canvas.winfo_width() > 300
assert window.video_timeline_text.winfo_height() > 40
window.notebook.select(window.realtime_tab)
window.withdraw()

window._start_evidence()
window._append_timeline('system', 'INSTALL_SMOKE', key=('install-smoke', 1))
window.update()
assert 'INSTALL_SMOKE' in window.timeline_text.get('1.0', 'end')
window.open_manual_hand()
window.update()
window.close()
print(json.dumps({'source_files_verified': len(manifest['source_sha256']),
    'templates_verified': len(manifest['template_sha256']),
    'reference_version': reference_version, 'references_loaded': reference_count, 'phase_images_loaded': 6, 'shanten': hint.shanten,
    'discard_candidates': [item.discard for item in hint.best_discards],
    'unknown_abstention': True, 'live_entrypoint': True,
    'ui': 'PASS', 'executor_enabled': False}))
