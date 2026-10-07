"""Rejected display observations must not move the trusted Gold boundary."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

try:
    from workspace.hint_alpha.app import HintAlphaApp
    from workspace.hint_alpha.live_app import LiveHintAlphaApp
except ImportError:
    LiveHintAlphaApp = None


@unittest.skipIf(LiveHintAlphaApp is None, 'optional UI/Vision dependencies unavailable')
class LiveGoldUIBoundaryTests(unittest.TestCase):
    def test_rejected_display_sequence_cannot_authorize_gold_reset(self):
        for sequence in ((3, 2, 3), (3, 5, 6), (3, 4, 4)):
            with self.subTest(sequence=sequence):
                app = LiveHintAlphaApp.__new__(LiveHintAlphaApp)
                app.runtime_advice_pipeline = Mock()
                app._gold_hand_number = None
                app.timeline_hand = None

                def display(observation):
                    app.timeline_hand = observation.hand_number

                with patch.object(HintAlphaApp, '_update_public_view', side_effect=display):
                    for hand in sequence:
                        app._update_public_view(SimpleNamespace(hand_number=hand, hand_votes=2))
                expected = 2 if sequence == (3, 4, 4) else 1
                self.assertEqual(app.runtime_advice_pipeline.reset.call_count, expected)
                self.assertEqual(app._gold_hand_number, 4 if expected == 2 else 3)

    def test_capture_invalidation_clears_trusted_hand_boundary(self):
        app = LiveHintAlphaApp.__new__(LiveHintAlphaApp)
        app.runtime_advice_pipeline = Mock()
        app._gold_hand_number = 8
        with patch.object(HintAlphaApp, '_invalidate_advice'):
            app._invalidate_advice('capture stopped')
        app.runtime_advice_pipeline.reset.assert_called_once()
        self.assertIsNone(app._gold_hand_number)
