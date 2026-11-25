"""Report local-match reuse without changing the frozen development score."""


def match_multiplicity(query, reference):
    import cv2
    from workspace.vision.public_meld_identity_sift import SIFT_KNN_K, SIFT_RATIO_TEST, SIFT_FALLBACK_RAW_MATCHES
    if query is None or reference is None or min(len(query), len(reference)) < 2:
        return {'scorable': False}
    matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    pairs = matcher.knnMatch(query, reference, k=SIFT_KNN_K)
    matches = [p[0] for p in pairs if len(p) == SIFT_KNN_K and p[0].distance < SIFT_RATIO_TEST*p[1].distance]
    ratio_count = len(matches)
    if not matches:
        matches = sorted(matcher.match(query, reference), key=lambda m: m.distance)[:SIFT_FALLBACK_RAW_MATCHES]
    return {'scorable': True, 'query_descriptors': len(query), 'reference_descriptors': len(reference),
        'ratio_accepted_matches': ratio_count, 'raw_fallback_used': ratio_count == 0,
        'scoring_matches': len(matches), 'unique_reference_descriptor_indices': len({m.trainIdx for m in matches}),
        'many_to_one_reuse_count': len(matches)-len({m.trainIdx for m in matches}),
        'mean_scoring_distance': sum(m.distance for m in matches)/len(matches) if matches else None,
        'spatial_consistency_checked': False, 'score_changed': False}
