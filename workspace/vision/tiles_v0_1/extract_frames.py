"""Extract deterministic, time-sampled key frames from Recorder AVI material."""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
from PIL import Image


def _frame_id(source, frame_index):
    digest = hashlib.sha256(f"{source.resolve()}:{frame_index}".encode()).hexdigest()[:12]
    return f"{source.stem}_f{frame_index:07d}_{digest}"


def extract_key_frames(source, dataset_root, interval_seconds=1.0, max_frames=None):
    """Write one PNG at each interval and append reproducible JSONL metadata."""
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")
    source, dataset_root = Path(source), Path(dataset_root)
    output = dataset_root / "images" / "frames"
    meta = dataset_root / "meta" / "frames.jsonl"
    output.mkdir(parents=True, exist_ok=True)
    meta.parent.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError(f"Cannot open video or image: {source}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 1.0
    next_seconds, written, frame_index = 0.0, [], 0
    with meta.open("a", encoding="utf-8") as stream:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            seconds = frame_index / fps
            if seconds + 1e-9 >= next_seconds:
                frame_id = _frame_id(source, frame_index)
                path = output / f"{frame_id}.png"
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                Image.fromarray(rgb).save(path)
                row = {
                    "frame_id": frame_id, "image": str(path.relative_to(dataset_root)).replace("\\", "/"),
                    "source": str(source), "source_frame": frame_index,
                    "video_seconds": seconds, "source_fps": fps,
                    "size": [int(frame.shape[1]), int(frame.shape[0])],
                }
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                written.append(row)
                next_seconds += interval_seconds
                if max_frames is not None and len(written) >= max_frames:
                    break
            frame_index += 1
    capture.release()
    return written


def main():
    parser = argparse.ArgumentParser(description="Extract fixed-interval frames from Recorder AVI")
    parser.add_argument("source")
    parser.add_argument("--dataset", default="dataset/tiles_v0_1")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--max-frames", type=int)
    args = parser.parse_args()
    rows = extract_key_frames(args.source, args.dataset, args.interval, args.max_frames)
    print(f"Extracted {len(rows)} frames into {Path(args.dataset) / 'images' / 'frames'}")


if __name__ == "__main__":
    main()
