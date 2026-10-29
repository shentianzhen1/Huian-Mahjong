"""Explicit development training exclusions; never a default Runtime policy.

Build a new resource dictionary from a byte-verified review registry. Both the
classifier and its coverage facts use the same remaining labels. Approved
labels, input resources and files are untouched.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def validate_reviewed_training_exclusions(resources, registry_path):
    """Validate review dependencies without building a classifier (cache-safe)."""
    path = Path(registry_path)
    raw = path.read_bytes()
    review = json.loads(raw)
    if (review.get('development_only') is not True
            or review.get('changes_runtime_labels') is not False
            or review.get('review_authority') != 'ASSISTANT_VISUAL_REVIEW_REVEALED_DEVELOPMENT'):
        raise ValueError('Require an explicit development crop-review registry')
    entries = review.get('excluded_training_images')
    if not isinstance(entries, list) or not entries:
        raise ValueError('Require nonempty reviewed crop exclusions')
    root = Path(resources['root']).resolve()
    labels = resources['labels']
    by_image = {}
    for label in labels:
        by_image.setdefault(label['image'], []).append(label)
    excluded = set()
    for entry in entries:
        name = entry.get('image')
        if not isinstance(name, str) or not name or name in excluded:
            raise ValueError('Invalid or duplicate reviewed crop path')
        relative = Path(name)
        target = (root / relative).resolve()
        if relative.is_absolute() or '..' in relative.parts or not target.is_relative_to(root):
            raise ValueError('Reviewed crop must be inside dataset root')
        matches = by_image.get(name, ())
        if not matches:
            raise ValueError('Reviewed crop is absent from dataset labels')
        if any(label.get('tile_id') != entry.get('tile_id')
               or label.get('sha256') != entry.get('source_sha256') for label in matches):
            raise ValueError('Reviewed crop label/source mismatch')
        digest = entry.get('crop_file_sha256')
        if (not isinstance(digest, str) or len(digest) != 64
                or hashlib.sha256(target.read_bytes()).hexdigest() != digest):
            raise ValueError('Reviewed crop byte hash mismatch')
        excluded.add(name)
    return excluded, hashlib.sha256(raw).hexdigest()


def with_reviewed_training_exclusions(resources, registry_path):
    from .runtime_reader import _coverage, _gold_skin_covered_classes
    from workspace.vision.tiles_v0_1.template_classifier import TemplateTileClassifier

    excluded, registry_digest = validate_reviewed_training_exclusions(resources, registry_path)
    labels = resources['labels']
    root = Path(resources['root']).resolve()
    training = [row for row in resources['training_labels'] if row['image'] not in excluded]
    remaining = [row for row in labels if row['image'] not in excluded]
    covered, regions, cross_session = _coverage(training)
    return {
        **resources,
        'labels': remaining,
        'training_labels': training,
        'covered': covered,
        'covered_by_region': regions,
        'cross_session': cross_session,
        'gold_skin_covered': _gold_skin_covered_classes(remaining),
        'classifier': TemplateTileClassifier.from_labels(root, training),
        'experimental_training_review': {
            'registry_sha256': registry_digest,
            'excluded_images': sorted(excluded),
            'removed_training_labels': len(resources['training_labels']) - len(training),
            'development_only': True,
            'formal_promotion_evidence': False,
        },
    }
