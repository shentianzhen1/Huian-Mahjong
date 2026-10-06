"""Development-only position-aware SIFT experiment; not Runtime confidence."""
from __future__ import annotations
import hashlib


def descriptor_key(descriptors):
    return hashlib.sha256(descriptors.tobytes()).hexdigest() if descriptors is not None else None


def _hull_area(points):
    import cv2
    return float(cv2.contourArea(cv2.convexHull(points))) if len(points) >= 3 else 0.0


def _grid_cells(points, *, grid_size=3):
    """Return occupied normalized grid cells for diagnostics only."""
    cells = set()
    for x, y in points:
        column = min(grid_size - 1, max(0, int(float(x) * grid_size)))
        row = min(grid_size - 1, max(0, int(float(y) * grid_size)))
        cells.add((column, row))
    return tuple(sorted(cells))


def _coverage_audit(query_positions, reference_positions, query_inliers, reference_inliers):
    """Describe how much of each whole-face keypoint layout the inliers explain.

    These values are diagnostic only and never participate in the score.
    Absolute hull coverage cannot be used as a generic acceptance gate because
    sparse tile artwork (for example S2) naturally occupies less area than
    denser artwork (for example S4).
    """
    q_full = _hull_area(query_positions)
    r_full = _hull_area(reference_positions)
    q_inlier = _hull_area(query_inliers)
    r_inlier = _hull_area(reference_inliers)
    q_full_cells = _grid_cells(query_positions)
    r_full_cells = _grid_cells(reference_positions)
    q_inlier_cells = _grid_cells(query_inliers)
    r_inlier_cells = _grid_cells(reference_inliers)
    return {
        'query_full_hull_area': q_full,
        'reference_full_hull_area': r_full,
        'query_inlier_hull_fraction': q_inlier / q_full if q_full > 0 else 0.0,
        'reference_inlier_hull_fraction': r_inlier / r_full if r_full > 0 else 0.0,
        'query_inlier_keypoint_fraction': (
            len(query_inliers) / len(query_positions) if len(query_positions) else 0.0
        ),
        'reference_inlier_keypoint_fraction': (
            len(reference_inliers) / len(reference_positions)
            if len(reference_positions) else 0.0
        ),
        'query_full_grid_cells': [list(cell) for cell in q_full_cells],
        'reference_full_grid_cells': [list(cell) for cell in r_full_cells],
        'query_inlier_grid_cells': [list(cell) for cell in q_inlier_cells],
        'reference_inlier_grid_cells': [list(cell) for cell in r_inlier_cells],
        'query_unmatched_grid_cells': [
            list(cell) for cell in q_full_cells if cell not in set(q_inlier_cells)
        ],
        'reference_unmatched_grid_cells': [
            list(cell) for cell in r_full_cells if cell not in set(r_inlier_cells)
        ],
    }


def _affine_points(points, matrix):
    import numpy as np
    values = np.asarray(points, dtype=np.float32)
    if not len(values):
        return values
    return values @ matrix[:, :2].T + matrix[:, 2]


def _nearest_support_fraction(source_points, target_points, *, radius=.08):
    """Fraction of source keypoints supported by a nearby target keypoint."""
    import numpy as np
    if not len(source_points) or not len(target_points):
        return 0.0
    distances = np.linalg.norm(
        np.asarray(source_points)[:, None, :] - np.asarray(target_points)[None, :, :],
        axis=2,
    )
    return float((distances.min(axis=1) <= radius).mean())


def _bidirectional_affine_support(query_positions, reference_positions, matrix, *, radius=.08):
    """Measure whole-pattern support after the accepted affine alignment.

    Diagnostic only: this does not alter the SIFT score or acceptance result.
    The two directions stay separate because sparse and dense tile artwork have
    different natural keypoint coverage.
    """
    import cv2
    import numpy as np
    matrix = np.asarray(matrix, dtype=np.float32)
    inverse = cv2.invertAffineTransform(matrix)
    query_in_reference = _affine_points(query_positions, matrix)
    reference_in_query = _affine_points(reference_positions, inverse)
    return {
        'bidirectional_support_checked': True,
        'support_radius_normalized': radius,
        'query_keypoints_supported_by_reference_fraction': _nearest_support_fraction(
            query_in_reference, reference_positions, radius=radius
        ),
        'reference_keypoints_supported_by_query_fraction': _nearest_support_fraction(
            reference_in_query, query_positions, radius=radius
        ),
    }


