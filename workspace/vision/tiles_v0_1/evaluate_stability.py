"""Evaluate temporal tile-prediction stability from JSONL frame outputs."""
import argparse
import json
from pathlib import Path

from .postprocess import TilePrediction, evaluate_temporal_stability


def _prediction(row):
    return TilePrediction(
        tile_id=row["tile_id"],
        confidence=float(row["confidence"]),
        region=row["region"],
        bbox=tuple(row["bbox"]),
        slot=row.get("slot"),
        category=row.get("category"),
    )


def load_prediction_frames(path):
    frames = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if "predictions" not in row or not isinstance(row["predictions"], list):
                raise ValueError(
                    f"line {line_number} must contain a predictions list")
            frames.append(tuple(_prediction(item) for item in row["predictions"]))
    if not frames:
        raise ValueError("prediction JSONL contains no frames")
    return tuple(frames)


def temporal_report_to_dict(report):
    return {
        "total_slots": report.total_slots,
        "stable_slots": report.stable_slots,
        "stable_fraction": report.stable_fraction,
        "minimum_agreement": report.minimum_agreement,
        "minimum_frames": report.minimum_frames,
        "slots": [
            {
                "region": item.region,
                "slot": item.slot,
                "frames_seen": item.frames_seen,
                "voted_tile": item.voted_tile,
                "agreement": item.agreement,
                "mean_confidence": item.mean_confidence,
                "stable": item.stable,
            }
            for item in report.slots
        ],
        "safe_for_executor": False,
        "note": (
            "Temporal agreement is not recognition accuracy; combine with "
            "independently labelled holdout accuracy before any executor gate."
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate aligned multi-frame Mahjong tile stability")
    parser.add_argument("predictions_jsonl")
    parser.add_argument("--agreement", type=float, default=0.80)
    parser.add_argument("--minimum-frames", type=int, default=3)
    parser.add_argument("--output")
    args = parser.parse_args()

    report = evaluate_temporal_stability(
        load_prediction_frames(args.predictions_jsonl),
        minimum_agreement=args.agreement,
        minimum_frames=args.minimum_frames,
    )
    payload = temporal_report_to_dict(report)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
