"""Explicit reference configuration for development video replay."""
import hashlib
import json
from pathlib import Path


def apply_replay_references(resources, manifest_path):
    from workspace.vision.tiles_runtime_v0_2.experimental_hand_translation import with_private_hand_packet
    from workspace.vision.tiles_runtime_v0_2.local_meld_trial import with_local_meld_trial
    path = Path(manifest_path).resolve()
    raw = path.read_bytes()
    manifest = json.loads(raw)
    adapted = with_private_hand_packet(resources, path)
    adapted = with_local_meld_trial(adapted)
    return adapted, {
        'version': manifest.get('version'), 'count': len(manifest['rows']),
        'manifest_sha256': hashlib.sha256(raw).hexdigest(),
        'training_review': adapted.get('experimental_training_review'),
        'geometry_policy': 'local_dark_meld_trial',
        'development_only': True, 'formal_promotion_evidence': False,
    }
