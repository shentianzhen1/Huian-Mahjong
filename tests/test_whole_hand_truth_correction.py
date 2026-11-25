import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "references/vision/2026-10-07/whole_hand_truth_seed_20261003_v0_1.json"
INTAKE = ROOT / "references/vision/2026-10-07/whole_hand_intake_queue_20261003.json"
LINEAGE = ROOT / "references/vision/2026-10-07/whole_hand_priority_class_lineage_audit_v0_1.json"
WRONG = ROOT / "references/vision/2026-10-07/high_confidence_concealed_wrong_accepts_v0_1.json"
CORRECTION = ROOT / "references/vision/2026-10-08/whole_hand_truth_correction_20261003_v0_1.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sample(seed, sample_id):
    return next(row for row in seed["samples"] if row["sample_id"] == sample_id)


def test_corrected_source_truth_is_pinned():
    seed = load(SEED)
    assert sample(seed, "20261003-seg-shae5b8-t30.0")["truth"]["concealed_hand"][-1] == "M6"
    assert sample(seed, "20261003-seg-shae5b8-t40.0")["truth"]["concealed_hand"][9] == "S5"
    assert sample(seed, "20261003-seg-shae5b8-t46.0")["truth"]["concealed_hand"][9] == "S5"


def test_invalid_m7_intake_cannot_return():
    intake = load(INTAKE)
    corrected = [row for row in intake["items"] if row.get("source_frame") == 1176 and row.get("slot") == 15]
    assert len(corrected) == 1
    assert corrected[0]["tile_id"] == "M6"
    assert intake["local_validation"]["M7_remains_single_reviewed_original_match_group"] is True


def test_m7_lineage_stays_fail_closed_after_truth_correction():
    audit = load(LINEAGE)
    m7 = audit["classes"]["M7"]
    assert m7["new_source_contains_reviewed_crop"] is False
    assert m7["post_asset_sync_status"] == "ONE_REVIEWED_ORIGINAL_MATCH_GROUP_ONLY"


def test_wrong_accept_metrics_use_corrected_truth():
    wrong = load(WRONG)
    assert wrong["baseline"]["accepted"] == 31
    assert wrong["baseline"]["accepted_correct"] == 31
    assert wrong["baseline"]["wrong_accepted"] == 0
    assert wrong["wrong_accepts"] == []
    correction = load(CORRECTION)
    metrics = correction["corrected_ordinary_43_tile_metrics"]
    assert metrics["raw_top1_correct"] == 36
    assert metrics["remaining_raw_confusions"] == {"S4->S6": 4, "M2->M3": 3}
    assert metrics["runtime_exposed_correct"] == 25
    assert metrics["runtime_exposed_wrong"] == 0
