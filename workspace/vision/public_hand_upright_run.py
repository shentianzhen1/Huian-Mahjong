"""Development-only hand ROI observer for #69.

Counts only the dominant run of upright concealed tile faces. Exposed melds,
draw_visual and Gold remain independent observers. No tile identity or action
semantics are inferred.
"""
from __future__ import annotations
from dataclasses import dataclass
from statistics import median
from collections import Counter
from typing import Sequence


@dataclass(frozen=True)
class UprightFace:
    x:int; y:int; width:int; height:int


@dataclass(frozen=True)
class UprightHandCount:
    status:str
    count:int|None
    reason:str


def _compatible(a:UprightFace,b:UprightFace, typical_width:float, typical_height:float)->bool:
    gap=b.x-(a.x+a.width)
    baseline_delta=abs((a.y+a.height)-(b.y+b.height))
    height_delta=abs(a.height-b.height)
    return (
        -typical_width*0.15 <= gap <= typical_width*0.40
        and baseline_delta <= typical_height*0.10
        and height_delta <= typical_height*0.12
    )


def count_upright_hand(faces:Sequence[UprightFace])->UprightHandCount:
    if len(faces)<8:
        return UprightHandCount("UNKNOWN",None,"insufficient_face_candidates")
    ordered=sorted(faces,key=lambda f:f.x)
    widths=[f.width for f in ordered if f.width>0]
    heights=[f.height for f in ordered if f.height>0]
    if len(widths)!=len(ordered) or len(heights)!=len(ordered):
        return UprightHandCount("UNKNOWN",None,"invalid_face_geometry")
    tw=float(median(widths)); th=float(median(heights))
    runs=[]; run=[ordered[0]]
    for face in ordered[1:]:
        if _compatible(run[-1],face,tw,th):
            run.append(face)
        else:
            runs.append(run); run=[face]
    runs.append(run)
    runs.sort(key=len,reverse=True)
    if len(runs[0])<8:
        return UprightHandCount("UNKNOWN",None,"no_dominant_upright_hand_run")
    if len(runs)>1 and len(runs[1])==len(runs[0]):
        return UprightHandCount("UNKNOWN",None,"ambiguous_upright_runs")
    return UprightHandCount("UPRIGHT_HAND_COUNT_CANDIDATE_ONLY",len(runs[0]),"dominant_upright_run")


def fuse_upright_hand_counts(counts:Sequence[UprightHandCount],minimum_frames:int=3)->UprightHandCount:
    accepted=[x.count for x in counts if x.status=="UPRIGHT_HAND_COUNT_CANDIDATE_ONLY" and x.count is not None]
    if minimum_frames<3 or minimum_frames>5:
        return UprightHandCount("UNKNOWN",None,"invalid_stability_requirement")
    if not accepted:
        return UprightHandCount("UNKNOWN",None,"no_accepted_frames")
    count,votes=Counter(accepted).most_common(1)[0]
    if votes<minimum_frames:
        return UprightHandCount("UNKNOWN",None,"count_not_stable_across_frames")
    return UprightHandCount("STABLE_UPRIGHT_HAND_COUNT_CANDIDATE_ONLY",count,f"stable_votes={votes}")
