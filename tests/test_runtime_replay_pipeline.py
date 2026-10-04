import unittest
from dataclasses import asdict
import json
from pathlib import Path
from workspace.hint_alpha.runtime_pipeline import evaluate_runtime_report
from workspace.hint_alpha.live_guard import LiveAdviceGuard


def trusted_report():
    # Synthetic contract fixture; this is not pixel/real-video acceptance evidence.
    hand = ['M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'M7', 'M8', 'M9',
            'P1', 'P2', 'P3', 'S1', 'S2', 'S3', 'E']
    components = [dict(region_candidate='hand', tile_id=t, confidence=.95,
                       identity_reason='accepted') for t in hand]
    components.append(dict(region_candidate='gold', tile_id='B', confidence=.95,
                           identity_reason='accepted'))
    return dict(session='synthetic-contract', stream_epoch=0, frames=[1, 2, 3],
                geometry_untrusted=False, components=components,
                concealed_tile_count=16, all_concealed_tile_ids_trusted=True,
                safe_for_hint=False, safe_for_executor=False)


class ReplayPipelineTests(unittest.TestCase):
    def test_frozen_real_snapshot_decisions_recompute_without_private_pixels(self):
        from workspace.vision.current_state_snapshot import CurrentTableSnapshot
        from workspace.hint_alpha.current_snapshot_advisor import analyze_snapshot_shanten
        from workspace.hint_alpha.replay_smoke import summarize_windows
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads((root / 'references/vision/2026-10-04/'
                               'alpha_continuous_real_recovery_v0_1.json').read_text())
        # This checks saved snapshot semantics; CI does not have private pixels.
        self.assertFalse(evidence['formal_promotion_evidence'])
        self.assertFalse(evidence['windows_capture_validated'])
        self.assertEqual(evidence['session_binding'], 'explicit_original_session')
        for row in evidence['rows']:
            hint = analyze_snapshot_shanten(CurrentTableSnapshot(**row['snapshot']))
            self.assertEqual(json.loads(json.dumps(asdict(hint))), row['hint'])
            self.assertEqual(hint.allowed, row['display_allowed'])
            self.assertFalse(hint.visible_remainders_used)
            self.assertFalse(hint.safe_for_executor)
        summary = summarize_windows(evidence['rows'])
        self.assertEqual(summary['advice_runs'], evidence['advice_runs'])
        self.assertEqual(summary['recovered_advice_runs'], 1)

    def test_frozen_real_discard_windows_remain_structural_and_read_only(self):
        from workspace.vision.current_state_snapshot import CurrentTableSnapshot
        from workspace.hint_alpha.current_snapshot_advisor import analyze_snapshot_shanten
        from workspace.hint_alpha.replay_smoke import summarize_windows
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads((root / 'references/vision/2026-10-04/'
                               'alpha_real_discard_160_164_v0_1.json').read_text())
        self.assertTrue(evidence['development_only'])
        self.assertFalse(evidence['formal_promotion_evidence'])
        self.assertFalse(evidence['discard_strategy_quality_measured'])
        self.assertEqual(evidence['session_binding'], 'explicit_original_session')
        self.assertEqual(evidence['identity_threshold'], .82)
        self.assertEqual(evidence['original_match_count'], 1)
        self.assertEqual((evidence['accepted_windows'], evidence['blocked_windows'],
                          evidence['discard_windows']), (8, 4, 2))
        candidates = []
        for row in evidence['rows']:
            hint = analyze_snapshot_shanten(CurrentTableSnapshot(**row['snapshot']))
            self.assertEqual(json.loads(json.dumps(asdict(hint))), row['hint'])
            self.assertEqual(hint.allowed, row['display_allowed'])
            self.assertFalse(hint.visible_remainders_used)
            self.assertFalse(hint.safe_for_executor)
            if hint.phase == 'POST_DRAW' and row['display_allowed']:
                candidates.append((row['frames'][-1],
                                   [item.discard for item in hint.best_discards]))
        self.assertEqual(candidates, [(9608, ['M3', 'P5', 'P7', 'P9']),
                                      (9626, ['M3', 'P5', 'P7', 'P9'])])
        self.assertEqual(summarize_windows(evidence['rows'])['advice_runs'],
                         evidence['advice_runs'])


    def test_replay_summary_distinguishes_first_acquisition_and_recovery(self):
        from workspace.hint_alpha.replay_smoke import summarize_windows
        rows = [dict(display_allowed=allowed, frames=[n, n + 1, n + 2],
                     source_seconds=[n / 10, (n + 1) / 10, (n + 2) / 10],
                     hint={'issues': [] if allowed else ['gold_untrusted']})
                for n, allowed in enumerate([False, True, True, False, True])]
        result = summarize_windows(rows)
        self.assertEqual(result['recovered_advice_runs'], 1)
        self.assertEqual([r['windows'] for r in result['advice_runs']], [1, 2, 1, 1])
        self.assertEqual(result['rejection_issue_windows'], {'gold_untrusted': 2})
        self.assertEqual(summarize_windows(rows[:3])['recovered_advice_runs'], 0)
        self.assertEqual(summarize_windows(rows[:1])['recovered_advice_runs'], 0)
        self.assertEqual(summarize_windows([])['advice_runs'], [])

    def test_default_gate_and_experimental_structural_advice(self):
        report = trusted_report()
        default = evaluate_runtime_report(report, captured=1)
        self.assertTrue(default.hint.allowed)
        self.assertFalse(default.display_allowed)
        experimental = evaluate_runtime_report(report, captured=1, experimental=True)
        self.assertTrue(experimental.display_allowed)
        self.assertFalse(experimental.hint.visible_remainders_used)
        self.assertFalse(experimental.safe_for_executor)

    def test_discard_windows_require_actual_post_draw_choices(self):
        report = trusted_report()
        report['components'].insert(-1, dict(region_candidate='draw_visual',
                                             tile_id='P4', confidence=.95,
                                             identity_reason='accepted'))
        report['concealed_tile_count'] = 17
        advisory = evaluate_runtime_report(report, captured=1, experimental=True)
        self.assertEqual(advisory.hint.phase, 'POST_DRAW')
        self.assertTrue(advisory.hint.best_discards)
        self.assertTrue(advisory.display_allowed)

    def test_unknown_then_recovered_current_snapshot_has_no_sticky_pollution(self):
        report = trusted_report()
        report['components'][0]['tile_id'] = 'UNKNOWN'
        report['all_concealed_tile_ids_trusted'] = False
        blocked = evaluate_runtime_report(report, captured=1, experimental=True)
        self.assertFalse(blocked.display_allowed)
        recovered = evaluate_runtime_report(trusted_report(), captured=2, experimental=True)
        self.assertTrue(recovered.display_allowed)
        self.assertEqual(recovered.snapshot.timestamp_seconds, 2)

    def test_black_or_disconnect_epoch_rejects_old_result_before_recovery(self):
        guard = LiveAdviceGuard()
        guard.observe(1, 1)
        old = guard.generation
        guard.invalidate()
        guard.observe(2, 2)
        self.assertFalse(guard.accepts(old, 1, 2))
        self.assertTrue(guard.accepts(guard.generation, 2, 2.1))

    def test_real_burst_rejects_repeated_source_indices(self):
        from workspace.hint_alpha.replay_smoke import evaluate_burst
        with self.assertRaises(ValueError):
            evaluate_burst([(1, 1, None)] * 3, session='s', dataset_root='unused')

    def test_sparse_pixels_do_not_enable_temporal_advice(self):
        from workspace.hint_alpha.replay_smoke import evaluate_burst
        class Pixels:
            def tobytes(self):
                return b'contract-fixture'
        called = []
        def reader(images, root, **options):
            called.append(options)
            return trusted_report()
        result = evaluate_burst([(1, 1, Pixels()), (2, 2, Pixels()), (3, 3, Pixels())],
                                session='s', dataset_root='unused', reader=reader)
        self.assertFalse(result['display_allowed'])
        self.assertTrue(result['sparse_source_burst'])
        self.assertEqual(called[0]['confidence_threshold'], .82)
