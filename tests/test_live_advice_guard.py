import unittest
from workspace.hint_alpha.live_guard import LiveAdviceGuard


class LiveGuardTests(unittest.TestCase):
    def test_stop_black_frame_or_error_rejects_inflight_result(self):
        guard = LiveAdviceGuard()
        guard.observe(1, 10)
        epoch = guard.generation
        guard.invalidate()
        guard.observe(2, 11)
        self.assertFalse(guard.accepts(epoch, 10, 11))
        self.assertTrue(guard.accepts(guard.generation, 11, 11.1))

    def test_stale_and_out_of_order_results_rejected(self):
        guard = LiveAdviceGuard()
        guard.observe(1, 10)
        self.assertFalse(guard.accepts(0, 10, 13))
        guard.last_result = 10
        self.assertFalse(guard.accepts(0, 10, 11))
        guard.observe(2, 12)
        self.assertTrue(guard.stale(12.1))  # old advice despite fresh capture

    def test_sequence_restart_creates_new_epoch(self):
        guard = LiveAdviceGuard()
        guard.observe(5, 10)
        guard.observe(1, 11)
        self.assertEqual(guard.generation, 1)
        self.assertFalse(guard.accepts(0, 10, 11))
        self.assertTrue(guard.accepts(1, 11, 11.1))

    def test_invalid_time_cannot_enable_advice(self):
        guard = LiveAdviceGuard()
        self.assertFalse(guard.observe(1, float('nan')))
        self.assertFalse(guard.accepts(guard.generation, 1, 1))
