import unittest
from workspace.hint_alpha.user_guidance import blocked_guidance, capture_to_hint_text


class UserGuidanceTests(unittest.TestCase):
    def test_blocked_reasons_are_actionable_and_unknown_remains_unknown(self):
        self.assertIn('手动选金牌', blocked_guidance(['gold_identity_unknown']))
        self.assertIn('手牌未识别完整', blocked_guidance(['hand_identity_unknown']))
        self.assertIn('副露数量', blocked_guidance(['player_meld_count_untrusted']))
        self.assertIn('正在确认', blocked_guidance(['live_hand_meld_waiting_confirmation', 'hand_untrusted']))
        self.assertIn('位置尚未稳定', blocked_guidance([], geometry_untrusted=True))
        self.assertIn('试用识别', blocked_guidance([], promotion_blocked=True))
        self.assertIn('尚未确认', blocked_guidance(['unrecognized_reason']))

    def test_latency_is_for_displayed_current_result_only(self):
        self.assertIn('250 毫秒', capture_to_hint_text(10.0, 10.25, displayed=True))
        for captured, updated, displayed in [(10., 10.25, False), (10., 9., True), (float('nan'), 10., True)]:
            self.assertIn('暂无', capture_to_hint_text(captured, updated, displayed=displayed))
