"""Private development probe: uploaded 42-cell artwork vs recovered meld faces."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
from io import BytesIO
import json
from pathlib import Path
import zipfile

from .development_asset_intake import CLIENT_TILES, STANDARD_TILES
from .concealed_template_match_lineage import load_concealed_template_lineage, qualify_concealed_template_labels, verify_lineage_evidence_paths


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def load_candidates(packet, repository):
    from PIL import Image

    root = Path(repository).resolve()
    faces = []
    with zipfile.ZipFile(packet) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names):
            raise ValueError('duplicate packet entry')
        manifest = json.loads(archive.read('candidate_manifest.json'))
        if (manifest.get('schema_version') != 'huian_redecoded_meld_candidates_v0_1'
                or manifest.get('development_only') is not True
                or manifest.get('legacy_approved_packet_reconstructed') is not False
                or any(manifest.get(k) is not False for k in ('formal_promotion_evidence', 'safe_for_runtime', 'safe_for_hint', 'safe_for_executor'))):
            raise ValueError('expected development-only redecoded candidate packet')
        evidence = (root / manifest['prior_label_evidence_path']).resolve()
        if not evidence.is_relative_to(root) or _sha(evidence.read_bytes()) != manifest['prior_label_evidence_sha256']:
            raise ValueError('prior reviewed label evidence mismatch')
        prior = {row['recovery_id']: row for row in json.loads(evidence.read_text(encoding='utf-8'))['items']}
        used, group_ids = set(), set()
        for group in manifest['groups']:
            if group['group_id'] in group_ids:
                raise ValueError('duplicate candidate group')
            group_ids.add(group['group_id'])
            old = prior.get(group['group_id'])
            if (old is None or old.get('status') != 'PRIVATE_TEMPLATE_EVIDENCE_RECOVERED'
                    or old['source_sha256'] != group['source_sha256'] or old['match_group'] != group['match_group']
                    or old['frame_index'] != group['decoded_frame_index'] or len(old['faces']) != len(group['faces'])):
                raise ValueError('candidate group does not bind to prior reviewed source/frame')
            for original, face in zip(old['faces'], group['faces']):
                if (face['crop_file'] in used or face.get('runtime_admission') is not False
                        or face['tile_id_from_existing_human_label'] != original['tile_id']
                        or face['bbox'] != original['bbox'] or face['legacy_crop_sha256'] != original['crop_sha256']):
                    raise ValueError('candidate crop conflicts with prior reviewed label')
                used.add(face['crop_file'])
                raw = archive.read(face['crop_file'])
                if _sha(raw) != face['crop_file_sha256']:
                    raise ValueError('candidate PNG hash mismatch')
                with Image.open(BytesIO(raw)) as source:
                    image = source.convert('RGB')
                if list(image.size) != face['size'] or _sha(image.tobytes()) != face['raw_rgb_sha256']:
                    raise ValueError('candidate decoded RGB identity mismatch')
                faces.append({'group_id': group['group_id'], 'tile_id': original['tile_id'],
                    'source_sha256': group['source_sha256'], 'match_group': group['match_group'],
                    'crop_sha256': face['crop_file_sha256'], 'image': image})
    if not faces:
        raise ValueError('candidate packet contains no reviewed faces')
    return faces, manifest


def artwork_cells(path, expected_sha):
    from PIL import Image

    raw = Path(path).read_bytes()
    if _sha(raw) != expected_sha:
        raise ValueError('uploaded artwork sheet hash mismatch')
    with Image.open(BytesIO(raw)) as source:
        image = source.convert('RGB')
    if image.size != (900, 720):
        raise ValueError('expected reviewed 900x720 42-cell sheet layout')
    # 9 columns / 100 pixels, 140-pixel rows. The bottom captions are excluded.
    # This layout was inspected on the uploaded sheet before query scoring.
    return {tile: image.crop(((i % 9) * 100, (i // 9) * 140,
                             (i % 9 + 1) * 100, (i // 9) * 140 + 108))
            for i, tile in enumerate(CLIENT_TILES)}


def _rank_sift(image, bank):
    from .public_meld_identity_sift import _descriptor_similarity, _sift_descriptors

    query = _sift_descriptors(image)
    scores = {}
    for tile, descriptors in bank.items():
        values = [_descriptor_similarity(query, other) for other in descriptors]
        usable = [score for score in values if score is not None]
        if usable:
            scores[tile] = max(usable)
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return {'tile': ranked[0][0] if ranked else None, 'score': ranked[0][1] if ranked else None}


def probe(sheet, sheet_sha, packet, dataset, lineage, repository):
    from PIL import Image
    from .tiles_v0_1.labels import approved_labels
    from .tiles_v0_1.template_classifier import TemplateTileClassifier, _feature
    from .public_meld_identity_sift import _sift_descriptors
    from .public_meld_synthetic_transfer import render_self_meld_variants

    cells = artwork_cells(sheet, sheet_sha)
    queries, manifest = load_candidates(packet, repository)
    groups = {row['match_group'] for row in queries}
    if len(groups) != 1:
        raise ValueError('this narrow probe expects one original query match')
    labels = [row for row in approved_labels(dataset) if row.get('region') in {'hand_region','draw_region','draw_visual'}
              and not row.get('gold_skin_only') and row.get('tile_id') in STANDARD_TILES]
    registry = load_concealed_template_lineage(lineage)
    if verify_lineage_evidence_paths(registry, repository):
        raise ValueError('training lineage evidence is missing or outside repository')
    training, selection = qualify_concealed_template_labels(labels, registry, query_match_group=next(iter(groups)))
    query_shas = {row['source_sha256'] for row in queries}
    training = [row for row in training if row['sha256'] not in query_shas]
    art_features = {tile: [_feature(image, region='hand_region')] for tile, image in cells.items() if tile in STANDARD_TILES}
    art = TemplateTileClassifier(art_features)
    real_sift, art_sift, rendered_sift = defaultdict(list), defaultdict(list), defaultdict(list)
    real_hashes = {}
    for row in training:
        root = Path(dataset).resolve()
        path = (root / row['image']).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('real training image escapes dataset or is missing')
        digest = _sha(path.read_bytes())
        if row.get('asset_sha256') and digest != row['asset_sha256']:
            raise ValueError('real training asset hash mismatch')
        real_hashes[row['image']] = digest
        with Image.open(path) as source:
            crop = source.convert('RGB')
            if Path(row['image']).parts[0] != 'templates':
                x,y,w,h = row['bbox']; crop = crop.crop((x,y,x+w,y+h))
        real_sift[row['tile_id']].append(_sift_descriptors(crop))
    real = TemplateTileClassifier.from_labels(dataset, training) if training else None
    for tile, image in cells.items():
        if tile not in STANDARD_TILES:
            continue
        art_sift[tile].append(_sift_descriptors(image))
        rendered_sift[tile].extend(_sift_descriptors(v) for v in render_self_meld_variants(image))
    fused = {tile: list(real_sift.get(tile, [])) + list(rendered_sift.get(tile, [])) for tile in STANDARD_TILES}
    variants = ('real_hand_ncc', 'artwork_ncc', 'real_hand_sift', 'artwork_sift', 'rendered_artwork_sift', 'fused_sift')
    rows = []
    for q in queries:
        a = real.classify(q['image']) if real else None
        b = art.classify(q['image'])
        rows.append({'group_id':q['group_id'], 'truth_tile':q['tile_id'], 'crop_sha256':q['crop_sha256'],
            'real_hand_ncc':{'tile':a.tile_id if a else None,'score':a.confidence if a else None}, 'artwork_ncc':{'tile':b.tile_id,'score':b.confidence},
            'real_hand_sift':_rank_sift(q['image'],real_sift), 'artwork_sift':_rank_sift(q['image'],art_sift),
            'rendered_artwork_sift':_rank_sift(q['image'],rendered_sift), 'fused_sift':_rank_sift(q['image'],fused),
            'runtime_tile_id':'UNKNOWN'})
    group_ids = sorted({row['group_id'] for row in rows})
    metrics = {variant:{'correct_faces':sum(row[variant]['tile']==row['truth_tile'] for row in rows),
        'total_faces':len(rows), 'exact_groups':sum(all(r[variant]['tile']==r['truth_tile'] for r in rows if r['group_id']==group) for group in group_ids),
        'total_groups':len(group_ids)} for variant in variants}
    import cv2,numpy,PIL
    return {'schema_version':'uploaded_artwork_redecoded_meld_probe_development_v0_1',
        'sheet_sha256':sheet_sha,'packet_sha256':_sha(Path(packet).read_bytes()),
        'prior_label_evidence_sha256':manifest['prior_label_evidence_sha256'], 'artwork_classes':34,'flowers_excluded':8,
        'lineage_registry_sha256':_sha(Path(lineage).read_bytes()),'real_template_sha256':real_hashes,
        'query_original_match_groups':sorted(groups),'query_source_count':len(query_shas),
        'training_selection':selection,'qualified_real_training_templates':len(training),
        'query_geometry':'existing reviewed crops; not automatic detector-path acceptance',
        'independent_holdout':False,'original_video_pixel_audit_repeated_here':False,
        'variants_predeclared':list(variants),'scores_calibrated_as_runtime_confidence':False,
        'metrics':metrics,'rows':rows,'environment':{'opencv':cv2.__version__,'numpy':numpy.__version__,'pillow':PIL.__version__},
        'runtime_changed':False,'formal_promotion_evidence':False,'safe_for_runtime':False,'safe_for_hint':False,'safe_for_executor':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for option in ('sheet','sheet-sha256','packet','dataset','lineage','repository-root','output'):
        parser.add_argument('--'+option,required=True)
    args=parser.parse_args()
    result=probe(args.sheet,args.sheet_sha256,args.packet,args.dataset,args.lineage,args.repository_root)
    with Path(args.output).open('x',encoding='utf-8') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(result['metrics']))


if __name__=='__main__': main()
