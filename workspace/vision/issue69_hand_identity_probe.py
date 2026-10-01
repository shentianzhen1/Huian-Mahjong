"""Local-only #69 probe: source-lock two Runtime Vision hand bursts around an event.

No source pixels are committed. The report contains only geometry/identity
facts needed to decide whether a HandIdentityDelta may be attempted.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

from workspace.vision.tiles_runtime_v0_2.runtime_reader import _video_frames, read_stable_frames


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()


def _burst(video: Path, start: int, *, dataset: str, session: str,
           frames: int, stride: int, threshold: float) -> dict:
    images, ids = _video_frames(video,start,frames,stride)
    out=read_stable_frames(images,dataset,frame_ids=ids,session=session,
                           confidence_threshold=threshold)
    concealed=[x for x in out.get("components",())
               if x.get("region_candidate") in {"hand","draw_visual"}]
    return {
        "frames": ids,
        "concealed_tile_count": out.get("concealed_tile_count"),
        "geometry_untrusted": out.get("geometry_untrusted"),
        "all_concealed_tile_ids_trusted": out.get("all_concealed_tile_ids_trusted"),
        "tiles": [x.get("tile_id","UNKNOWN") for x in concealed],
        "minimum_identity_confidence": min(
            (float(x.get("tile_confidence",0)) for x in concealed), default=0.0),
        "identity_reasons": [x.get("identity_reason") for x in concealed],
    }


def run(video: Path, *, expected_sha256: str, before_start: int, after_start: int,
        dataset: str, session: str, frames: int=5, stride: int=1,
        threshold: float=.82) -> dict:
    digest=sha256(video)
    if digest != expected_sha256:
        raise ValueError("video SHA256 does not match reviewed source")
    before=_burst(video,before_start,dataset=dataset,session=session,
                  frames=frames,stride=stride,threshold=threshold)
    after=_burst(video,after_start,dataset=dataset,session=session,
                 frames=frames,stride=stride,threshold=threshold)
    qualified=all(
        not row["geometry_untrusted"]
        and row["all_concealed_tile_ids_trusted"]
        and row["minimum_identity_confidence"] >= threshold
        for row in (before,after)
    )
    return {
        "schema_version":"issue69_hand_identity_probe_v0_1",
        "development_only":True,
        "source_sha256":digest,
        "source_session":session,
        "identity_threshold":threshold,
        "before":before,"after":after,
        "identity_delta_gate_eligible":qualified,
        "formal_promotion_evidence":False,
        "safe_for_runtime":False,"safe_for_hint":False,"safe_for_executor":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--video",type=Path,required=True)
    p.add_argument("--expected-sha256",required=True)
    p.add_argument("--before-start",type=int,required=True)
    p.add_argument("--after-start",type=int,required=True)
    p.add_argument("--dataset",default="dataset/tiles_runtime_v0_2")
    p.add_argument("--session",required=True)
    p.add_argument("--frames",type=int,default=5,choices=(3,4,5))
    p.add_argument("--stride",type=int,default=1)
    p.add_argument("--threshold",type=float,default=.82)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    report=run(a.video,expected_sha256=a.expected_sha256,
               before_start=a.before_start,after_start=a.after_start,
               dataset=a.dataset,session=a.session,frames=a.frames,
               stride=a.stride,threshold=a.threshold)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__": main()
