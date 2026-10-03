"""SHA-pinned, reviewed opponent strip as a development reference only."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def source_disjoint_templates(templates, excluded_match_groups, query_source_sha):
    """Exclude all same-match aliases even when source files differ."""
    return [t for t in templates if t.match_group and t.source_sha256
            and t.match_group not in excluded_match_groups
            and t.source_sha256 != query_source_sha]


def load_s123_reference_templates():
    from PIL import Image
    from workspace.vision.evaluate_sift_detector_body_boundary_probe import raw_face_boxes
    from workspace.vision.evaluate_sift_symmetric_geometry_probe import normalize_single_face
    from workspace.vision.public_meld_identity_sift import PublicMeldSiftTemplate, _sift_descriptors
    from workspace.vision.public_tile_detector import PublicGeometryCandidate

    queue_path = Path('references/vision/2026-10-01/opponent_public_meld_review_queue_v0_1.json')
    queue = json.loads(queue_path.read_text())
    item = next(row for row in queue['items'] if row['review_id'] == 'opp_meld_0926_hand1_s123')
    if item['evidence_status'] != 'USER_AND_VIDEO_REVIEW_CONFIRMED' or item['expected_tiles'] != ['S1', 'S2', 'S3']:
        raise ValueError('reviewed opponent label contract drifted')
    strip_path = Path(item['public_strip_path'])
    strip_sha = hashlib.sha256(strip_path.read_bytes()).hexdigest()
    if strip_sha != item['public_strip_sha256'] or strip_sha != '4a3c2b5f125b668ec5ff7ecc1fddf0d41cff241e7968482e11fe34c9e75bc5de':
        raise ValueError('reviewed opponent strip SHA mismatch')
    source_sha = 'fba5f67d244fb5bdc916f24707de288fef939a9444fa66bec21347e52bd64fc3'
    match_group = 'reviewed_match_2026_09_26_first_hand'
    if item['source_sha256'] != source_sha or item['match_group'] != match_group:
        raise ValueError('reviewed source lineage drifted')
    with Image.open(strip_path) as original:
        strip = original.convert('RGB')
    if strip.size != (71, 165):
        raise ValueError('reviewed strip dimensions drifted')
    # Choose the central strip row before query evaluation. It is an ordinal,
    # not a recovered raw-video frame index. Top-seat orientation is fixed.
    group = strip.crop((0, 66, 71, 99)).transpose(Image.Transpose.ROTATE_180)
    candidate = PublicGeometryCandidate((0, 0, 71, 33), (0., 0., 1., 1.), 'bottom_group', 0., 0., None, None)
    boxes, audit = raw_face_boxes(group, candidate, body_context=True, seam_context=2)
    if len(boxes) != 3:
        raise ValueError('reviewed opponent reference no longer splits')
    templates = []
    for tile, box in zip(item['expected_tiles'], boxes):
        face, _ = normalize_single_face(group.crop(box))
        descriptors = _sift_descriptors(face) if face is not None else None
        if descriptors is None:
            raise ValueError('reviewed opponent reference has no descriptors')
        templates.append(PublicMeldSiftTemplate(tile, 'reviewed_opponent_s123_strip', source_sha, match_group, descriptors))
    return tuple(templates), {'strip_sha256': strip_sha, 'source_sha256': source_sha,
        'declared_original_match_group': match_group, 'strip_ordinal': 3,
        'original_source_frame_index': None, 'orientation_degrees': 180,
        'tile_ids': item['expected_tiles'], 'split_audit': audit,
        'descriptor_counts': {t.tile_id: len(t.descriptors) for t in templates},
        'reviewed_strip_exact_hash_verified': True,
        'raw_source_bytes_reverified_in_this_probe': False,
        'source_lineage_status': 'existing_repository_declaration; raw-original-recheck-pending',
        'declared_reference_original_matches': 1, 'development_only': True,
        'formal_promotion_evidence': False, 'safe_for_runtime': False,
        'safe_for_hint': False, 'safe_for_executor': False}
