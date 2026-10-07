"""Run against an extracted installer using its bundled Python, without capture."""
import hashlib
import json
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
site = root / 'runtime/Lib/site-packages'
manifest = json.loads((root / 'BUILD_INFO.json').read_text(encoding='utf-8'))
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
window.withdraw()
window.update()
window.open_assistant()
assistant = window.assistant_window
window.open_assistant()
assert window.assistant_window is assistant
assert '未知' in window.simple_hint.get()
window.open_diagnostics()
window.update()
assert window.pages.tab(1, 'text') == '实时对局流水'
window._start_evidence()
window._update_timeline()
assert len(window.timeline_table.get_children()) >= 2
window.open_manual_hand()
window.update()
window.close()
print(json.dumps({'source_files_verified': len(manifest['source_sha256']),
    'templates_verified': len(manifest['template_sha256']), 'shanten': hint.shanten,
    'discard_candidates': [item.discard for item in hint.best_discards],
    'unknown_abstention': True, 'live_entrypoint': True,
    'ui': 'PASS', 'executor_enabled': False}))
