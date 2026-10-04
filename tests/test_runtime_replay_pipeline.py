import unittest
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
    def test_default_gate_and_experimental_structural_advice(self):
        report = trusted_report()
        default = evaluate_runtime_report(report, captured=1)
        self.assertTrue(default.hint.allowed)
        self.assertFalse(default.display_allowed)
        experimental = evaluate_runtime_report(report, captured=1, experimental=True)
        self.assertTrue(experimental.display_allowed)
        self.assertFalse(experimental.hint.visible_remainders_used)
        self.assertFalse(experimental.safe_for_executor)

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
