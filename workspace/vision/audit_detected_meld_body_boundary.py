"""Source-locked development audit; manual boxes are comparison only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def audit(video_path):
    import cv2
    from PIL import Image
    from workspace.vision.public_tile_detector import detect_public_tile_geometry
    from workspace.vision.public_meld_geometry_normalization import normalize_public_meld_crop

    spec = json.loads(Path('references/vision/2026-10-03/hand8_s789_harvest_spec_v0_1.json').read_text())
    source = spec['sources'][0]
    digest = hashlib.sha256(Path(video_path).read_bytes()).hexdigest()
    if digest != source['source_sha256']:
        raise ValueError('source SHA mismatch')
    group = source['groups'][0]
    boxes = group['face_bboxes']
    manual = [min(b[0] for b in boxes), min(b[1] for b in boxes),
              max(b[0]+b[2] for b in boxes), max(b[1]+b[3] for b in boxes)]
    cap = cv2.VideoCapture(str(video_path))
    rows = []
    try:
        for frame in group['frame_indices']:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
            ok, bgr = cap.read()
            if not ok or int(cap.get(cv2.CAP_PROP_POS_FRAMES)) != frame + 1:
                raise ValueError('frame decode mismatch')
            image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
            # Audit all detector candidates; no manual ROI selects the input.
            candidates = []
            for candidate in detect_public_tile_geometry(image, frame=frame).candidates:
                if candidate.geometry_kind != 'bottom_group':
                    continue
                normalized = normalize_public_meld_crop(image, candidate)
                tight = normalized.analysis.tight_bbox_in_group
                if tight is None:
                    candidates.append({'detector_bbox': list(candidate.pixel_bbox),
                                       'analysis': normalized.analysis.to_dict()})
                    continue
                x, y, _, _ = candidate.pixel_bbox
                tx, ty, tw, th = tight
                body = [x+tx, y+ty, x+tx+tw, y+ty+th]
                candidates.append({'detector_bbox': list(candidate.pixel_bbox),
                    'analysis': normalized.analysis.to_dict(),
                    'tight_body_xyxy': body,
                    'manual_comparison_xyxy': manual,
                    'edge_delta_left_top_right_bottom': [body[i]-manual[i] for i in range(4)],
                    'raw_detector_equal_thirds_x': [x+round(candidate.pixel_bbox[2]*i/3) for i in range(4)],
                    'tight_body_equal_thirds_x': [body[0]+round(tw*i/3) for i in range(4)]})
            rows.append({'frame': frame, 'candidates': candidates})
    finally:
        cap.release()
    return {'schema_version': 'detected_meld_body_boundary_audit_dev_v0_1',
        'source_sha256': digest, 'rows': rows,
        'prior_identity_result_user_reported_not_rerun': {'correct_faces': 10, 'faces': 15,
            'correct_groups': 0, 'groups': 5, 'S9_top1': 'S7'},
        'development_only': True, 'manual_boxes_used_as_detector_input': False,
        'identity_accuracy_measured_this_run': False, 'automatic_repair_verified': False,
        'safe_for_hint': False, 'safe_for_executor': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--video', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(args.video), indent=2)+'\n')
