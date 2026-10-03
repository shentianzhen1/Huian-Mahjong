"""Development factorial: detector ROI -> tight body -> raw seam-context faces.

The pinned ROI selects the audit target only. No pinned boundary is used to
construct a candidate crop. This previously inspected batch is not a holdout.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path


def raw_face_boxes(image, candidate, *, body_context=False, seam_context=2, outer_body=False, face_plane=False, face_plane_outer_edges=False):
    """Geometry-only experimental adapter. Abstain on stacked/rotated rows."""
    from workspace.vision.public_meld_geometry_normalization import normalize_public_meld_crop, FLAT
    if seam_context < 0:
        raise ValueError("negative seam context")
    if sum((body_context, outer_body, face_plane)) > 1:
        raise ValueError("choose one body boundary mode")
    if face_plane_outer_edges and not face_plane:
        raise ValueError('outer face edges require face-plane mode')
    normalized = normalize_public_meld_crop(image, candidate)
    a = normalized.analysis
    if a.stack_state != FLAT or abs(a.rotation_degrees) > .01 or a.tight_bbox_in_group is None:
        return (), {'reason': 'requires_unrotated_flat_body'}
    x, y, w, h = candidate.pixel_bbox
    if face_plane:
        import math
        from workspace.vision.public_meld_outer_body_probe import face_plane_quads
        quads, audit = face_plane_quads(image, candidate.pixel_bbox, seam_context=seam_context, fit_outer_edges=face_plane_outer_edges, light_body_only=face_plane_outer_edges)
        boxes = tuple((math.floor(min(p[0] for p in q)), math.floor(min(p[1] for p in q)),
                       math.ceil(max(p[0] for p in q))+1, math.ceil(max(p[1] for p in q))+1) for q in quads)
        return boxes, {**audit, 'face_xyxy': boxes}
    outer_audit = None
    if outer_body:
        from workspace.vision.public_meld_outer_body_probe import outer_body_box
        box, outer_audit = outer_body_box(image, candidate.pixel_bbox)
        if box is None:
            return (), outer_audit
        x, top, right, bottom = box
        w, pad = right-x, 0
    elif body_context:
        tx, ty, w, h = a.tight_bbox_in_group
        x, y = x+tx, y+ty
        pad = max(1, round(h*.025))
        top, bottom = max(0, y-pad), min(image.height, y+h+pad)
    else:
        pad = 0
        top, bottom = y, y+h
    cuts = [round(w*i/3) for i in range(4)]
    boxes = tuple((x+max(0,cuts[i]-(seam_context if i else 0)), top,
                   x+min(w,cuts[i+1]+(seam_context if i<2 else 0)), bottom)
                  for i in range(3))
    return boxes, {'detector_bbox': list(candidate.pixel_bbox),
        'tight_bbox_in_group': list(a.tight_bbox_in_group), 'vertical_context': pad,
        'raw_group_xyxy': [x, top, x+w, bottom], 'face_xyxy': boxes,
        'geometry': a.to_dict(), 'outer_body_probe': outer_audit}


def evaluate(video_path, private_template_zip, *, spec_file='references/vision/2026-10-03/hand8_s789_harvest_spec_v0_1.json', source_index=0, group_index=0, reference_geometry=False, opponent_s123_reference=False, bottom_reference_video=None, bottom_reference_rectified=False):
    import cv2
    import numpy as np
    from PIL import Image
    if bottom_reference_rectified and bottom_reference_video is None:
        raise ValueError('rectified bottom reference requires source video')
    from workspace.vision.public_identity_labels import load_public_identity_manifest
    from workspace.vision.public_meld_identity_sift import build_public_meld_sift_bank, _sift_descriptors
    from workspace.vision.public_meld_private_sift_loader import augment_public_meld_sift_bank_from_private_zip
    from workspace.vision.evaluate_sift_symmetric_geometry_probe import normalize_single_face
    from workspace.vision.evaluate_sift_group_split_geometry_probe import frozen_score
    from workspace.vision.public_tile_detector import detect_public_tile_geometry, target_coverage
    spec_path = Path(spec_file)
    spec = json.loads(spec_path.read_text()); source = spec['sources'][source_index]; group = source['groups'][group_index]
    digest = hashlib.sha256(Path(video_path).read_bytes()).hexdigest()
    if digest != source['source_sha256']:
        raise ValueError('source SHA mismatch')
    manifest = load_public_identity_manifest('references/vision/2026-09-22/public_identity_labels_v0_1.json')
    from contextlib import ExitStack
    from unittest.mock import patch
    from workspace.vision import public_meld_identity_sift as identity, public_meld_private_sift_loader as loader
    original_loader_extractor = loader._sift_descriptors
    def reference_descriptors(image):
        normalized, _ = normalize_single_face(image)
        return _sift_descriptors(normalized) if normalized is not None else None
    with ExitStack() as stack:
        if reference_geometry:
            stack.enter_context(patch.object(identity, '_sift_descriptors', reference_descriptors))
            stack.enter_context(patch.object(loader, '_sift_descriptors', reference_descriptors))
        bank = build_public_meld_sift_bank(manifest, Path('.'), Path('references/vision/2026-09-24/public_identity_source_groups.development.json'))
        bank, loaded = augment_public_meld_sift_bank_from_private_zip(bank, private_zip_path=private_template_zip,
            recovery_result_path='references/vision/2026-10-02/public_meld_private_recovery_result_v0_3.json', repository_root=Path('.'))
    if identity._sift_descriptors is not _sift_descriptors or loader._sift_descriptors is not original_loader_extractor:
        raise RuntimeError('reference extractor was not restored')
    aliases = set(spec['excluded_same_match_aliases'])
    from workspace.vision.public_meld_opponent_reference_probe import source_disjoint_templates
    templates = source_disjoint_templates(bank.templates, aliases, digest)
    reference_supplement = None
    if opponent_s123_reference:
        if not reference_geometry:
            raise ValueError('opponent reference requires symmetric reference geometry')
        from workspace.vision.public_meld_opponent_reference_probe import load_s123_reference_templates
        supplement, reference_supplement = load_s123_reference_templates()
        admitted = source_disjoint_templates(supplement, aliases, digest)
        templates.extend(admitted)
        reference_supplement['admitted_tile_ids_after_source_exclusion'] = [t.tile_id for t in admitted]
        reference_supplement['admitted_original_match_count'] = len({t.match_group for t in admitted})
    bottom_supplement = None
    if bottom_reference_video is not None:
        if not reference_geometry:
            raise ValueError('bottom reference requires symmetric reference geometry')
        from workspace.vision.public_meld_bottom_reference_probe import load_bottom_s234_templates
        supplement, bottom_supplement = load_bottom_s234_templates(bottom_reference_video, rectified=bottom_reference_rectified)
        admitted = source_disjoint_templates(supplement, aliases, digest)
        templates.extend(admitted)
        bottom_supplement['admitted_tile_ids_after_source_exclusion'] = [t.tile_id for t in admitted]
        bottom_supplement['admitted_original_match_count'] = len({t.match_group for t in admitted})
    modes = {'detector_seam2': (False,2,False,False), 'body_context_no_seam': (True,0,False,False), 'body_context_seam2': (True,2,False,False), 'outer_body_seam2': (False,2,True,False), 'face_plane_seam_boxes': (False,2,False,True), 'face_plane_seam_rectified': (False,2,False,True), 'face_plane_full_rectified': (False,2,False,True)}
    cap = cv2.VideoCapture(str(video_path)); rows=[]
    try:
        for frame in group['frame_indices']:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame); ok,bgr=cap.read()
            if not ok or int(cap.get(cv2.CAP_PROP_POS_FRAMES)) != frame+1:
                raise ValueError('frame decode mismatch')
            image=Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB))
            # Manual target is an audit association, never a crop boundary.
            boxes=group['face_bboxes']; left=min(b[0] for b in boxes); top=min(b[1] for b in boxes)
            right=max(b[0]+b[2] for b in boxes); bottom=max(b[1]+b[3] for b in boxes)
            target=(left/image.width,top/image.height,(right-left)/image.width,(bottom-top)/image.height)
            candidates=[g for g in detect_public_tile_geometry(image,frame=frame).candidates
                if g.geometry_kind=='bottom_group' and target_coverage(g.normalized_bbox,target)>.5]
            if len(candidates)!=1:
                raise ValueError('audit candidate association absent or ambiguous')
            for mode,(body,seam,outer,plane) in modes.items():
                crops,audit=raw_face_boxes(image,candidates[0],body_context=body,seam_context=seam,outer_body=outer,face_plane=plane,face_plane_outer_edges=mode=='face_plane_full_rectified')
                ranked=[]
                for index,box in enumerate(crops):
                    if mode in ('face_plane_seam_rectified', 'face_plane_full_rectified'):
                        from workspace.vision.public_meld_outer_body_probe import rectify_face_quad
                        crop = rectify_face_quad(image, audit['face_quads'][index])
                    else:
                        crop = image.crop(box)
                    face,_=normalize_single_face(crop); query=_sift_descriptors(face) if face is not None else None
                    scores={}
                    best_references={}
                    for t in templates:
                        score=frozen_score(query,t.descriptors)
                        if score is not None:
                            if score > scores.get(t.tile_id,float('-inf')):
                                scores[t.tile_id]=score
                                best_references[t.tile_id]=t
                    ranking=sorted(scores.items(),key=lambda p:(-p[1],p[0]))
                    expected_tile=(group.get('reviewed_candidate_tiles') or [group['reviewed_candidate_tile']]*3)[index]
                    from workspace.vision.sift_match_multiplicity_probe import match_multiplicity
                    diagnostic_tiles={expected_tile}
                    if ranking:
                        diagnostic_tiles.add(ranking[0][0])
                    ranked.append({'top1':ranking[0][0] if ranking else None,'scores':ranking,
                        'match_diagnostics': {tile:{**match_multiplicity(query,best_references[tile].descriptors),
                            'reference_match_group':best_references[tile].match_group,
                            'reference_source_sha256':best_references[tile].source_sha256} for tile in sorted(diagnostic_tiles) if tile in best_references}})
                winners=[r['top1'] for r in ranked]
                expected=group.get('reviewed_candidate_tiles') or [group['reviewed_candidate_tile']]*3
                supported = [tile in dict(r['scores']) for tile,r in zip(expected,ranked)]
                rows.append({'frame':frame,'group_id':group['group_id'],'mode':mode,'audit':audit,'rankings':ranked,
                    'expected_classes_supported': supported,
                    'scorable_faces':sum(supported),
                    'group_scorable':len(supported)==3 and all(supported),
                    'correct_faces':sum(a==b for a,b in zip(winners,expected)),
                    'exact_group_correct':winners==expected,'scored_faces':len(ranked)})
    finally:
        cap.release()
    summary={mode:{'correct_faces':sum(r['correct_faces'] for r in rows if r['mode']==mode),
        'faces':3*len(group['frame_indices']),
        'scorable_faces':sum(r['scorable_faces'] for r in rows if r['mode']==mode),
        'scorable_groups':sum(r['group_scorable'] for r in rows if r['mode']==mode),
        'exact_groups_correct':sum(r['exact_group_correct'] for r in rows if r['mode']==mode),'groups':len(group['frame_indices'])} for mode in modes}
    return {'schema_version':'sift_detector_body_boundary_probe_dev_v0_5','source_sha256':digest,
        'summary':summary,'rows':rows,'private_template_load':loaded,
        'reference_geometry_normalized': reference_geometry,
        'opponent_reference_supplement': reference_supplement,
        'bottom_reference_supplement': bottom_supplement,
        'query_geometry_normalized': True, 'scorer_changed': False,
        'dependency_versions':{'opencv':cv2.__version__,'numpy':np.__version__},
        'input_sha256':{str(spec_path):hashlib.sha256(spec_path.read_bytes()).hexdigest(),
            'private_template_zip':hashlib.sha256(Path(private_template_zip).read_bytes()).hexdigest()},
        'manual_roi_used_only_for_audit_target_association':True,'crop_edges_depend_on_manual_roi':False,
        'parameter_selected_after_viewing_development_batch':True,'independent_match_groups':1,
        'development_only':True,'formal_promotion_evidence':False,'runtime_integration':False,
        'safe_for_runtime':False,'safe_for_hint':False,'safe_for_executor':False,
        'decision':'development_comparison_only; assess_reference_transform_symmetry_before_attributing_identity_failure_to_crop'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--video',required=True);p.add_argument('--private-template-zip',required=True);p.add_argument('--output',required=True);p.add_argument('--reference-geometry',action='store_true')
    p.add_argument('--spec-file', default='references/vision/2026-10-03/hand8_s789_harvest_spec_v0_1.json')
    p.add_argument('--source-index', type=int, default=0)
    p.add_argument('--group-index', type=int, default=0)
    p.add_argument('--opponent-s123-reference', action='store_true')
    p.add_argument('--bottom-reference-video')
    p.add_argument('--bottom-reference-rectified', action='store_true')
    args=p.parse_args();result=evaluate(args.video,args.private_template_zip,reference_geometry=args.reference_geometry,
        spec_file=args.spec_file, source_index=args.source_index, group_index=args.group_index,
        opponent_s123_reference=args.opponent_s123_reference, bottom_reference_video=args.bottom_reference_video,
        bottom_reference_rectified=args.bottom_reference_rectified)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['summary']))
