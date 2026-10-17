from dataclasses import replace

from workspace.vision.public_dense_river_slots import (
    DenseRiverMaskFrame, DenseRiverSlotProfile,
    audit_dense_river_occupancy_sequence,
)

PROFILE = DenseRiverSlotProfile('player', ((.1,.1,.1,.1),(.2,.1,.1,.1),(.1,.2,.1,.1)))


def packets(masks):
    return tuple(DenseRiverMaskFrame('s', 'a'*64, 0, i, tuple(mask), True)
                 for i, mask in enumerate(masks))


def audit(masks):
    return audit_dense_river_occupancy_sequence(
        packets(masks), profile=PROFILE, slots_independently_reviewed=True)


def test_removed_cell_reoccupation_is_reported_without_action_promotion():
    report = audit([(True,False,False)]*3 + [(True,True,False)]*3
                   + [(True,False,False)]*3 + [(True,True,False)]*3)
    rows = report['transitions']
    assert [r['change'] for r in rows] == ['OCCUPANCY_INCREASE','OCCUPANCY_DECREASE','OCCUPANCY_INCREASE']
    assert [r['reused_cell'] for r in rows] == [False,False,True]
    assert rows[-1]['first_stable_after_frame'] == 9
    assert rows[-1]['confirmation_frame'] == 11
    assert report['actual_actions_emitted'] == 0
    assert report['safe_for_runtime'] is False


def test_reviewed_second_row_cell_can_grow_without_resetting_first_row():
    report = audit([(True,True,False)]*3 + [(True,True,True)]*3)
    assert [(r['before_count'],r['after_count']) for r in report['transitions']] == [(2,3)]


def test_unknown_interval_is_preserved_and_multi_cell_change_is_ambiguous():
    report = audit([(True,False,False)]*3 + [(True,None,False)]*3 + [(True,True,False)]*3)
    assert report['transitions'][0]['intervening_unknown_mask'] is True
    assert report['transitions'][0]['evidence_grade'] == 'UNKNOWN'
    report = audit([(False,False,False)]*3 + [(True,True,False)]*3)
    assert report['transitions'] == [] and report['ambiguous_changes'] == 1


def test_source_gap_epoch_and_unreviewed_layout_fail_closed():
    frames = packets([(False,False,False)]*3 + [(True,False,False)]*3)
    for rows in [frames[:2]+frames[3:], frames[:3]+(replace(frames[3],stream_epoch=1),)+frames[4:]]:
        assert audit_dense_river_occupancy_sequence(rows,profile=PROFILE,slots_independently_reviewed=True)['status'] == 'UNKNOWN'
    assert audit_dense_river_occupancy_sequence(frames,profile=PROFILE,slots_independently_reviewed=False)['status'] == 'UNKNOWN'
