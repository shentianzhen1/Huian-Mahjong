"""Offline development comparison; no Runtime imports or production promotion."""
import argparse
from collections import defaultdict
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageFilter


def main():
    import torch
    import torchvision
    from torchvision.models import mobilenet_v3_small, MobileNet_V3_Small_Weights
    from workspace.vision.public_identity_labels import load_public_identity_manifest, approved_labels, pixel_bbox, verify_repository_files
    from workspace.vision.public_identity_shadow_v0_2 import load_development_sources
    from workspace.vision.public_meld_identity_sift import build_public_meld_sift_bank
    from workspace.vision.public_meld_private_sift_loader import augment_public_meld_sift_bank_from_private_zip
    from workspace.vision.public_meld_private_recovery_result import load_private_recovery_results, RecoveredPrivateTemplate

    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'private-zip', 'recovery', 'query-dir', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--canvas-policy', choices=('native', 'canonical'), default='native')
    args = parser.parse_args()
    root = Path(args.root)
    manifest = load_public_identity_manifest(root / 'references/vision/2026-09-22/public_identity_labels_v0_1.json')
    registry = root / 'references/vision/2026-09-24/public_identity_source_groups.development.json'
    assert not verify_repository_files(manifest, root)
    bank = build_public_meld_sift_bank(manifest, root, registry)
    bank, _ = augment_public_meld_sift_bank_from_private_zip(bank, private_zip_path=args.private_zip, recovery_result_path=args.recovery, repository_root=root)
    excluded = {'reviewed_match_2026_09_26_first_hand', 'reviewed_match_2026_09_26_eight_hand'}
    sources = load_development_sources(registry)
    images = []
    for label in approved_labels(manifest):
        group = sources[label.source_session].match_group
        if label.region != 'public_meld' or group in excluded:
            continue
        image = Image.open(root / label.image_path).convert('RGB')
        x, y, w, h = pixel_bbox(label, image.size)
        images.append((label.tile_id, group, image.crop((x, y, x+w, y+h))))
    recovered = [x for x in load_private_recovery_results(args.recovery).values() if isinstance(x, RecoveredPrivateTemplate)]
    with ZipFile(args.private_zip) as archive:
        payload = json.loads(archive.read('private_approved_labels.json'))
        for item in recovered:
            if item.match_group in excluded:
                continue
            group = next(g for g in payload['groups'] if g['video_sha256'] == item.source_sha256 and g['frame_index'] == item.frame_index and tuple(f['crop_sha256'] for f in g['faces']) == item.crop_sha256)
            for face in group['faces']:
                data = archive.read('approved_faces/' + face['crop_file'])
                assert hashlib.sha256(data).hexdigest() == face['crop_sha256']
                images.append((face['approved_tile_id'], item.match_group, Image.open(io.BytesIO(data)).convert('RGB')))
    support = defaultdict(set)
    for tile, group, _ in images:
        support[tile].add(group)
    classes = sorted(tile for tile, groups in support.items() if len(groups) >= 2)
    images = [row for row in images if row[0] in classes]
    torch.manual_seed(69)
    torch.set_num_threads(2)
    weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1
    model = mobilenet_v3_small(weights=weights)
    model.classifier = torch.nn.Identity()
    model.eval()
    model.requires_grad_(False)
    transform = weights.transforms()

    def canvas(image):
        image = image.copy()
        if args.canvas_policy == 'canonical':
            scale = min(160 / image.width, 192 / image.height)
            image = image.resize((max(1, round(image.width*scale)), max(1, round(image.height*scale))), Image.Resampling.BICUBIC)
        else:
            image.thumbnail((160, 192), Image.Resampling.BICUBIC)
        result = Image.new('RGB', (224, 224), 'white')
        result.paste(image, ((224-image.width)//2, (224-image.height)//2))
        return result

    train, labels = [], []
    for tile, _, image in images:
        for size in (None, (24, 27), (32, 36)):
            for blur in (0.0, 0.5):
                variant = image if size is None else image.resize(size, Image.Resampling.BICUBIC)
                if blur:
                    variant = variant.filter(ImageFilter.GaussianBlur(blur))
                train.append(transform(canvas(variant)))
                labels.append(classes.index(tile))
    with torch.no_grad():
        features = torch.cat([model(torch.stack(train[i:i+32])) for i in range(0, len(train), 32)])
        features = torch.nn.functional.normalize(features, dim=1)
    head = torch.nn.Linear(features.shape[1], len(classes))
    optimizer = torch.optim.Adam(head.parameters(), lr=0.01, weight_decay=0.01)
    targets = torch.tensor(labels)
    counts = torch.bincount(targets, minlength=len(classes)).float()
    criterion = torch.nn.CrossEntropyLoss(weight=counts.reciprocal())
    for _ in range(200):
        optimizer.zero_grad()
        loss = criterion(head(features), targets)
        loss.backward()
        optimizer.step()
    query_dir = Path(args.query_dir)
    queries = [('hand1_P6', 'P6', Image.open(query_dir/'first_hand_174s_p6.jpg').convert('RGB')), ('hand1_S4', 'S4', Image.open(query_dir/'first_hand_174s_s4.jpg').convert('RGB'))]
    meld = Image.open(query_dir/'round8_new_meld_normalized.png').convert('RGB')
    cuts = [0, round(meld.width/3), round(2*meld.width/3), meld.width]
    for i, tile in enumerate(('P9', 'P8', 'P7')):
        queries.append(('round8_'+tile, tile, meld.crop((cuts[i], 0, cuts[i+1], meld.height))))
    rows = []
    with torch.no_grad():
        for name, truth, image in queries:
            embedding = torch.nn.functional.normalize(model(transform(canvas(image)).unsqueeze(0)), dim=1)
            scores = head(embedding)[0]
            order = scores.argsort(descending=True).tolist()
            group_scores = defaultdict(dict)
            for index, (tile, group, _) in enumerate(images):
                similarity = torch.dot(embedding[0], features[index*6]).item()
                group_scores[tile][group] = max(similarity, group_scores[tile].get(group, -2.0))
            prototype_ranking = sorted([(tile, sorted(groups.values(), reverse=True)[1]) for tile, groups in group_scores.items() if len(groups) >= 2], key=lambda item: (-item[1], item[0]))
            rows.append({'query_id': name, 'expected_tile': truth, 'expected_class_eligible': truth in classes, 'top1_tile': classes[order[0]], 'top1_correct': classes[order[0]] == truth, 'untrained_embedding_top1': prototype_ranking[0][0], 'untrained_embedding_correct': prototype_ranking[0][0] == truth, 'ranked_logits': [{'tile_id': classes[i], 'logit': round(scores[i].item(), 6)} for i in order]})
    report = {'schema_version': 'public_meld_linear_head_development_v0_1', 'model': 'mobilenet_v3_small_imagenet1k_v1', 'backbone_frozen': True, 'trained_component': 'linear_head_only', 'seed': 69, 'epochs': 200, 'learning_rate': 0.01, 'weight_decay': 0.01, 'classes': classes, 'original_training_faces': len(images), 'augmented_training_faces': len(train), 'training_augmentation': {'sizes': [None, [24, 27], [32, 36]], 'blur_sigma': [0.0, 0.5]}, 'query_original_match_excluded_from_training': True, 'query_group_count': 1, 'query_pixels_used_in_training': False, 'previously_inspected_development_queries': True, 'rows': rows, 'correct': sum(r['top1_correct'] for r in rows), 'query_count': len(rows), 'torch_version': torch.__version__, 'torchvision_version': torchvision.__version__, 'scores_are_calibrated_probabilities': False, 'development_only': True, 'formal_promotion_evidence': False, 'changes_runtime_behavior': False, 'safe_for_runtime': False, 'safe_for_hint': False, 'safe_for_executor': False}
    report['untrained_embedding_correct'] = sum(r['untrained_embedding_correct'] for r in rows)
    report['canvas_policy'] = args.canvas_policy
    report['pretrained_weight_sha256'] = hashlib.sha256((Path(torch.hub.get_dir())/'checkpoints/mobilenet_v3_small-047dcff4.pth').read_bytes()).hexdigest()
    report['query_file_sha256'] = {name: hashlib.sha256((query_dir/name).read_bytes()).hexdigest() for name in ('first_hand_174s_p6.jpg', 'first_hand_174s_s4.jpg', 'round8_new_meld_normalized.png')}
    Path(args.output).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print([(r['query_id'], r['top1_tile']) for r in rows])


if __name__ == '__main__':
    main()
