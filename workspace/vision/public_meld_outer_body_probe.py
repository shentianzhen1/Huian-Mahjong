"""Development-only table-background contour probe; no identity inputs."""
from __future__ import annotations


def outer_body_box(image, detector_bbox):
    """Return an unclipped foreground envelope, or abstain.

    The median of a search-window rim estimates the table colour. This assumes
    a flat bottom meld on a locally uniform table, not arbitrary screenshots.
    """
    import cv2
    import numpy as np

    x, y, w, h = detector_bbox
    px, py = max(3, round(w * .1)), max(3, round(h * .1))
    left, top = max(0, x-px), max(0, y-py)
    right, bottom = min(image.width, x+w+px), min(image.height, y+h+py)
    rgb = np.asarray(image.crop((left, top, right, bottom))).astype(np.float32)
    rim = np.concatenate((rgb[:3].reshape(-1, 3), rgb[-3:].reshape(-1, 3),
                          rgb[:, :3].reshape(-1, 3), rgb[:, -3:].reshape(-1, 3)))
    background = np.median(rim, axis=0)
    mask = (np.linalg.norm(rgb-background, axis=2) > 30).astype(np.uint8)*255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    eligible = []
    for contour in contours:
        cx, cy, cw, ch = cv2.boundingRect(contour)
        gx, gy = left+cx, top+cy
        overlap = max(0, min(gx+cw, x+w)-max(gx, x))*max(0, min(gy+ch, y+h)-max(gy, y))
        if overlap > .4*w*h:
            eligible.append((cv2.contourArea(contour), (cx, cy, cw, ch)))
    audit = {'search_xyxy': [left, top, right, bottom],
             'background_rgb': background.tolist(), 'distance_threshold': 30,
             'search_padding_fraction': .1, 'eligible_contours': len(eligible)}
    if len(eligible) != 1:
        return None, {**audit, 'reason': 'ambiguous_or_absent_body'}
    _, (cx, cy, cw, ch) = eligible[0]
    if cx == 0 or cy == 0 or cx+cw == right-left or cy+ch == bottom-top:
        return None, {**audit, 'reason': 'body_touches_search_boundary'}
    box = (left+cx, top+cy, left+cx+cw, top+cy+ch)
    return box, {**audit, 'outer_body_xyxy': list(box)}


def face_plane_quads(image, detector_bbox, *, seam_context=2, fit_outer_edges=False, light_body_only=False):
    """Inspect blank face bands for sloping seams; abstain if unsupported.

    Equal thirds only constrain the seam search, never define accepted cuts.
    This deliberately narrow experiment supports flat, three-face rows only.
    """
    import cv2
    import numpy as np
    if light_body_only:
        from workspace.vision.public_meld_geometry_normalization import normalize_public_meld_crop, FLAT
        from workspace.vision.public_tile_detector import PublicGeometryCandidate
        candidate = PublicGeometryCandidate(detector_bbox, (0., 0., 1., 1.), 'bottom_group', 0., 0., None, None)
        analysis = normalize_public_meld_crop(image, candidate).analysis
        if analysis.stack_state != FLAT or abs(analysis.rotation_degrees) > .01 or analysis.tight_bbox_in_group is None:
            return (), {'reason': 'light_body_requires_unrotated_flat_row'}
        dx, dy, w, h = analysis.tight_bbox_in_group
        x, y = detector_bbox[0]+dx, detector_bbox[1]+dy
        box, audit = (x, y, x+w, y+h), {'boundary_seed': 'detector_light_face_body', 'face_seed_xyxy': [x, y, x+w, y+h]}
    else:
        box, audit = outer_body_box(image, detector_bbox)
    if box is None:
        return (), audit
    x, y, right, bottom = box
    rgb = np.asarray(image.crop(box))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    light = (hsv[:, :, 1] < 110) & (hsv[:, :, 2] > 110)
    occupied = np.flatnonzero(light.mean(axis=1) > .45)
    if len(occupied) < 10:
        return (), {**audit, 'reason': 'face_plane_absent'}
    first, last = int(occupied[0]), int(occupied[-1])
    height, width = last-first+1, right-x
    bands = []
    for lo, hi in ((first, first+max(1, round(height*.2))),
                   (first+round(height*.55), first+round(height*.85))):
        occupancy = light[lo:hi].mean(axis=1)
        row = lo+int(np.argmax(occupancy))
        if float(occupancy.max()) < .8:
            return (), {**audit, 'reason': 'blank_face_band_absent'}
        bands.append(row)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(float)
    seams = []
    outer_edges = []
    for row in bands:
        occupied_x = np.flatnonzero(light[row])
        outer_edges.append([float(occupied_x[0]), float(occupied_x[-1])])
        cuts = []
        for index in (1, 2):
            center, radius = round(width*index/3), max(2, round(width/12))
            lo, hi = center-radius, center+radius+1
            profile = gray[row, lo:hi]
            cut = lo+int(np.argmin(profile))
            contrast = float(np.percentile(profile, 80)-profile.min())
            if cut in (lo, hi-1) or contrast < 20:
                return (), {**audit, 'reason': 'seam_absent_or_search_edge'}
            cuts.append(cut)
        seams.append(cuts)
    top, end = max(0, y+first-2), min(image.height, y+last+3)
    def cuts_at(global_y):
        ratio = (global_y-y-bands[0])/(bands[1]-bands[0])
        left_edge = outer_edges[0][0]+ratio*(outer_edges[1][0]-outer_edges[0][0]) if fit_outer_edges else 0.0
        right_edge = outer_edges[0][1]+ratio*(outer_edges[1][1]-outer_edges[0][1]) if fit_outer_edges else float(width)
        return [left_edge]+[seams[0][i]+ratio*(seams[1][i]-seams[0][i]) for i in (0, 1)]+[right_edge]
    upper, lower = cuts_at(top), cuts_at(end-1)
    quads = []
    for index in range(3):
        offset_left = seam_context if index else 0
        offset_right = seam_context if index < 2 else 0
        quads.append(((x+upper[index]-offset_left, top),
                      (x+upper[index+1]+offset_right, top),
                      (x+lower[index+1]+offset_right, end-1),
                      (x+lower[index]-offset_left, end-1)))
    return tuple(quads), {**audit, 'face_plane_rows': [y+first, y+last+1],
        'blank_band_rows': [y+row for row in bands],
        'measured_seams_in_outer_body': seams, 'face_quads': quads,
        'fit_outer_edges': fit_outer_edges, 'measured_outer_edges_in_body': outer_edges,
        'light_body_only': light_body_only,
        'vertical_context': 2, 'seam_context': seam_context}


def rectify_face_quad(image, quad):
    import cv2
    import numpy as np
    from PIL import Image
    points = np.array(quad, dtype=np.float32)
    width = max(2, round(max(np.linalg.norm(points[1]-points[0]), np.linalg.norm(points[2]-points[3]))))
    height = max(2, round(max(np.linalg.norm(points[3]-points[0]), np.linalg.norm(points[2]-points[1]))))
    target = np.array(((0, 0), (width-1, 0), (width-1, height-1), (0, height-1)), dtype=np.float32)
    transform = cv2.getPerspectiveTransform(points, target)
    return Image.fromarray(cv2.warpPerspective(np.asarray(image), transform, (width, height)))
