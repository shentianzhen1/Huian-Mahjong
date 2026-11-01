"""Development scoring of Gold SIFT evidence; no Runtime confidence promotion."""
from __future__ import annotations

import math

FEATURE_NAMES = ('log_best', 'log_second', 'relative_margin', 'numeral_method',
                 'log_unique_matches', 'unique_ratio', 'log_inliers',
                 'inlier_ratio', 'inlier_coverage')


def geometry_evidence(query, reference):
    import cv2
    import numpy as np
    zero = dict(unique_matches=0, unique_ratio=0.0, inliers=0,
                inlier_ratio=0.0, inlier_coverage=0.0)
    points, descriptors, size = query
    target, bank, _ = reference
    if descriptors is None or bank is None or len(descriptors)<2 or len(bank)<2:
        return zero
    matches = cv2.BFMatcher(cv2.NORM_L2).knnMatch(descriptors, bank, k=2)
    good = [a for a,b in matches if a.distance < 0.75*b.distance]
    # Several query points mapped to one reference point are not independent
    # geometric correspondences. Keep only the closest one for each target.
    unique = {}
    for match in sorted(good, key=lambda m:m.distance):
        unique.setdefault(match.trainIdx, match)
    selected = list(unique.values())
    result = dict(zero, unique_matches=len(selected), unique_ratio=len(selected)/max(1,len(good)))
    if len(selected)<4:
        return result
    source = np.float32([points[m.queryIdx] for m in selected])
    destination = np.float32([target[m.trainIdx] for m in selected])
    cv2.setRNGSeed(0)
    homography, mask = cv2.findHomography(source, destination, cv2.RANSAC, 3.0)
    if homography is None or mask is None:
        return result
    keep = mask.ravel().astype(bool)
    n = int(keep.sum())
    coverage = 0.0
    if n>=3:
        coverage = float(cv2.contourArea(cv2.convexHull(source[keep])))/(size[0]*size[1])
    result.update(inliers=n, inlier_ratio=n/len(selected),
                  inlier_coverage=max(0.0,min(1.0,coverage)))
    return result


def evidence_features(classifier, image, prediction):
    from workspace.vision.tiles_v0_1.gold_classifier import (
        _sift_features, _wan_numeral_features, _good_sift_matches,
    )
    numeral = prediction.method == 'sift_wan_numeral'
    details = classifier.numeral_details if numeral else classifier.full_details
    query = _wan_numeral_features(image) if numeral else _sift_features(image)
    references = details.get(prediction.tile_id, [])
    geometry = dict(unique_matches=0,unique_ratio=0.,inliers=0,inlier_ratio=0.,inlier_coverage=0.)
    if references:
        reference = max(references, key=lambda r:_good_sift_matches(query[1],r[1]))
        geometry = geometry_evidence(query,reference)
    b,s = prediction.evidence_count,prediction.second_best_evidence_count
    vector = [math.log1p(b),math.log1p(s),(b-s)/max(1,b),int(numeral),
              math.log1p(geometry['unique_matches']),geometry['unique_ratio'],
              math.log1p(geometry['inliers']),geometry['inlier_ratio'],geometry['inlier_coverage']]
    return vector,geometry


def probability(vector, model, *, candidate):
    if candidate == 'UNKNOWN':
        return 0.0
    if model['feature_names'] != list(FEATURE_NAMES):
        raise ValueError('Scoring feature definition mismatch')
    if len(vector) != len(model['feature_names']):
        raise ValueError('Scoring feature count mismatch')
    if any(not math.isfinite(float(x)) for x in vector):
        raise ValueError('Scoring features must be finite')
    z = model['intercept'] + sum(w*(x-m)/s for w,x,m,s in zip(
        model['coef'],vector,model['mean'],model['scale']))
    return 1/(1+math.exp(-z)) if z>=0 else math.exp(z)/(1+math.exp(z))


def training_labels(dataset_root, lineage_path, excluded_images, excluded_groups):
    from workspace.vision.tiles_v0_1.labels import approved_labels
    from workspace.vision.concealed_template_match_lineage import load_concealed_template_lineage
    lineage=load_concealed_template_lineage(lineage_path)
    labels=[r for r in approved_labels(dataset_root) if r['image'] not in excluded_images
            and (r.get('sha256') not in lineage or lineage[r['sha256']].match_group not in excluded_groups)]
    return labels,lineage


