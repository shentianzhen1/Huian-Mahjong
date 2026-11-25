import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from workspace.hint_alpha.live_timeline import EvidenceTail, event_row


class LiveTimelineTests(unittest.TestCase):
    def test_candidates_do_not_become_actions_or_confirmed_evidence(self):
        row = event_row({'kind': 'CURRENT_SNAPSHOT_HINT', 'payload': {
            'display_allowed': True, 'hand': ['M1'], 'gold_tile': 'P2',
            'shanten': 0, 'best_discards': [{'tile': 'M1'}]}})
        self.assertEqual(row[2], '未知')
        self.assertIn('非确认动作', row[5])
        self.assertIn('动作=未知', row[6])
        self.assertEqual(row[4], 'P2')

    def test_blocked_snapshot_hides_candidate_hand_and_shanten(self):
        row = event_row({'kind': 'CURRENT_SNAPSHOT_HINT', 'payload': {
            'display_allowed': False, 'hand': ['M1'], 'gold_tile': 'P2', 'shanten': 0}})
        self.assertEqual(row[4], '未知')
        self.assertNotIn('M1', row[6])
        self.assertIn('向听=未知', row[6])

    def test_invalid_score_or_issue_never_shown_as_valid(self):
        for observation in ({'score_pair': [1100, 1000]},
                            {'score_pair': [1100, 900], 'issues': ['low_confidence']}):
            row = event_row({'kind': 'PUBLIC_STATE', 'payload': {'observation': observation}})
            self.assertIn('比分=未知', row[6])

    def test_rejected_public_read_is_unknown_in_live_timeline(self):
        row = event_row({'kind': 'PUBLIC_STATE', 'payload': {
            'accepted_for_live_view': False,
            'observation': {'hand_number': 5, 'score_pair': [1100, 900],
                            'remaining_tiles': 80}}})
        self.assertEqual(row[1], '未知')
        self.assertIn('比分=未知；余牌=未知', row[6])
        self.assertIn('局号尚未确认', row[6])

    def test_expired_public_read_shows_expiry_reason(self):
        row = event_row({'kind': 'PUBLIC_STATE', 'payload': {
            'accepted_for_live_view': False,
            'live_view_rejection_reason': 'OCR 结果已过期',
            'observation': {'hand_number': 3, 'remaining_tiles': 105}}})
        self.assertEqual(row[1], '未知')
        self.assertIn('余牌=未知', row[6])
        self.assertIn('OCR 结果已过期', row[6])

    def test_runtime_timeout_shows_capture_age_and_source_frame(self):
        row = event_row({'kind': 'RUNTIME_RESULT_TOO_OLD',
                         'source': {'sequence': 25}, 'payload': {
                             'runtime_elapsed_seconds': None,
                             'capture_age_seconds': 2.205,
                         }})
        self.assertEqual(row[5], '超时丢弃')
        self.assertEqual(row[6], '来源帧 25；牌面计算 未知；采集到界面接收 2205 毫秒')

    def test_tail_partial_writes_no_duplicates_and_session_reset(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'events.jsonl'
            event = json.dumps({'kind': 'CAPTURE_STARTED'}).encode()
            path.write_bytes(event[:10])
            tail = EvidenceTail()
            self.assertEqual(tail.read(path), [])
            with path.open('ab') as stream:
                stream.write(event[10:] + b'\n')
            self.assertEqual(len(tail.read(path)), 1)
            self.assertEqual(tail.read(path), [])
            second = Path(folder) / 'next.jsonl'
            second.write_bytes(event + b'\n')
            self.assertEqual(len(tail.read(second)), 1)

    def test_missing_and_manual_settlement_remain_unverified(self):
        row = event_row({'kind': 'MANUAL_SCORE_INPUT', 'payload': {'score_delta': [10, -10]}})
        self.assertEqual(row[1:3], ('未知', '未知'))
        self.assertEqual(row[5], '未验证观察')