def _reverse_descriptor_reference_support(
    query_descriptors,
    reference_descriptors,
    query_positions,
    reference_positions,
    matrix,
    *,
    radius=.2,
    ratio=.8,
):
    """Audit reference content explained by query after accepted affine.

    The forward affine is inverted to predict where each reference keypoint
    should appear in the query. Nearby query descriptors must then pass the
    same ratio-test idea in the reverse direction.

    This is audit-only: it never alters the forward score, ranking, Runtime
    confidence, Hint, or Executor behavior.
    """
    import cv2
    import numpy as np

    inverse = cv2.invertAffineTransform(
        np.asarray(matrix, dtype=np.float32)
    )
    predicted_query_positions = _affine_points(
        reference_positions, inverse
    )
    proposed = []
    for reference_index, descriptor in enumerate(reference_descriptors):
        neighbors = np.flatnonzero(
            np.linalg.norm(
                query_positions - predicted_query_positions[reference_index],
                axis=1,
            )
            <= radius
        )
        if len(neighbors) < 2:
            continue
        distances = np.linalg.norm(
            query_descriptors[neighbors] - descriptor,
            axis=1,
        )
        order = np.argsort(distances, kind='stable')
        if distances[order[0]] < ratio * distances[order[1]]:
            proposed.append(
                (
                    float(distances[order[0]]),
                    reference_index,
                    int(neighbors[order[0]]),
                )
            )

    proposed.sort()
    matched = []
    used_reference = set()
    used_query = set()
    for distance, reference_index, query_index in proposed:
        reference_position = tuple(
            np.round(reference_positions[reference_index], 2)
        )
        query_position = tuple(np.round(query_positions[query_index], 2))
        if (
            reference_position in used_reference
            or query_position in used_query
        ):
            continue
        used_reference.add(reference_position)
        used_query.add(query_position)
        matched.append((distance, reference_index, query_index))

    matched_reference = np.asarray(
        [reference_positions[index] for _, index, _ in matched],
        dtype=np.float32,
    )
    matched_query = np.asarray(
        [query_positions[index] for _, _, index in matched],
        dtype=np.float32,
    )
    reference_full_hull = _hull_area(reference_positions)
    query_full_hull = _hull_area(query_positions)
    reference_matched_hull = _hull_area(matched_reference)
    query_matched_hull = _hull_area(matched_query)
    reference_full_cells = _grid_cells(reference_positions)
    reference_matched_cells = _grid_cells(matched_reference)

    return {
        'reverse_descriptor_support_checked': True,
        'reverse_descriptor_position_window': radius,
        'reverse_descriptor_ratio_test': ratio,
        'reverse_descriptor_ratio_matches': len(proposed),
        'reverse_descriptor_unique_position_pairs': len(matched),
        'reverse_descriptor_reference_keypoint_fraction': (
            len(matched_reference) / len(reference_positions)
            if len(reference_positions) else 0.0
        ),
        'reverse_descriptor_query_keypoint_fraction': (
            len(matched_query) / len(query_positions)
            if len(query_positions) else 0.0
        ),
        'reverse_descriptor_reference_hull_fraction': (
            reference_matched_hull / reference_full_hull
            if reference_full_hull > 0 else 0.0
        ),
        'reverse_descriptor_query_hull_fraction': (
            query_matched_hull / query_full_hull
            if query_full_hull > 0 else 0.0
        ),
        'reverse_descriptor_reference_unexplained_grid_cells': [
            list(cell)
            for cell in reference_full_cells
            if cell not in set(reference_matched_cells)
        ],
        'reverse_descriptor_mean_distance': (
            float(np.mean([distance for distance, _, _ in matched]))
            if matched else None
        ),
    }


def reference_completeness_score(forward_score, audit):
    """Reweight one development score by whole-reference geometric support.

    This is an offline candidate only. It adds no acceptance threshold and
    fails closed when the bidirectional reference-support audit is unavailable.
    """
    if forward_score is None:
        return None
    if isinstance(forward_score, bool) or not isinstance(forward_score, (int, float)):
        raise ValueError('forward_score must be numeric or None')
    if forward_score <= 0:
        return 0.0
    support = audit.get('reference_keypoints_supported_by_query_fraction')
    if support is None:
        return 0.0
    if (
        isinstance(support, bool)
        or not isinstance(support, (int, float))
        or not 0.0 <= float(support) <= 1.0
    ):
        raise ValueError('reference support must be within [0, 1]')
    return float(forward_score) * float(support)


