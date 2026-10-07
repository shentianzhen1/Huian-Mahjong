"""Development-only provenance probe for concealed template matches.

The production classifier scores each class by the maximum NCC over all of its
reviewed templates.  This helper exposes which exact exemplar produced that
maximum and whether other source sessions also score the same class highly.
It never changes Runtime acceptance and it never treats source_session as proof
of an independent original match.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Iterable

import cv2
from PIL import Image

from workspace.vision.tiles_v0_1.labels import approved_labels
from workspace.vision.tiles_v0_1.template_classifier import (
    _canonical_region,
    _feature,
)


CONCEALED_REGIONS = frozenset({"hand_region", "draw_visual"})


def _sample_key(row: dict) -> str:
    return str(
        row.get("id")
        or f"{row.get('image')}|{row.get('source_frame')}|{row.get('bbox')}"
    )


def _load_label_crop(root: Path, row: dict) -> Image.Image:
    path = root / row["image"]
    with Image.open(path) as source:
        image = source.convert("RGB")
        if Path(row["image"]).parts[:1] == ("templates",):
            return image.copy()
        x, y, width, height = (int(value) for value in row["bbox"])
        return image.crop((x, y, x + width, y + height)).copy()


def _concealed_labels(
    dataset_root: str | Path,
    *,
    exclude_source_session: str | None = None,
) -> list[dict]:
    rows: list[dict] = []
    for row in approved_labels(dataset_root):
        region = _canonical_region(row.get("region"))
        if region not in CONCEALED_REGIONS or row.get("gold_skin_only"):
            continue
        if exclude_source_session and row.get("source_session") == exclude_source_session:
            continue
        if not isinstance(row.get("tile_id"), str):
            continue
        if not isinstance(row.get("source_session"), str):
            continue
        rows.append(row)
    return rows


def summarize_scored_rows(scored_rows: Iterable[dict]) -> dict[str, object]:
    """Summarize already-scored exemplars without inferring match lineage."""
    rows = list(scored_rows)
    if not rows:
        raise ValueError("at least one scored template is required")
    by_class: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_class[str(row["tile_id"])].append(row)

    classes = []
    for tile_id, class_rows in by_class.items():
        ordered = sorted(class_rows, key=lambda row: float(row["score"]), reverse=True)
        session_best: dict[str, dict] = {}
        for row in ordered:
            session = str(row["source_session"])
            if session not in session_best:
                session_best[session] = row
        ordered_sessions = sorted(
            session_best.values(), key=lambda row: float(row["score"]), reverse=True
        )
        top_two = ordered_sessions[:2]
        classes.append(
            {
                "tile_id": tile_id,
                "class_max": float(ordered[0]["score"]),
                "winning_template": {
                    key: ordered[0].get(key)
                    for key in (
                        "sample_key",
                        "source_session",
                        "source_sha256",
                        "source_frame",
                        "region",
                        "image",
                    )
                },
                "distinct_source_session_count": len(session_best),
                "per_source_session_max": [
                    {
                        "source_session": row.get("source_session"),
                        "source_sha256": row.get("source_sha256"),
                        "sample_key": row.get("sample_key"),
                        "score": float(row["score"]),
                    }
                    for row in ordered_sessions
                ],
                "second_source_score": (
                    float(top_two[1]["score"]) if len(top_two) >= 2 else None
                ),
                "top_two_source_mean": (
                    sum(float(row["score"]) for row in top_two) / 2.0
                    if len(top_two) >= 2
                    else None
                ),
            }
        )

    classes.sort(key=lambda row: float(row["class_max"]), reverse=True)
    top_margin = (
        float(classes[0]["class_max"]) - float(classes[1]["class_max"])
        if len(classes) >= 2
        else None
    )
    return {
        "class_ranking": classes,
        "top1_tile": classes[0]["tile_id"],
        "top1_score": classes[0]["class_max"],
        "top2_tile": classes[1]["tile_id"] if len(classes) >= 2 else None,
        "top2_score": classes[1]["class_max"] if len(classes) >= 2 else None,
        "top1_top2_margin": top_margin,
    }


def probe_query(
    dataset_root: str | Path,
    query_path: str | Path,
    *,
    exclude_source_session: str | None = None,
    top_n: int = 8,
) -> dict[str, object]:
    root = Path(dataset_root)
    query = Path(query_path)
    if not query.is_file():
        raise ValueError("query_path must be an existing tile crop")
    if top_n < 1:
        raise ValueError("top_n must be positive")

    with Image.open(query) as source:
        query_feature = _feature(source.convert("RGB"), region="concealed_identity")

    scored = []
    for row in _concealed_labels(root, exclude_source_session=exclude_source_session):
        image_path = root / row["image"]
        if not image_path.is_file():
            continue
        template_feature = _feature(
            _load_label_crop(root, row), region="concealed_identity"
        )
        score = float(
            cv2.matchTemplate(
                query_feature, template_feature, cv2.TM_CCOEFF_NORMED
            )[0, 0]
        )
        if not (score == score):
            score = -1.0
        scored.append(
            {
                "tile_id": row["tile_id"],
                "score": score,
                "sample_key": _sample_key(row),
                "source_session": row.get("source_session"),
                "source_sha256": row.get("sha256"),
                "source_frame": row.get("source_frame"),
                "region": _canonical_region(row.get("region")),
                "image": row.get("image"),
            }
        )

    summary = summarize_scored_rows(scored)
    return {
        "schema_version": "concealed_template_source_consensus_probe_v0_1",
        "development_only": True,
        "runtime_changed": False,
        "source_session_is_independent_match_evidence": False,
        "query": str(query),
        "excluded_source_session": exclude_source_session,
        "top": summary["class_ranking"][:top_n],
        "top1_tile": summary["top1_tile"],
        "top1_score": summary["top1_score"],
        "top2_tile": summary["top2_tile"],
        "top2_score": summary["top2_score"],
        "top1_top2_margin": summary["top1_top2_margin"],
        "interpretation": (
            "class_max reproduces current max-exemplar behavior; second_source_score "
            "and top_two_source_mean are diagnostics only. Review original-match "
            "lineage before treating multiple source sessions as independent support."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="private reviewed tile crop to diagnose")
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument("--exclude-source-session")
    parser.add_argument("--top", type=int, default=8)
    parser.add_argument("--output")
    args = parser.parse_args()
    report = probe_query(
        args.dataset,
        args.query,
        exclude_source_session=args.exclude_source_session,
        top_n=args.top,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
