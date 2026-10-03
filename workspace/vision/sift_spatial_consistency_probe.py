"""Development-only position-aware SIFT experiment; not Runtime confidence."""
from __future__ import annotations
import hashlib


def descriptor_key(descriptors):
    return hashlib.sha256(descriptors.tobytes()).hexdigest() if descriptors is not None else None


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
                 'raw_match_fallback':False, 'spatial_consistency_checked':True}
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
        def hull_area(points):
            return float(cv2.contourArea(cv2.convexHull(points))) if len(points) >= 3 else 0.0
        q_area, r_area = hull_area(src[selected]), hull_area(dst[selected])
        if count < 4 or min(q_area, r_area) < .01:
            self.last_audit = {**audit,'reason':'localized_or_sparse_inliers','inliers':count,'query_hull_area':q_area,'reference_hull_area':r_area}
            return 0.0
        distance = float(np.mean([m.distance for m, keep in zip(matches, selected) if keep]))
        score = count/(len(query)*len(reference))**.5 * (q_area*r_area)**.5 / (1+distance/512)
        self.last_audit = {**audit,'reason':None,'inliers':count,'query_hull_area':q_area,'reference_hull_area':r_area,
                           'mean_descriptor_distance':distance,'affine':matrix.tolist(),'score':float(score)}
        return float(score)
