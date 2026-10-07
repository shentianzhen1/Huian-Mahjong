"""Live-only identity confirmation must never fill an unknown current hand."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import queue
import unittest
from unittest.mock import Mock, patch

from tests.test_live_opening_tracker import runtime_report
from workspace.hint_alpha.live_snapshot_stability import LiveSnapshotStability
from workspace.hint_alpha.runtime_pipeline import RuntimeAdvicePipeline, evaluate_runtime_report
from workspace.hint_alpha.live_guard import LiveAdviceGuard
from workspace.vision.runtime_public_adapter import current_snapshot_from_runtime

try:
    from workspace.hint_alpha.live_app import LiveHintAlphaApp
except ImportError:
    LiveHintAlphaApp = None


def burst(frame=3, **changes):
    return runtime_report(frames=(frame - 2, frame - 1, frame), **changes)


class LiveSnapshotStabilityTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = RuntimeAdvicePipeline(stability_tracker=LiveSnapshotStability())

    def evaluate(self, report, captured):
        return self.pipeline.evaluate(report, captured=captured, experimental=True)

    def test_same_hand_needs_two_distinct_identity_frames(self):
        first = self.evaluate(burst(), 1)
        self.assertFalse(first.display_allowed)
        self.assertIn('live_hand_meld_waiting_confirmation', first.hint.issues)
        second = self.evaluate(burst(6), 1.8)
        self.assertTrue(second.display_allowed)
        self.assertFalse(second.safe_for_executor)

    def test_overlapping_bursts_reusing_identity_frame_cannot_add_vote(self):
        self.evaluate(burst(), 1)
        repeated = burst()
        repeated['frames'] = [2, 3, 4]
        blocked = self.evaluate(repeated, 1.2)
        self.assertFalse(blocked.display_allowed)
        self.assertIn('live_identity_frame_repeated', blocked.hint.issues)
        self.assertTrue(self.evaluate(burst(6), 1.8).display_allowed)

    def test_changed_hand_blocks_immediately_without_carrying_old_hand(self):
        self.evaluate(burst(), 1)
        self.evaluate(burst(6), 1.8)
        changed = burst(9)
        changed['components'][0]['tile_id'] = 'P9'
        blocked = self.evaluate(changed, 2.6)
        self.assertFalse(blocked.display_allowed)
        self.assertEqual(blocked.snapshot.own_hand[0], 'P9')
        confirmed = deepcopy(changed)
        confirmed['frames'] = [10, 11, 12]
        for item in confirmed['components']:
            item['frame'] = 12
        confirmed['gold_identity_observations'] = burst(12)['gold_identity_observations']
        self.assertTrue(self.evaluate(confirmed, 3.4).display_allowed)

    def test_unknown_breaks_streak_and_recovery_needs_fresh_confirmation(self):
        self.evaluate(burst(), 1)
        self.evaluate(burst(6), 1.8)
        unknown = burst(9)
        unknown['components'][0]['tile_id'] = 'UNKNOWN'
        unknown['all_concealed_tile_ids_trusted'] = False
        self.assertFalse(self.evaluate(unknown, 2.6).display_allowed)
        self.assertFalse(self.evaluate(burst(12), 3.4).display_allowed)
        self.assertTrue(self.evaluate(burst(15), 4.2).display_allowed)

    def test_source_epoch_gap_and_reset_forget_votes(self):
        for kind in ('source', 'epoch', 'gap', 'reset'):
            with self.subTest(kind=kind):
                self.setUp()
                self.evaluate(burst(), 1)
                self.evaluate(burst(6), 1.8)
                changes = {'session': 'new'} if kind == 'source' else {'epoch': 1} if kind == 'epoch' else {}
                if kind == 'reset':
                    self.pipeline.reset()
                self.assertFalse(self.evaluate(burst(9, **changes), 5 if kind == 'gap' else 2.6).display_allowed)

    def test_invalid_identity_scope_and_time_fail_closed(self):
        for kind in ('missing', 'mixed', 'outside', 'nan', 'regression'):
            with self.subTest(kind=kind):
                self.setUp()
                self.evaluate(burst(), 1)
                candidate = burst(6)
                captured = 1.8
                if kind == 'missing':
                    candidate['components'][0].pop('frame')
                elif kind == 'mixed':
                    candidate['components'][0]['frame'] = 5
                elif kind == 'outside':
                    candidate['frames'] = [7, 8, 9]
                    candidate['gold_identity_observations'] = burst(9)['gold_identity_observations']
                elif kind == 'nan':
                    captured = float('nan')
                else:
                    captured = 0.5
                self.assertFalse(self.evaluate(candidate, captured).display_allowed)

    def test_meld_structure_count_only_can_confirm_without_inventing_identity(self):
        def own_meld_report(frame):
            r = burst(frame)
            r['components'] = [*r['components'][3:16], r['components'][-1]]
            r['concealed_tile_count'] = 13
            for index in range(3):
                r['components'].append(dict(region_candidate='meld', tile_id='UNKNOWN',
                    normalized_bbox=[0.10 + index * 0.04, 0.80, 0.035, 0.10],
                    confidence=0.95, frame=frame, identity_reason='region_not_classified'))
            return r
        self.assertFalse(self.evaluate(own_meld_report(3), 1).display_allowed)
        ready = self.evaluate(own_meld_report(6), 1.8)
        self.assertTrue(ready.display_allowed)
        self.assertEqual(ready.snapshot.melds[0], ((None, None, None),))
        self.assertFalse(ready.hint.visible_remainders_used)

    def test_stateless_replay_boundary_is_unchanged_and_bind_is_scoped(self):
        self.assertTrue(evaluate_runtime_report(burst(), captured=1, experimental=True).display_allowed)
        with self.pipeline.bind():
            self.assertFalse(evaluate_runtime_report(burst(), captured=1, experimental=True).display_allowed)
            self.assertTrue(evaluate_runtime_report(burst(6), captured=1.8, experimental=True).display_allowed)
        self.assertTrue(evaluate_runtime_report(burst(), captured=1, experimental=True).display_allowed)

    def test_invalid_configuration_is_rejected(self):
        for kwargs in ({'minimum_observations': 1}, {'minimum_observations': True},
                       {'max_gap_seconds': float('inf')}, {'max_gap_seconds': 0}):
            with self.assertRaises(ValueError):
                LiveSnapshotStability(**kwargs)

    @unittest.skipIf(LiveHintAlphaApp is None, 'optional UI/Vision dependencies unavailable')
    def test_live_ui_consumer_uses_confirmation_gate(self):
        app = LiveHintAlphaApp.__new__(LiveHintAlphaApp)
        app.runtime_advice_pipeline = self.pipeline
        app.live_guard = LiveAdviceGuard()
        app.evidence = SimpleNamespace(session_id='runtime-live', mark=Mock())
        app.runtime_result_queue = queue.Queue()
        app.runtime_status = app.hint_status = Mock()
        app.experimental_runtime_advisory = True
        app._update_snapshot_view = Mock()
        app.source = {}
        app.last_runtime_event_key = None
        for frame, captured, allowed in ((3, 1, False), (6, 1.8, True)):
            app.live_guard.observe(frame, captured)
            app.runtime_result_queue.put(('ok', 'runtime-live', 0, captured, burst(frame)))
            with patch('workspace.hint_alpha.app.time.monotonic', return_value=captured):
                app._consume_runtime_result()
            payload = app.evidence.mark.call_args.args[1]
            self.assertEqual(payload['display_allowed'], allowed)
            self.assertEqual(payload['runtime_frames'][-1], frame)
            self.assertIn('melds', payload)
            self.assertFalse(payload['safe_for_executor'])

    @unittest.skipIf(LiveHintAlphaApp is None, 'optional UI/Vision dependencies unavailable')
    def test_meld_display_distinguishes_count_from_identity(self):
        from workspace.hint_alpha.app import HintAlphaApp
        snapshot = current_snapshot_from_runtime(burst(), timestamp_seconds=1)
        unknown = replace(snapshot, melds=(((None, None, None),), ()))
        self.assertIn('牌面未确认', HintAlphaApp._format_own_melds(unknown))
        known = replace(snapshot, melds=((('P6', 'P6', 'P6'),), ()))
        self.assertIn('六筒', HintAlphaApp._format_own_melds(known))
