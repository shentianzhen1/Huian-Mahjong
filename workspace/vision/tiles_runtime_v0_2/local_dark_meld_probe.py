"""Explicit OFFLINE geometry proposal for revealed dark-meld experiments.

Not imported by Runtime. Inputs are geometry component dictionaries; proposal
pixels/detector thresholds and temporal validation belong to the caller.
Groups here assert geometry only, never tile identities or legal melds.
"""

from statistics import median


def complete_gap_groups(components):
    """Return complete 3/4-face proposals, or None so callers retain baseline."""
    groups = []
    for item in sorted(components, key=lambda item: item['pixel_bbox'][0]):
        box = item['pixel_bbox']
        if not groups:
            groups.append([item])
            continue
        previous = groups[-1][-1]['pixel_bbox']
        gap = box[0] - previous[0] - previous[2]
        group_boxes = [member['pixel_bbox'] for member in groups[-1]]
        centre_y = median(y+h/2 for _, y, _, h in group_boxes)
        typical_height = median(h for _, _, _, h in group_boxes)
        vertically_aligned = abs(box[1]+box[3]/2-centre_y) <= typical_height*.8
        if gap > min(box[2], previous[2]) * .2 or not vertically_aligned:
            groups.append([item])
        else:
            groups[-1].append(item)
    return groups if groups and all(len(group) in (3, 4) for group in groups) else None


def _overlap_fraction(first, second):
    x, y, w, h = first
    bx, by, bw, bh = second
    area = max(0, min(x+w, bx+bw)-max(x, bx)) * max(0, min(y+h, by+bh)-max(y, by))
    return area / min(w*h, bw*bh)


def propose_local_meld_components(baseline, proposals):
    """Append local dark faces only when every proposed group is complete.

    Original component objects and all hand/Gold observations remain intact.
    Source/frame metadata is copied from a matching baseline meld seed.
    This is tuned development geometry, not a qualification/promotion gate.
    """
    seeds = [item for item in baseline if item['region_candidate'] == 'meld']
    additions = []
    for item in proposals:
        box = item['pixel_bbox']
        x, y, w, h = box
        if any(_overlap_fraction(box, other['pixel_bbox']) > .15
               for other in [*baseline, *additions]):
            continue
        for seed in seeds:
            if any(item.get(key) != seed.get(key) for key in ('frame', 'session')):
                continue
            sx, sy, sw, sh = seed['pixel_bbox']
            if (abs(y-sy) <= sh*.2 and abs(h-sh) <= sh*.25
                    and -sw*.1 <= x-(sx+sw) <= sw*.45):
                additions.append({**item, 'region_candidate': 'meld',
                                  'frame': seed.get('frame'), 'session': seed.get('session'),
                                  'confidence': .76, 'gold_skin': False})
                break
    if not additions or complete_gap_groups([*seeds, *additions]) is None:
        return baseline
    return [*baseline, *additions]
