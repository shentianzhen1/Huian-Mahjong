import json
from pathlib import Path

from workspace.vision.tiles_runtime_v0_2.concealed_template_quarantine_probe import (
    filter_exact_images,
    support_summary,
)


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset/tiles_runtime_v0_2"
BAD_S6 = "templates/hand/960_hand_region_s05_S6.png"


def _labels():
    rows = []
    paths = [DATASET / "labels.jsonl"]
    additions = DATASET / "labels_reviewed_additions"
    if additions.is_dir():
        paths.extend(sorted(additions.glob("*.jsonl")))
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("approved") is True or row.get("status") == "approved":
                rows.append(row)
    return rows


def test_exact_candidate_filter_does_not_pattern_delete_other_s6_assets():
    labels = _labels()
    filtered = filter_exact_images(labels, [BAD_S6])
    assert all(row.get("image") != BAD_S6 for row in filtered)
    assert any(
        row.get("tile_id") == "S6" and row.get("image") != BAD_S6
        for row in filtered
    )


def test_candidate_quarantine_preserves_all_concealed_classes():
    summary = support_summary(_labels(), [BAD_S6])
    assert summary["removed_label_count"] == 1
    assert summary["classes_losing_all_support"] == []
    assert summary["class_count_before"] == summary["class_count_after"] == 34
    assert summary["support_before"]["S6"] == summary["support_after"]["S6"] + 1


def test_filter_is_exact_path_only():
    labels = [
        {"image": BAD_S6, "tile_id": "S6", "region": "hand_region"},
        {"image": "templates/hand/copy_960_hand_region_s05_S6.png", "tile_id": "S6", "region": "hand_region"},
    ]
    filtered = filter_exact_images(labels, [BAD_S6])
    assert [row["image"] for row in filtered] == [
        "templates/hand/copy_960_hand_region_s05_S6.png"
    ]
