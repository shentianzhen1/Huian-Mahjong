"""Run against an extracted installer using its bundled Python, without capture."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

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
from workspace.hint_alpha.manual_input import evaluate_manual_input
from workspace.hint_alpha.runtime_pipeline import evaluate_runtime_report
from workspace.vision.tiles_v0_1.labels import approved_labels
from workspace.vision.tiles_v0_1.template_classifier import TemplateTileClassifier

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
assert len(reference_resources['classifier'].extra_features) == 16
assert reference_resources['classifier'].opened_gold_reference_count == 3
assert len(reference_resources['training_labels']) == 137
assert reference_resources['experimental_training_review']['removed_training_labels'] == 10
assert len(reference_resources['classifier'].extra_features) + reference_resources['classifier'].opened_gold_reference_count == reference_count
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
