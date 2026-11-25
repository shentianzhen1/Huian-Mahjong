"""Read-only opened-Gold trial; raw source-rejection records remain unchanged."""
import math
from numbers import Real
from huian._legacy import env

_REASONS = {'class_not_cross_session_validated_in_region', 'class_missing_real_gold_skin_example'}


def trial_opened_gold_report(report):
    observations = report.get('gold_identity_observations', ())
    frames = report.get('frames', ())
    if (report.get('geometry_untrusted', True) or len(observations) < 3
            or len(set(frames)) != len(frames)):
        return report, ()
    changed_observations, used = [], []
    for item in observations:
        score = item.get('tile_confidence')
        tile = item.get('candidate_tile_id')
        if (isinstance(item.get('frame'), bool) or item.get('frame') not in frames or tile not in env.BASE_TILES
                or item.get('opened_gold_reference_supported') is not True
                or isinstance(score, bool) or not isinstance(score, Real)
                or not math.isfinite(score) or not .82 <= score <= 1.):
            return report, ()
        changed = dict(item)
        if item.get('tile_id') == 'UNKNOWN' and item.get('identity_reason') in _REASONS:
            changed.update(tile_id=tile, identity_reason='accepted',
                           original_identity_reason=item['identity_reason'])
            used.append(tile)
        elif item.get('tile_id') != tile or item.get('identity_reason') != 'accepted':
            return report, ()
        changed_observations.append(changed)
    if (not used or len({o['frame'] for o in changed_observations}) < 3
            or len({o['tile_id'] for o in changed_observations}) != 1):
        return report, ()
    tile = changed_observations[0]['tile_id']
    components = []
    gold_count = 0
    for item in report.get('components', ()):
        changed = dict(item)
        if item.get('region_candidate') == 'gold':
            gold_count += 1
            score = item.get('tile_confidence')
            if (item.get('candidate_tile_id') != tile
                    or item.get('frame') not in frames
                    or isinstance(item.get('frame'), bool)
                    or isinstance(score, bool) or not isinstance(score, Real)
                    or not math.isfinite(score) or not .82 <= score <= 1.
                    or item.get('opened_gold_reference_supported') is not True):
                return report, ()
            if item.get('tile_id') == 'UNKNOWN' and item.get('identity_reason') in _REASONS:
                changed.update(tile_id=tile, identity_reason='accepted',
                               original_identity_reason=item['identity_reason'])
            elif item.get('tile_id') != tile or item.get('identity_reason') != 'accepted':
                return report, ()
        components.append(changed)
    if gold_count != 1:
        return report, ()
    return dict(report, components=components,
                gold_identity_observations=changed_observations), tuple(used)