def fit_development_model(dataset_root, lineage_path, crop_review_path, excluded_groups):
    import hashlib
    import json
    from pathlib import Path
    from collections import Counter
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from workspace.vision.tiles_v0_1.gold_classifier import GoldTileClassifier,_crop_label
    review=json.loads(Path(crop_review_path).read_text())
    excluded_images=[r['image'] for r in review['excluded_training_images']]
    labels,lineage=training_labels(dataset_root,lineage_path,set(excluded_images),set(excluded_groups))
    def group(row):
        return ('match:'+lineage[row['sha256']].match_group if row.get('sha256') in lineage
                else 'unresolved-sha:'+row['sha256'])
    queries=[r for r in labels if r['region'] in ('hand_region','draw_region','draw_visual')
             and not r.get('gold_skin_only')]
    classifiers,rows={},[]
    for row in queries:
        g=group(row)
        if g not in classifiers:
            classifiers[g]=GoldTileClassifier.from_labels(dataset_root,[r for r in labels if group(r)!=g])
        image=_crop_label(Path(dataset_root),row)
        prediction=classifiers[g].classify(image)
        vector,geometry=evidence_features(classifiers[g],image,prediction)
        rows.append(dict(image=row['image'],group=g,truth=row['tile_id'],candidate=prediction.tile_id,
                         correct=prediction.tile_id==row['tile_id'],features=vector,geometry=geometry))
    known=[r for r in rows if r['candidate']!='UNKNOWN']
    counts=Counter((r['group'],r['truth']) for r in known)
    weights=np.array([1/counts[(r['group'],r['truth'])] for r in known])
    x=np.array([r['features'] for r in known]);y=np.array([r['correct'] for r in known])
    # Preserve the observed source/class-weighted prior. Balancing positive and
    # negative outcomes would produce a discrimination score, not this estimate.
    scaler=StandardScaler().fit(x,sample_weight=weights)
    logistic=LogisticRegression(C=1,random_state=0,max_iter=1000).fit(
        scaler.transform(x),y,sample_weight=weights)
    model=dict(schema_version='gold_sift_score_model_development_v0_1',
        development_only=True,safe_for_runtime=False,safe_for_hint=False,safe_for_executor=False,
        scope='opened_gold_only_not_hand',feature_names=list(FEATURE_NAMES),
        coef=logistic.coef_[0].tolist(),intercept=float(logistic.intercept_[0]),
        mean=scaler.mean_.tolist(),scale=scaler.scale_.tolist(),
        lineage_path=str(lineage_path),excluded_images=excluded_images,excluded_groups=sorted(excluded_groups),
        fit_method='source/class-weighted logistic C=1 seed=0; no outcome class balancing',
        training_queries=len(rows),training_known=len(known),training_correct=int(sum(y)),
        training_groups=len(classifiers),unresolved_query_groups=sum(g.startswith('unresolved-sha:') for g in classifiers),
        weighted_positive_prior=float(np.average(y,weights=weights)),
        training_trace_sha256=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        confidence_domain_validation='NOT_ESTABLISHED; revealed Gold checks only')
    return model,rows,labels


class GoldOnlyScoredClassifier:
    """Opt-in offline adapter; ordinary hand/draw classification stays unchanged."""
    def __init__(self, ordinary_classifier, gold_classifier, model):
        self.ordinary=ordinary_classifier
        self.gold=gold_classifier
        self.model=model

    def classify(self,image,region=None):
        return self.ordinary.classify(image,region=region)

    def classify_gold_skin(self,image):
        return self.ordinary.classify_gold_skin(image)

    def classify_opened_gold(self,image):
        from workspace.vision.tiles_v0_1.template_classifier import Classification
        candidate=self.gold.classify(image)
        features,_=evidence_features(self.gold,image,candidate)
        return Classification(candidate.tile_id,probability(features,self.model,candidate=candidate.tile_id))


def experimental_resources(resources,dataset_root,model):
    from workspace.vision.tiles_v0_1.gold_classifier import GoldTileClassifier
    labels,_=training_labels(dataset_root,model['lineage_path'],set(model['excluded_images']),set(model['excluded_groups']))
    copied=dict(resources)
    copied['classifier']=GoldOnlyScoredClassifier(resources['classifier'],
        GoldTileClassifier.from_labels(dataset_root,labels),model)
    return copied


def main():
    import argparse,json,hashlib
    from pathlib import Path
    from PIL import Image
    from workspace.vision.tiles_v0_1.gold_classifier import GoldTileClassifier
    parser=argparse.ArgumentParser(description='Fit and test a development Gold-only scoring model')
    parser.add_argument('--dataset',type=Path,default=Path('dataset/tiles_runtime_v0_2'))
    parser.add_argument('--lineage',type=Path,default=Path('references/vision/2026-10-01/concealed_template_match_lineage.development.json'))
    parser.add_argument('--crop-review',type=Path,default=Path('references/vision/2026-10-24/sampled_classifier_crop_review_v0_1.json'))
    parser.add_argument('--exclude-match',action='append',default=[])
    parser.add_argument('--queries',type=Path,required=True)
    parser.add_argument('--model-output',type=Path,required=True)
    parser.add_argument('--report-output',type=Path,required=True)
    args=parser.parse_args()
    model,_,labels=fit_development_model(args.dataset,args.lineage,args.crop_review,args.exclude_match)
    classifier=GoldTileClassifier.from_labels(args.dataset,labels)
    manifest=json.loads(args.queries.read_text());rows=[]
    for query in manifest['queries']:
        with Image.open(args.queries.parent/query['crop']) as original:image=original.convert('RGB')
        if hashlib.sha256(image.tobytes()).hexdigest()!=query['crop_rgb_sha256']:
            raise ValueError('Gold query RGB mismatch')
        for removed in (False,True):
            bank=classifier if not removed else GoldTileClassifier.from_labels(args.dataset,[r for r in labels if r['tile_id']!=query['truth']])
            candidate=bank.classify(image);features,geometry=evidence_features(bank,image,candidate)
            score=probability(features,model,candidate=candidate.tile_id)
            rows.append(dict(query=query['query'],truth=query['truth'],candidate=candidate.tile_id,
                true_class_removed=removed,correct=candidate.tile_id==query['truth'],
                score=score,passes_082=score>=0.82,features=features,geometry=geometry))
    report=dict(development_only=True,formal_promotion_evidence=False,runtime_changed=False,
        real_queries=sum(not r['true_class_removed'] for r in rows),
        real_passes=sum(not r['true_class_removed'] and r['passes_082'] for r in rows),
        real_wrong_passes=sum(not r['true_class_removed'] and r['passes_082'] and not r['correct'] for r in rows),
        class_removed_wrong_passes=sum(r['true_class_removed'] and r['passes_082'] for r in rows),rows=rows,
        training_trace_sha256=model['training_trace_sha256'])
    args.model_output.write_text(json.dumps(model,indent=2)+'\n')
    args.report_output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}))


if __name__=='__main__':main()