class PositionedSift:
    """Retain positions while preserving the frozen descriptor extraction."""
    def __init__(self, *, local_window=False):
        self.positions = {}
        self.last_audit = {}
        self.local_window = local_window

    def extract(self, image):
        import cv2
        import numpy as np
        from workspace.vision.public_meld_identity_sift import (
            SIFT_SCALE_FACTOR, SIFT_CLAHE_CLIP_LIMIT, SIFT_CLAHE_TILE_GRID, SIFT_NFEATURES)
        rgb = np.asarray(image.convert('RGB'))
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        gray = cv2.resize(gray, None, fx=SIFT_SCALE_FACTOR, fy=SIFT_SCALE_FACTOR, interpolation=cv2.INTER_CUBIC)
        gray = cv2.createCLAHE(clipLimit=SIFT_CLAHE_CLIP_LIMIT, tileGridSize=SIFT_CLAHE_TILE_GRID).apply(gray)
        points, descriptors = cv2.SIFT_create(nfeatures=SIFT_NFEATURES).detectAndCompute(gray, None)
        if descriptors is None or len(descriptors) < 2:
            return None
        descriptors = descriptors.astype('float32', copy=False)
        positions = np.array([(p.pt[0]/gray.shape[1], p.pt[1]/gray.shape[0]) for p in points], dtype=np.float32)
        key = descriptor_key(descriptors)
        if key in self.positions and not np.array_equal(self.positions[key], positions):
            raise ValueError('descriptor fingerprint has conflicting positions')
        self.positions[key] = positions
        return descriptors

    def score(self, query, reference):
        import cv2
        import numpy as np
        from workspace.vision.public_meld_identity_sift import SIFT_RATIO_TEST, SIFT_KNN_K
        if query is None or reference is None or min(len(query), len(reference)) < 2:
            self.last_audit = {'reason': 'descriptors_absent'}
            return None
        q, r = self.positions[descriptor_key(query)], self.positions[descriptor_key(reference)]
        if self.local_window:
            proposed = []
            for index, descriptor in enumerate(query):
                neighbors = np.flatnonzero(np.linalg.norm(r-q[index], axis=1) <= .2)
                if len(neighbors) < 2:
                    continue
                distances = np.linalg.norm(reference[neighbors]-descriptor, axis=1)
                order = np.argsort(distances, kind='stable')
                if distances[order[0]] < SIFT_RATIO_TEST*distances[order[1]]:
                    proposed.append(cv2.DMatch(index, int(neighbors[order[0]]), float(distances[order[0]])))
        else:
            pairs = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False).knnMatch(query, reference, k=SIFT_KNN_K)
            proposed = [p[0] for p in pairs if len(p)==SIFT_KNN_K and p[0].distance < SIFT_RATIO_TEST*p[1].distance]
        proposed = sorted(proposed, key=lambda m:(m.distance,m.queryIdx,m.trainIdx))
        matches = []
        used_q, used_r = set(), set()
        for m in proposed:
            qp, rp = tuple(np.round(q[m.queryIdx], 2)), tuple(np.round(r[m.trainIdx], 2))
            if qp not in used_q and rp not in used_r:
                matches.append(m); used_q.add(qp); used_r.add(rp)
        audit = {'ratio_matches':len(proposed), 'unique_position_pairs':len(matches),
                 'local_position_window':.2 if self.local_window else None,
                 'raw_match_fallback':False, 'spatial_consistency_checked':True,
                 'pattern_coverage_checked':False}
        if len(matches) < 4:
            self.last_audit = {**audit, 'reason':'insufficient_unique_pairs', 'inliers':0}
            return 0.0
        src = np.array([q[m.queryIdx] for m in matches], dtype=np.float32)
        dst = np.array([r[m.trainIdx] for m in matches], dtype=np.float32)
        cv2.setRNGSeed(69)
        matrix, mask = cv2.estimateAffine2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=.04, maxIters=2000, confidence=.99, refineIters=10)
        if matrix is None or mask is None:
            self.last_audit = {**audit,'reason':'affine_fit_failed','inliers':0}
            return 0.0
        singular = np.linalg.svd(matrix[:, :2], compute_uv=False)
        if np.linalg.det(matrix[:, :2]) <= 0 or singular.min() < .65 or singular.max() > 1.5 or np.max(np.abs(matrix[:, 2])) > .2:
            self.last_audit = {**audit,'reason':'implausible_normalized_affine','inliers':int(mask.sum()),'affine':matrix.tolist()}
            return 0.0
        selected = mask.ravel().astype(bool)
        count = int(selected.sum())
        q_inliers, r_inliers = src[selected], dst[selected]
        q_area, r_area = _hull_area(q_inliers), _hull_area(r_inliers)
        coverage = _coverage_audit(q, r, q_inliers, r_inliers)
        bidirectional = _bidirectional_affine_support(q, r, matrix)
        reverse_descriptor = {'reverse_descriptor_support_checked': False}
        if self.local_window:
            reverse_descriptor = _reverse_descriptor_reference_support(
                query,
                reference,
                q,
                r,
                matrix,
                radius=.2,
                ratio=SIFT_RATIO_TEST,
            )
        if count < 4 or min(q_area, r_area) < .01:
            self.last_audit = {
                **audit, **coverage, **bidirectional, **reverse_descriptor, 'pattern_coverage_checked':True,
                'reason':'localized_or_sparse_inliers','inliers':count,
                'query_hull_area':q_area,'reference_hull_area':r_area,
            }
            return 0.0
        distance = float(np.mean([m.distance for m, keep in zip(matches, selected) if keep]))
        score = count/(len(query)*len(reference))**.5 * (q_area*r_area)**.5 / (1+distance/512)
        self.last_audit = {
            **audit, **coverage, **bidirectional, **reverse_descriptor, 'pattern_coverage_checked':True,
            'reason':None,'inliers':count,'query_hull_area':q_area,
            'reference_hull_area':r_area,'mean_descriptor_distance':distance,
            'affine':matrix.tolist(),'score':float(score),
        }
        return float(score)
