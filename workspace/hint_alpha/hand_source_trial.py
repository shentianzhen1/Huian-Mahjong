"""Explicit read-only structural trial of high-score, single-source identities.

Raw Runtime rejection records remain unchanged. This is not source validation
and must never authorize public counts, danger, actions or classifier promotion.
"""
import math
from numbers import Real
from huian._legacy import env


def trial_hand_report(report):
    components, used = [], []
    for item in report.get('components', ()):
        if not isinstance(item, dict):
            components.append(item)
            continue
        changed = dict(item)
        score = item.get('tile_confidence')
        if (item.get('region_candidate') in {'hand', 'draw_visual'}
                and item.get('identity_reason') == 'class_not_cross_session_validated_in_region'
                and item.get('tile_id') == 'UNKNOWN'
                and item.get('candidate_tile_id') in env.BASE_TILES
                and not isinstance(score, bool) and isinstance(score, Real)
                and math.isfinite(score) and 0.82 <= score <= 1.):
            changed.update(tile_id=item['candidate_tile_id'], identity_reason='accepted',
                           original_identity_reason=item['identity_reason'])
            used.append(item['candidate_tile_id'])
        components.append(changed)
    if not used:
        return report, ()
    concealed = [c for c in components if isinstance(c, dict) and c.get('region_candidate') in {'hand', 'draw_visual'}]
    copied = dict(report, components=components,
        all_concealed_tile_ids_trusted=bool(concealed) and all(
            c.get('tile_id') in env.BASE_TILES and c.get('identity_reason') == 'accepted'
            for c in concealed))
    return copied, tuple(used)
