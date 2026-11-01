"""Source/pixel-pinned bottom-seat S234 development reference loader."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path


PIN = Path('references/vision/2026-10-03/bottom_s234_reference_pin_v0_1.json')


def load_bottom_s234_templates(video_path, *, rectified=False, descriptor_extractor=None):
    import cv2
    from PIL import Image
    from workspace.vision.evaluate_sift_detector_body_boundary_probe import raw_face_boxes
    from workspace.vision.evaluate_sift_symmetric_geometry_probe import normalize_single_face
    from workspace.vision.public_meld_identity_sift import PublicMeldSiftTemplate, _sift_descriptors
    from workspace.vision.public_tile_detector import detect_public_tile_geometry

    pin = json.loads(PIN.read_text())
    if pin['label_authority'] != 'assistant_visual_review_not_user_confirmation' or pin['reviewed_candidate_tiles'] != ['S2', 'S3', 'S4']:
        raise ValueError('bottom reference label contract drifted')
    if [f['tile_id'] for f in pin['faces']] != pin['reviewed_candidate_tiles']:
        raise ValueError('bottom reference face labels drifted')
    source_sha = hashlib.sha256(Path(video_path).read_bytes()).hexdigest()
    if source_sha != pin['source_sha256']:
        raise ValueError('bottom reference source SHA mismatch')
    cap = cv2.VideoCapture(str(video_path))
    try:
        frame = pin['source_frame_index']
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
        ok, bgr = cap.read()
        if not ok or int(cap.get(cv2.CAP_PROP_POS_FRAMES)) != frame+1:
            raise ValueError('bottom reference frame decode mismatch')
    finally:
        cap.release()
    image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    candidates = [g for g in detect_public_tile_geometry(image, frame=frame).candidates
                  if g.geometry_kind == 'bottom_group' and list(g.pixel_bbox) == pin['detector_bbox']]
    if len(candidates) != 1:
        raise ValueError('bottom reference detector candidate drifted')
    boxes, audit = raw_face_boxes(image, candidates[0], body_context=True, seam_context=2)
    if len(boxes) != 3:
        raise ValueError('bottom reference split failed')
    templates = []
    rectified_audit = None
    if rectified:
        from workspace.vision.public_meld_outer_body_probe import rectify_face_quad
        _, rectified_audit = raw_face_boxes(image, candidates[0], face_plane=True, face_plane_outer_edges=True)
        if len(rectified_audit.get('face_quads', ())) != 3:
            raise ValueError('bottom reference quadrilateral detection failed')
    for index, (box, face_pin) in enumerate(zip(boxes, pin['faces'])):
        if list(box) != face_pin['crop_xyxy']:
            raise ValueError('bottom reference crop edges drifted')
        crop = image.crop(box)
        encoded = io.BytesIO()
        crop.save(encoded, format='PNG')
        if hashlib.sha256(encoded.getvalue()).hexdigest() != face_pin['crop_png_sha256']:
            raise ValueError('bottom reference crop SHA mismatch')
        descriptor_crop = rectify_face_quad(image, rectified_audit['face_quads'][index]) if rectified else crop
        face, _ = normalize_single_face(descriptor_crop)
        descriptors = (descriptor_extractor or _sift_descriptors)(face) if face is not None else None
        if descriptors is None:
            raise ValueError('bottom reference descriptors absent')
        templates.append(PublicMeldSiftTemplate(face_pin['tile_id'], 'chunk3_bottom_s234', source_sha,
                                              pin['original_match_group'], descriptors))
    return tuple(templates), {'source_sha256': source_sha, 'source_frame_index': frame,
        'original_match_group': pin['original_match_group'], 'pin_sha256': hashlib.sha256(PIN.read_bytes()).hexdigest(),
        'raw_source_and_crop_hashes_verified': True, 'label_authority': pin['label_authority'],
        'reference_faces': pin['faces'], 'split_audit': audit,
        'full_quad_rectified': rectified, 'rectified_audit': rectified_audit,
        'descriptor_counts': {t.tile_id: len(t.descriptors) for t in templates},
        'development_only': True, 'formal_promotion_evidence': False,
        'safe_for_runtime': False, 'safe_for_hint': False, 'safe_for_executor': False}
