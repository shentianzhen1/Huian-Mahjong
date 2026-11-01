"""Train a development MobileNet feature classifier on existing tile crops.

Missing source lineage/classes are reported, not training prerequisites. Known
query matches and exact query sources are excluded. No Runtime wiring or score
calibration; candidate margins/cosines are not Runtime confidence.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import time

from workspace.vision.concealed_template_match_lineage import (
    canonicalize_match_group, load_concealed_template_lineage,
)
from workspace.vision.tiles_v0_1.labels import approved_labels
from .concealed_mobilenet_ab import (
    STANDARD_CLASSES, APPEARANCE_AUGMENTATION_VERSION, _appearance_variants, _square_tile_canvas,
    _load_model, _embed_images,
)


def select_rows(labels, lineage, query_shas, query_groups, *, reviewed_only=False):
    selected = []
    counts = Counter()
    for row in labels:
        if row.get('tile_id') not in STANDARD_CLASSES or row.get('gold_skin_only'):
            continue
        if row.get('region') not in ('hand_region', 'draw_region', 'draw_visual', 'gold_region'):
            continue
        sha = row.get('sha256')
        source = lineage.get(sha)
        if sha in query_shas or (source and source.match_group in query_groups):
            counts['excluded_query_source_or_known_match'] += 1
            continue
        if source is None:
            counts['unresolved_lineage_available'] += 1
            if reviewed_only:
                continue
        selected.append(row)
    return selected, dict(counts)


def summarize(rows, key):
    hands = defaultdict(list)
    confusions = Counter()
    concealed = [r for r in rows if r['role'] == 'concealed']
    for r in concealed:
        hands[r['sample_id']].append(r[key] == r['truth'])
        if r[key] != r['truth']:
            confusions[f"{r['truth']}->{r[key]}"] += 1
    gold = [r for r in rows if r['role'] == 'opened_gold']
    return dict(concealed_correct=sum(r[key] == r['truth'] for r in concealed),
                concealed_total=len(concealed), whole_hand_exact=sum(all(x) for x in hands.values()),
                hands=len(hands), opened_gold_correct=sum(r[key] == r['truth'] for r in gold),
                opened_gold_total=len(gold), concealed_confusions=dict(confusions),
                opened_gold_by_cohort={cohort: dict(
                    correct=sum(r[key]==r['truth'] for r in gold if r.get('cohort','replay')==cohort),
                    total=sum(r.get('cohort','replay')==cohort for r in gold))
                    for cohort in sorted({r.get('cohort','replay') for r in gold})})


def load_queries(replay_path, truth_path, video_path, frame_ids):
    import cv2
    from PIL import Image
    replay = json.loads(replay_path.read_text())
    truth = json.loads(truth_path.read_text())
    with video_path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != replay['source_sha256'] or digest != truth['source_sha256']:
        raise ValueError('Video/replay/truth source mismatch')
    truths = {e['frame_index']: e for e in truth['frames']}
    selected = {r['frames'][-1]: r for r in replay['rows'] if r['frames'][-1] in frame_ids}
    if set(selected) != set(frame_ids):
        raise ValueError('Selected replay frame missing')
    images, meta = [], []
    cap = cv2.VideoCapture(str(video_path))
    try:
        index = 0
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            if index in selected:
                row, annotation = selected[index], truths[index]
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                rgb_sha = hashlib.sha256(rgb.tobytes()).hexdigest()
                if rgb_sha != annotation['rgb_sha256'] or rgb_sha != row['pixel_sha256'][-1]:
                    raise ValueError('Query frame RGB mismatch')
                image = Image.fromarray(rgb)
                components = row['identity_observations']['components']
                hand = [c for c in components if c.get('region_candidate') in ('hand', 'draw_visual')]
                gold = [c for c in components if c.get('region_candidate') == 'gold']
                if len(hand) != len(annotation['own_hand']) or len(gold) != 1:
                    raise ValueError('Reviewed query geometry does not match components')
                for slot, (component, tile) in enumerate(zip(hand + gold, annotation['own_hand'] + [annotation['gold_tile']])):
                    x, y, w, h = component['classification_crop_bbox']
                    crop = image.crop((x, y, x+w, y+h))
                    images.append(_square_tile_canvas(crop))
                    meta.append(dict(sample_id=f'{digest[:8]}:{index}', frame_index=index,
                        slot=slot, role='concealed' if slot < len(hand) else 'opened_gold',
                        truth=tile, template=component.get('candidate_tile_id'),
                        crop_rgb_sha256=hashlib.sha256(crop.tobytes()).hexdigest()))
            index += 1
    finally:
        cap.release()
    if len({r['sample_id'] for r in meta}) != len(frame_ids):
        raise ValueError('Could not decode every query frame')
    return images, meta




def load_gold_packet(directory):
    from PIL import Image
    manifest = json.loads((directory / 'manifest.json').read_text())
    images, metadata, sources = [], [], set()
    for source in manifest['sources']:
        for anchor in source['anchors']:
            file = anchor.get('private_packet_crop')
            if not file:
                continue
            path = directory / file
            if hashlib.sha256(path.read_bytes()).hexdigest() != anchor['crop_png_sha256']:
                raise ValueError('Gold packet crop file mismatch')
            with Image.open(path) as original:
                crop = original.convert('RGB')
            if hashlib.sha256(crop.tobytes()).hexdigest() != anchor['crop_rgb_sha256']:
                raise ValueError('Gold packet crop RGB mismatch')
            images.append(_square_tile_canvas(crop))
            sources.add(source['sha256'])
            metadata.append(dict(sample_id=f"gold-packet:{source['sha256'][:8]}:{anchor['frame_index']}",
                frame_index=anchor['frame_index'], slot=0, role='opened_gold', cohort='gold_packet',
                truth=anchor['reviewed_opened_gold'],
                template=anchor['runtime']['candidate_tile_id'],
                crop_rgb_sha256=anchor['crop_rgb_sha256']))
    return images, metadata, sources


def finetune_tail(train_images, train_ids, query_images, *, epochs=10):
    """Fixed ten-epoch supervised tail update; query images never train/select epochs."""
    import numpy as np
    import torch
    from torch import nn
    torch.manual_seed(0)
    model, transform, _ = _load_model()
    prefix = model.features[:8].eval()
    for parameter in prefix.parameters():
        parameter.requires_grad_(False)

    def early_features(images):
        values = []
        with torch.no_grad():
            for start in range(0, len(images), 32):
                batch = torch.stack([transform(im) for im in images[start:start+32]])
                values.append(prefix(batch).detach())
        return torch.cat(values)

    x = early_features(train_images)
    q = early_features(query_images)
    classes = sorted(set(train_ids))
    y = torch.tensor([classes.index(t) for t in train_ids])
    tail = nn.Sequential(model.features[8:], nn.AdaptiveAvgPool2d(1), nn.Flatten(),
                         nn.Linear(576, len(classes)))
    counts = torch.bincount(y, minlength=len(classes)).float()
    criterion = nn.CrossEntropyLoss(weight=len(y)/(len(classes)*counts), label_smoothing=0.05)
    optimizer = torch.optim.AdamW(tail.parameters(), lr=0.001, weight_decay=0.01)
    generator = torch.Generator().manual_seed(0)
    history = []
    for epoch in range(epochs):
        tail.train()
        order = torch.randperm(len(y), generator=generator)
        loss_sum = 0.0
        for indices in order.split(64):
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(tail(x[indices]), y[indices])
            loss.backward()
            optimizer.step()
            loss_sum += float(loss.detach()) * len(indices)
        history.append(dict(epoch=epoch+1, train_loss=round(loss_sum/len(y), 6)))
        print('finetune', history[-1], flush=True)
    tail.eval()
    with torch.no_grad():
        pred = torch.cat([tail(batch).argmax(1) for batch in q.split(64)]).tolist()
        train_pred = torch.cat([tail(batch).argmax(1) for batch in x.split(64)])
    return [classes[i] for i in pred], dict(
        epochs=epochs, frozen_prefix_blocks=8, learned_tail_blocks='8..12',
        optimizer='AdamW lr=0.001 weight_decay=0.01', batch_size=64, seed=0,
        class_balanced_loss=True, label_smoothing=0.05, query_used_for_training=False,
        query_used_for_epoch_selection=False, training_fit_correct=int((train_pred==y).sum()),
        training_variants=len(y), history=history)


def run(args):
    from workspace.vision.tiles_v0_1.evaluate_tiles import _crop_label
    import numpy as np
    import torch
    import sklearn
    from sklearn.svm import LinearSVC
    torch.set_num_threads(4)
    torch.manual_seed(0)
    started = time.perf_counter()
    lineage = load_concealed_template_lineage(args.lineage)
    labels = approved_labels(args.dataset)
    # The short source belongs to Sep26; unknown long-clip lineage is not guessed.
    query_groups = {canonicalize_match_group(g) for g in args.exclude_match}
    query_shas, images, query = set(), [], []
    for replay, truth, video, frames in zip(args.replay, args.truth, args.video, args.frames):
        query_shas.add(json.loads(replay.read_text())['source_sha256'])
        im, metadata = load_queries(replay, truth, video, [int(f) for f in frames.split(',')])
        images.extend(im)
        query.extend(metadata)
    if args.gold_packet:
        im, metadata, sources = load_gold_packet(args.gold_packet)
        images.extend(im)
        query.extend(metadata)
        query_shas.update(sources)
    selected, exclusions = select_rows(labels, lineage, query_shas, query_groups)
    crop_exclusions = json.loads(args.crop_review.read_text())['excluded_training_images'] if args.crop_review else []
    excluded_paths = {r['image'] for r in crop_exclusions}
    for row in crop_exclusions:
        if hashlib.sha256((args.dataset / row['image']).read_bytes()).hexdigest() != row['crop_file_sha256']:
            raise ValueError('Reviewed crop exclusion no longer matches bytes')
    selected = [r for r in selected if r['image'] not in excluded_paths]
    train_images, train_ids, train_sources = [], [], []
    readable, missing = [], []
    for row in selected:
        try:
            crop = _crop_label(args.dataset, row)
        except FileNotFoundError:
            missing.append(row['image'])
            continue
        readable.append(row)
        variants = _appearance_variants(crop)
        train_images.extend(variants)
        train_ids.extend([row['tile_id']] * len(variants))
        train_sources.extend([row.get('sha256')] * len(variants))
    if len(set(train_ids)) < 2:
        raise ValueError('Need at least two trainable classes')
    model, transform, weights = _load_model()
    train_x = _embed_images(train_images, model, transform)
    query_x = _embed_images(images, model, transform)
    policies = {}
    for name, strict in [('development_all_sources', False), ('reviewed_sources_only', True)]:
        keep = np.array([not strict or sha in lineage for sha in train_sources])
        x, y = train_x[keep], np.array(train_ids)[keep]
        if len(set(y)) < 2:
            policies[name] = {'status': 'insufficient_classes', 'class_count': len(set(y))}
            continue
        clf = LinearSVC(C=1.0, class_weight='balanced', random_state=0, max_iter=10000)
        clf.fit(x, y)
        ids = sorted(set(y))
        prototypes = np.stack([x[y == t].mean(axis=0) for t in ids])
        prototypes /= np.maximum(np.linalg.norm(prototypes, axis=1, keepdims=True), 1e-12)
        prototype_pred = [ids[i] for i in np.argmax(query_x @ prototypes.T, axis=1)]
        linear_pred = clf.predict(query_x).tolist()
        results = [dict(r, prototype=p, linear=l) for r,p,l in zip(query, prototype_pred, linear_pred)]
        policies[name] = dict(class_count=len(ids), missing_classes=sorted(STANDARD_CLASSES-set(ids)),
            training_crops=sum(not strict or r.get('sha256') in lineage for r in readable),
            training_variants=len(y), training_fit_correct=int(sum(clf.predict(x)==y)),
            training_unresolved_source_shas=sorted({s for s in np.array(train_sources)[keep] if s not in lineage}),
            template=summarize(results, 'template'), prototype=summarize(results, 'prototype'),
            linear=summarize(results, 'linear'), results=results)
    if args.finetune:
        predictions, training = finetune_tail(train_images, train_ids, images)
        results = [dict(r, finetuned=p) for r, p in zip(query, predictions)]
        policies['development_supervised_tail'] = dict(training=training,
            finetuned=summarize(results, 'finetuned'), results=results)
    return dict(schema_version='sampled_replay_mobilenet_linear_ab_v0_1',
        development_only=True, formal_promotion_evidence=False, safe_for_runtime=False,
        safe_for_executor=False, automatic_advice_improvement_measured=False,
        candidate_scores_calibrated=False, runtime_threshold_unchanged=0.82,
        pretrained_weights=weights, classifier='LinearSVC C=1 class_weight=balanced seed=0',
        augmentation='existing concealed_mobilenet_ab nine deterministic variants',
        augmentation_version=APPEARANCE_AUGMENTATION_VERSION,
        torch_version=torch.__version__, sklearn_version=sklearn.__version__,
        query_sources=sorted(query_shas), known_query_matches_excluded=sorted(query_groups),
        query_scope='Revealed sampled states and optional same-match Gold packet; UNKNOWN long original-match group; no holdout claim',
        reviewed_training_crop_exclusions=crop_exclusions,
        selection=exclusions, missing_training_files=missing,
        elapsed_seconds=round(time.perf_counter()-started, 3), policies=policies)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('replay', 'truth', 'video'):
        parser.add_argument('--'+flag, type=Path, action='append', required=True)
    parser.add_argument('--frames', action='append', required=True)
    parser.add_argument('--exclude-match', action='append', default=[])
    parser.add_argument('--dataset', type=Path, default=Path('dataset/tiles_runtime_v0_2'))
    parser.add_argument('--lineage', type=Path, default=Path('references/vision/2026-10-01/concealed_template_match_lineage.development.json'))
    parser.add_argument('--gold-packet', type=Path)
    parser.add_argument('--crop-review', type=Path)
    parser.add_argument('--finetune', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if len({len(args.replay), len(args.truth), len(args.video), len(args.frames)}) != 1:
        parser.error('Repeat replay/truth/video/frames equally')
    result = run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'policies'}))
    for name, p in result['policies'].items():
        print(name, json.dumps({k:v for k,v in p.items() if k != 'results'}))


if __name__ == '__main__':
    main()
