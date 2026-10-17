from workspace.vision.concealed_template_match_lineage import ConcealedTemplateSource
from workspace.vision.tiles_runtime_v0_2.opened_gold_role_invariant_lomo import (
    has_disjoint_truth_reference,
    ordinary_concealed_labels,
    representative_labels,
    summarize,
)


def source(sha, group):
    return ConcealedTemplateSource(sha, group, "evidence.json")


def test_ordinary_concealed_labels_excludes_gold_roles():
    labels = [
        {"region": "hand_region", "tile_id": "M1", "gold_skin_only": False},
        {"region": "draw_visual", "tile_id": "M2"},
        {"region": "gold_region", "tile_id": "M3"},
        {"region": "hand_region", "tile_id": "M4", "gold_skin_only": True},
    ]
    assert [row["tile_id"] for row in ordinary_concealed_labels(labels)] == ["M1", "M2"]


def test_representative_labels_collapses_same_match_and_tile_deterministically():
    a = "a" * 64
    b = "b" * 64
    lineage = {a: source(a, "match_a"), b: source(b, "match_b")}
    labels = [
        {"region": "hand_region", "tile_id": "M1", "sha256": a, "source_frame": 20, "image": "z.png"},
        {"region": "hand_region", "tile_id": "M1", "sha256": a, "source_frame": 10, "image": "a.png"},
        {"region": "draw_visual", "tile_id": "M2", "sha256": a, "source_frame": 5, "image": "m2.png"},
        {"region": "hand_region", "tile_id": "M1", "sha256": b, "source_frame": 3, "image": "b.png"},
        {"region": "hand_region", "tile_id": "M9", "sha256": "c" * 64, "source_frame": 1, "image": "unknown.png"},
    ]
    reps = representative_labels(labels, lineage)
    assert [(row["sha256"], row["tile_id"], row["source_frame"]) for row in reps] == [
        (a, "M1", 10),
        (a, "M2", 5),
        (b, "M1", 3),
    ]


def test_has_disjoint_truth_reference_uses_match_group_not_session():
    a = "a" * 64
    b = "b" * 64
    c = "c" * 64
    lineage = {
        a: source(a, "match_a"),
        b: source(b, "match_a"),
        c: source(c, "match_b"),
    }
    same_only = [
        {"region": "hand_region", "tile_id": "M6", "sha256": a},
        {"region": "draw_visual", "tile_id": "M6", "sha256": b},
    ]
    assert not has_disjoint_truth_reference(same_only, lineage, query_match_group="match_a", tile_id="M6")
    assert has_disjoint_truth_reference(
        same_only + [{"region": "hand_region", "tile_id": "M6", "sha256": c}],
        lineage,
        query_match_group="match_a",
        tile_id="M6",
    )


def test_summarize_does_not_count_unscorable_as_wrong():
    result = summarize([
        {"scorable": True, "correct": True},
        {"scorable": True, "correct": False},
        {"scorable": False, "correct": False},
    ])
    assert result == {
        "query_count": 3,
        "scorable_query_count": 2,
        "correct_query_count": 1,
        "unscorable_query_count": 1,
        "diagnostic_ratio": 0.5,
    }
