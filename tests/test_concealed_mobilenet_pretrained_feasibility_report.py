import json
from pathlib import Path

REPORT = Path("references/vision/2026-10-08/concealed_mobilenet_pretrained_feasibility_v0_1.json")


def _load():
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_pretrained_probe_keeps_runtime_frozen():
    report = _load()
    frozen = report["frozen_contract"]
    assert frozen["runtime_identity_threshold"] == 0.82
    assert frozen["runtime_identity_threshold_changed"] is False
    assert frozen["current_agent"] == "MeldAwareShantenAgent V0.10"
    assert frozen["executor_enabled"] is False
    assert frozen["runtime_changed"] is False
    assert frozen["classifier_promoted"] is False
    assert report["safe_for_runtime"] is False
    assert report["formal_promotion_evidence"] is False


def test_official_weights_are_pinned_but_not_packaged():
    weights = _load()["official_pretrained_weights"]
    assert weights["sha256"] == "047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f"
    assert weights["workflow_run_id"] == 37742044630
    assert weights["artifact_id"] == 11533369139
    assert weights["weights_committed_to_git"] is False
    assert weights["weights_packaged_in_installer"] is False
    assert weights["existing_runner_cache_compatibility_verified"] is True


def test_m2_failure_is_not_hidden_by_model_selection():
    report = _load()
    experiments = report["experiments"]
    assert experiments["pretrained_prototype_with_existing_appearance_augmentation"]["m2_correct"] == 0
    assert experiments["frozen_backbone_balanced_linear_head"]["m2_correct_each_seed"] == 0
    assert experiments["pretrained_last_projection_plus_linear_head"]["m2_correct_each_seed"] == 0
    recrop = experiments["reviewed_m2_source_recrop"]
    assert recrop["adding_clean_recrop_m2_correct"] == 0
    assert recrop["combined_remaining_errors"] == {"M2->M3": 3}
    assert report["decision"]["do_not_lower_runtime_threshold"] is True
    assert report["decision"]["do_not_hardcode_m2_rule"] is True
