# Raised-tile HOG/SVM feasibility — 2026-10-25

Using the current approved ordinary concealed crops and ten existing packet
hand references, compared fixed HOG features with linear and RBF SVC(C=10,
gamma=scale). Seven deterministic training variants: original, four small xy
translations, lower shadow and vertical compression. Query crops never train.
No Runtime wiring, threshold change or SVM-score→confidence mapping.

Strict reviewed exact-SHA lineage:75 original crops,525 variants,32 classes.
Permissive development scope:154 crops,1078 variants,34 classes; unresolved
source SHAs remain explicitly marked. Query exact source SHA is excluded.
Packet hand references retain the reviewed Sep26 group. W has one qualified
crop in one original-match group; M3 has six in two reviewed groups. This is
stored coverage, not demonstrated raised-appearance diversity.

On the two actual Runtime raised crops, strict linear predicts W/M9, strict
RBF predicts M3/M3; permissive linear W/M9, permissive RBF W/M3. Thus permissive
RBF alone gets both targets. Do not pick kernels per known truth class.

Tested that fixed RBF candidate against frozen truth for frames936,942,2466,
2514:62 ordinary tiles across four sampled frames. Strict model54/62 and0/4
exact hands (P2→P8 six times,P2→P5 twice); permissive model58/62 and1/4 exact
hands (S9→S8 four times). Repeated hands are not independent samples. These
were previously accepted development anchors, so replacing their classifier
would regress the intended whole-hand objective.

Reject deployment of this candidate. The target2/2 result is insufficient;
training fit525/525 and1078/1078 is not generalization evidence. Preserve
UNKNOWN,0.82, read-only Hint, V0.10 and Executor OFF. Next priority is qualified
raised/animated appearance coverage plus full-hand classification validation,
not more two-query tuning. No new independent source or label approval claimed.

The current OpenCV build lacks HOGDescriptor; the experiment explicitly used
NumPy gradients and9-bin cell histograms with2x2-cell L2-Hys blocks. Metadata
records the actual feature definition, dependency versions, source inventory,
query crop hashes and predictions. No private pixels or runtime model added.
No production code changed; no unrelated full tests rerun.
