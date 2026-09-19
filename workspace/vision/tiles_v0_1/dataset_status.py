"""Audit real-label coverage before reporting Vision accuracy."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from .labels import approved_labels
from .taxonomy import TILE_CLASSES


REGIONS = ("hand_region", "draw_region", "gold_region")


def dataset_readiness(dataset_root):
    root = Path(dataset_root)
    labels = approved_labels(root)

    class_counts = Counter()
    class_groups = defaultdict(set)
    region_counts = Counter()
    group_counts = Counter()
    for label in labels:
        tile_id = label["tile_id"]
        group = str(label.get("source_frame") or label["image"])
        class_counts[tile_id] += 1
        class_groups[tile_id].add(group)
        region_counts[label["region"]] += 1
        group_counts[group] += 1

    replicated_classes = sorted(
        tile_id for tile_id, groups in class_groups.items()
        if len(groups) >= 2
    )
    single_group_classes = sorted(
        tile_id for tile_id, groups in class_groups.items()
        if len(groups) == 1
    )
    missing_classes = sorted(
        set(TILE_CLASSES) - set(class_counts)
    )
    scorable_labels = sum(
        1 for label in labels
        if len(class_groups[label["tile_id"]]) >= 2
    )

    return {
        "approved_labels": len(labels),
        "source_groups": len(group_counts),
        "observed_classes": len(class_counts),
        "taxonomy_classes": len(TILE_CLASSES),
        "replicated_classes": replicated_classes,
        "replicated_class_count": len(replicated_classes),
        "single_group_classes": single_group_classes,
        "missing_classes": missing_classes,
        "region_counts": {
            region: region_counts.get(region, 0) for region in REGIONS
        },
        "class_counts": dict(sorted(class_counts.items())),
        "class_source_group_counts": {
            tile_id: len(class_groups[tile_id])
            for tile_id in sorted(class_groups)
        },
        "scorable_labels_for_group_holdout": scorable_labels,
        "scorable_fraction": (
            scorable_labels / len(labels) if labels else 0.0
        ),
        "can_run_leakage_safe_accuracy": (
            len(group_counts) >= 2 and scorable_labels > 0
        ),
        "all_observed_classes_replicated": (
            bool(class_counts)
            and not single_group_classes
        ),
        "all_three_regions_labelled": all(
            region_counts.get(region, 0) > 0 for region in REGIONS
        ),
        "safe_for_executor": False,
        "next_data_priority": {
            "replicate_across_source_groups": single_group_classes,
            "unseen_taxonomy_classes": missing_classes,
            "empty_regions": [
                region for region in REGIONS
                if region_counts.get(region, 0) == 0
            ],
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Audit Tiles V0.1 real-label coverage")
    parser.add_argument("--dataset", default="dataset/tiles_v0_1")
    parser.add_argument("--output")
    args = parser.parse_args()

    report = dataset_readiness(args.dataset)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
