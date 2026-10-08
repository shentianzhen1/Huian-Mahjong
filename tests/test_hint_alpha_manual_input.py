"""Manual observations are product input, not Vision or rule confirmation."""
import unittest
from dataclasses import asdict
import json
from tempfile import TemporaryDirectory

from huian._legacy import env
from workspace.hint_alpha.evidence import EvidenceSession
from workspace.hint_alpha.manual_input import evaluate_manual_input, observed_score_entry
from workspace.vision.current_state_snapshot import (
    CurrentTableSnapshot, SnapshotCapability, assess_current_snapshot,
)


HAND = ('M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'M7', 'M8', 'M9',
        'P1', 'P2', 'P3', 'S1', 'S2', 'S3', 'E')
UNRESOLVED_SETTLEMENT = 'settlement.youjin_full'


class ManualInputTests(unittest.TestCase):
    def snapshot(self, **overrides):
        values = dict(session_id='owner-entry-1', revision=0, captured=1.0,
                      hand=HAND, gold_tile='B', own_meld_count=0)
        values.update(overrides)
        return evaluate_manual_input(**values)

    def test_manual_complete_hand_enables_only_structural_shanten(self):
        snap, hint = self.snapshot()
        cap = assess_current_snapshot(snap)
        self.assertEqual(snap.input_source, 'user_entered')
        self.assertEqual(snap.stable_frames, 0)
        self.assertEqual(snap.source_session, 'manual:owner-entry-1')
        self.assertEqual(cap.capabilities, (SnapshotCapability.SHANTEN,))
        self.assertEqual(hint.status, 'PARTIAL')
        self.assertTrue(hint.allowed)
        self.assertFalse(hint.visible_remainders_used)
        self.assertFalse(hint.safe_for_executor)
        self.assertIn('user_entered_unverified', hint.issues)

    def test_manual_post_draw_reuses_discard_gate_without_public_risk(self):
        snap, hint = self.snapshot(hand=(*HAND, 'P4'), revision=1)
        self.assertEqual(snap.stream_epoch, 1)
        self.assertEqual(hint.phase, 'POST_DRAW')
        self.assertTrue(hint.best_discards)
        self.assertTrue(all(item.total_live_copies is None for item in hint.best_discards))

    def test_unknown_or_inconsistent_input_blocks_without_sticky_state(self):
        for overrides, issue in (
            ({'hand': (*HAND[:-1], None)}, 'hand_identity_unknown'),
            ({'gold_tile': None}, 'gold_identity_unknown'),
            ({'hand': (*HAND[:-1],)}, 'concealed_hand_count_invalid'),
            ({'gold_tile': 'M1', 'hand': ('M1',) * 4 + HAND[4:]},
             'playable_gold_copy_overflow'),
            ({'hand': ('M1',) * 5 + HAND[5:]}, 'physical_copy_overflow:M1'),
        ):
            with self.subTest(issue=issue):
                _, result = self.snapshot(**overrides)
                self.assertFalse(result.allowed)
                self.assertIn(issue, result.issues)
                self.assertFalse(result.safe_for_executor)
        _, recovered = self.snapshot(revision=2)
        self.assertTrue(recovered.allowed)

    def test_manual_meld_count_has_unknown_identity_not_fake_legal_group(self):
        hand = ('M6', 'M6', 'P3', 'P4', 'P5', 'P5', 'P7', 'P7', 'P9', 'P9')
        snap, hint = self.snapshot(hand=hand, gold_tile='M6', own_meld_count=2)
        self.assertTrue(hint.allowed)
        self.assertEqual(len(snap.melds[0]), 2)
        self.assertEqual(snap.melds[0], ((None,), (None,)))
        self.assertIn('meld_identity_unknown:0', hint.issues)
        self.assertFalse(hint.visible_remainders_used)

    def test_manual_source_cannot_claim_visual_frames_or_unqualified_source(self):
        snap, _ = self.snapshot()
        for changed in (
            dict(stable_frames=3), dict(source_session='video:owner-entry-1'),
        ):
            with self.subTest(changed=changed):
                values = {**snap.__dict__, **changed}
                assessment = assess_current_snapshot(CurrentTableSnapshot(**values))
                self.assertFalse(assessment.allows(SnapshotCapability.SHANTEN))

    def test_invalid_meld_count_and_revision_rejected(self):
        for changed in (dict(own_meld_count=True), dict(own_meld_count=6),
                        dict(revision=-1)):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.snapshot(**changed)

    def test_observed_score_is_not_a_rule_settlement(self):
        row = observed_score_entry(scores_before=(1000, 1000),
                                   scores_after=(1080, 920),
                                   unresolved_rule_id=UNRESOLVED_SETTLEMENT)
        self.assertEqual(row['status'], 'OBSERVED_ONLY')
        self.assertEqual(row['score_delta'], [80, -80])
        self.assertEqual(row['input_source'], 'USER_ENTERED_UNVERIFIED')
        self.assertFalse(row['automatic_settlement'])
        self.assertFalse(row['confirmed_rule_evidence'])
        self.assertFalse(row['official_ai_reward_eligible'])

    def test_invalid_scores_and_missing_unknown_rule_rejected(self):
        for before, after, rule in (
            ((1000, 1000), (1080, 930), UNRESOLVED_SETTLEMENT),
            ((1000, 1000), (True, 1999), UNRESOLVED_SETTLEMENT),
            ((1000, 1000), (-1, 2001), UNRESOLVED_SETTLEMENT),
            ((1000, 1000), (1080, 920), ''),
            ((1000, 1000), (1080, 920), 'settlement.qiangjin_full'),
            ((1000, 1000), (1080, 920), 'settlement.gang_hu'),
            ((1000, 1000), (1080, 920), 'settlement.does_not_exist'),
        ):
            with self.subTest(after=after, rule=rule), self.assertRaises(ValueError):
                observed_score_entry(scores_before=before, scores_after=after,
                                     unresolved_rule_id=rule)

    def test_manual_events_keep_provenance_and_never_book_settlement(self):
        snapshot, hint = self.snapshot()
        score = observed_score_entry(scores_before=(1000, 1000),
                                     scores_after=(1080, 920),
                                     unresolved_rule_id=UNRESOLVED_SETTLEMENT)
        with TemporaryDirectory() as folder:
            evidence = EvidenceSession(folder, metadata={'backend': 'MANUAL'})
            evidence.mark('MANUAL_TABLE_SNAPSHOT', {
                'input_source': 'USER_ENTERED_UNVERIFIED',
                'snapshot': asdict(snapshot), 'hint': asdict(hint),
                'official_ai_reward_eligible': False, 'safe_for_executor': False,
            })
            evidence.mark('MANUAL_SCORE_OBSERVATION', score)
            evidence.close()
            rows = [json.loads(line) for line in evidence.events_path.read_text(
                encoding='utf-8').splitlines()]
            self.assertEqual([row['kind'] for row in rows[1:]], [
                'MANUAL_TABLE_SNAPSHOT', 'MANUAL_SCORE_OBSERVATION'])
            self.assertEqual(rows[1]['payload']['snapshot']['stable_frames'], 0)
            self.assertFalse(rows[1]['payload']['hint']['visible_remainders_used'])
            self.assertFalse(rows[2]['payload']['automatic_settlement'])
            self.assertFalse(rows[2]['payload']['confirmed_rule_evidence'])
            self.assertEqual(rows[1]['rule_snapshot_id'], rows[2]['rule_snapshot_id'])

    def test_ui_labels_cover_entire_base_tile_alphabet(self):
        try:
            from workspace.hint_alpha.app import HintAlphaApp
        except ImportError:
            self.skipTest('optional UI dependencies unavailable')
        self.assertEqual({tile: HintAlphaApp._tile_label(tile)
                          for tile in env.BASE_TILES},
                         {tile: env.CN[tile] for tile in env.BASE_TILES})


if __name__ == '__main__':
    unittest.main()
